"""Business logic for process 50 — ta_to_instructor_auto."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student, User
from app.services.course_committee_roster_service import list_course_catalog_options

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
REQUIRED_PASSES = 2
REQUIRED_RANK = "assistant_faculty"


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _safe_int(val: Any, default: int = 0) -> int:
    try:
        if val is None:
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def _course_label(code: str) -> str:
    for opt in list_course_catalog_options():
        if str(opt.get("value")) == str(code):
            return str(opt.get("label_fa") or code)
    return str(code or "—")


def _track_label(code: str) -> str:
    from app.services.course_committee_roster_service import _load_roster_file

    for track in _load_roster_file().get("tracks") or []:
        if isinstance(track, dict) and str(track.get("code")) == str(code):
            return str(track.get("name_fa") or code)
    return str(code or "—")


def _iter_ta_pass_counts(lms: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize TA pass records from LMS extra_data."""
    rows: list[dict[str, Any]] = []

    passes_map = lms.get("ta_course_passes")
    if isinstance(passes_map, dict):
        for code, count in passes_map.items():
            rows.append({
                "course_code": str(code),
                "pass_count": _safe_int(count),
                "track_code": (lms.get("ta_course_tracks") or {}).get(str(code)),
            })

    records = lms.get("ta_course_records")
    if isinstance(records, list):
        for rec in records:
            if not isinstance(rec, dict):
                continue
            rows.append({
                "course_code": str(rec.get("course_code") or rec.get("code") or ""),
                "pass_count": _safe_int(rec.get("pass_count") or rec.get("passes")),
                "track_code": rec.get("track_code") or rec.get("track"),
                "course_name": rec.get("course_name"),
                "track_name": rec.get("track_name"),
            })

    return [r for r in rows if r.get("course_code")]


def _resolve_next_course(
    lms: dict[str, Any],
    *,
    track_code: str,
    source_course_code: str,
) -> tuple[Optional[str], Optional[str]]:
    sequences = lms.get("track_course_sequences") or {}
    seq = sequences.get(track_code) if isinstance(sequences, dict) else None
    if not isinstance(seq, list) or not seq:
        catalog = [o["value"] for o in list_course_catalog_options()]
        seq = catalog

    codes = [str(c) for c in seq]
    try:
        idx = codes.index(str(source_course_code))
    except ValueError:
        return None, None
    if idx + 1 >= len(codes):
        return None, None
    nxt = codes[idx + 1]
    return nxt, _course_label(nxt)


def evaluate_ta_to_instructor_eligibility(
    student: Student,
    user: Optional[User] = None,
) -> dict[str, Any]:
    """Return eligibility summary for process 50."""
    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    rank = str(extra.get("rank") or (user.role if user else "") or "").strip()
    rank_ok = rank == REQUIRED_RANK

    qualifying = None
    for row in _iter_ta_pass_counts(lms):
        if _safe_int(row.get("pass_count")) >= REQUIRED_PASSES:
            qualifying = row
            break

    eligible = rank_ok and qualifying is not None
    source_code = str(qualifying.get("course_code")) if qualifying else ""
    track_code = str(qualifying.get("track_code") or lms.get("active_ta_track") or "") if qualifying else ""
    next_code, next_name = (
        _resolve_next_course(lms, track_code=track_code, source_course_code=source_code)
        if qualifying and track_code
        else (None, None)
    )

    source_name = (
        qualifying.get("course_name")
        if qualifying and qualifying.get("course_name")
        else _course_label(source_code)
    )
    track_name = (
        qualifying.get("track_name")
        if qualifying and qualifying.get("track_name")
        else _track_label(track_code)
    )

    return {
        "eligible": eligible,
        "rank_ok": rank_ok,
        "current_rank": rank or "—",
        "passes_ok": qualifying is not None,
        "required_passes": REQUIRED_PASSES,
        "source_course_code": source_code or None,
        "source_course_name": source_name or None,
        "track_code": track_code or None,
        "track_name": track_name or None,
        "next_course_code": next_code,
        "next_course_name": next_name,
        "promoted_role": "instructor",
        "eligibility_summary_fa": (
            f"رتبه دستیار هیئت علمی: {'✓' if rank_ok else '✗'}؛ "
            f"دو بار پاس موفق در یک درس: {'✓' if qualifying else '✗'}"
        ),
    }


async def build_ta_to_instructor_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    stmt = select(Student).where(Student.id == student_id)
    student = (await db.execute(stmt)).scalars().first()
    if not student:
        return dict(existing or {})

    user = None
    if student.user_id:
        user = (await db.execute(select(User).where(User.id == student.user_id))).scalars().first()

    ev = evaluate_ta_to_instructor_eligibility(student, user)
    ctx = {
        **ev,
        "course_name": ev.get("source_course_name"),
        "course_code": ev.get("source_course_code"),
        "next_course_code": ev.get("next_course_code"),
    }
    if student.user_id and user and user.full_name_fa:
        ctx["student_name_fa"] = user.full_name_fa
    return {**_as_mapping(existing), **ctx}


async def persist_ta_to_instructor_context(
    db: AsyncSession,
    instance: ProcessInstance,
    extra_fields: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ctx = await build_ta_to_instructor_context(
        db,
        instance.student_id,
        {**_as_mapping(instance.context_data), **_as_mapping(extra_fields)},
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()
    return ctx


async def run_auto_ta_to_instructor_transition(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    actor_id: uuid.UUID | None = None,
) -> Optional[str]:
    """Auto-fire conditions_met or conditions_failed from end_of_term_check."""
    from app.core.engine import InvalidTransitionError, StateMachineEngine

    if instance.process_code != "ta_to_instructor_auto":
        return None
    if instance.current_state_code != "end_of_term_check":
        return None
    if instance.is_completed or instance.is_cancelled:
        return None

    ctx = await persist_ta_to_instructor_context(db, instance)
    trigger = "conditions_met" if ctx.get("eligible") else "conditions_failed"
    if trigger == "conditions_met":
        ctx["upgrade_applied_at"] = datetime.now(timezone.utc).isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db.flush()

    engine = StateMachineEngine(db)
    aid = actor_id or SYSTEM_ACTOR_ID
    try:
        res = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event=trigger,
            actor_id=aid,
            actor_role="admin",
            payload={},
        )
        if res.success:
            return res.to_state
    except InvalidTransitionError as exc:
        logger.warning("ta_to_instructor_auto auto transition failed: %s", exc)
    return None
