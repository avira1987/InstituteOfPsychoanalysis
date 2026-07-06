"""Business logic for process 49 — ta_to_assistant_faculty."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student, User
from app.services.course_committee_roster_service import (
    list_course_catalog_options,
    merge_course_grants,
    promote_ta_to_instructor_on_roster,
)
from app.services.ta_track_change_service import get_active_ta_tracks

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
REQUIRED_PASSES = 2
ASSISTANT_RANK_CODES = frozenset({"assistant_faculty", "instructor"})

REJECT_MESSAGE_FA = (
    "صلاحیت ارتقا به مدرس/دستیار هیئت علمی در این مرحله تأیید نشد. "
    "برای درخواست ارزیابی مجدد در ترم‌های بعد از گزینهٔ «درخواست ارزیابی مجدد» استفاده کنید."
)
ALREADY_ASSISTANT_MESSAGE_FA = (
    "شما قبلاً رتبهٔ تحلیلی دستیار هیئت علمی را اخذ کرده‌اید."
)
UPGRADE_SUCCESS_HINT_FA = (
    "ارتقا با موفقیت اعمال شد. نقش شما در این درس به «مدرس» تغییر یافت "
    "و در صورت اولین ارتقا، رتبهٔ تحلیلی به دستیار هیئت علمی ارتقا یافت."
)

RANK_LABELS_FA = {
    "teaching_assistant": "کمک‌مدرس",
    "assistant_faculty": "دستیار هیئت علمی",
    "instructor": "مدرس",
    "student": "دانشجو",
}


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


def _resolve_rank(student: Student, user: Optional[User] = None) -> str:
    extra = _as_mapping(student.extra_data)
    rank = str(extra.get("rank") or "").strip()
    if rank:
        return rank
    if user and (user.role or "").strip():
        return str(user.role).strip()
    return "teaching_assistant"


def _rank_label_fa(rank_code: str) -> str:
    return RANK_LABELS_FA.get(str(rank_code or "").strip(), str(rank_code or "—"))


def _iter_ta_course_rows(lms: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    completions = lms.get("ta_course_completions")
    if isinstance(completions, dict):
        for code, info in completions.items():
            if isinstance(info, dict):
                rows.append({
                    "course_code": str(code),
                    "pass_count": _safe_int(info.get("pass_count")),
                    "last_term": info.get("last_term"),
                })
            else:
                rows.append({
                    "course_code": str(code),
                    "pass_count": _safe_int(info),
                })

    passes_map = lms.get("ta_course_passes")
    if isinstance(passes_map, dict):
        for code, count in passes_map.items():
            rows.append({
                "course_code": str(code),
                "pass_count": _safe_int(count),
            })

    records = lms.get("ta_course_records")
    if isinstance(records, list):
        for rec in records:
            if not isinstance(rec, dict):
                continue
            rows.append({
                "course_code": str(rec.get("course_code") or rec.get("code") or ""),
                "pass_count": _safe_int(rec.get("pass_count") or rec.get("passes")),
                "course_name": rec.get("course_name"),
            })

    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("course_code") or "").strip()
        if not code:
            continue
        prev = merged.get(code)
        if prev is None or _safe_int(row.get("pass_count")) > _safe_int(prev.get("pass_count")):
            merged[code] = row
    return list(merged.values())


def _pick_qualifying_course(
    lms: dict[str, Any],
    *,
    course_code: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    rows = _iter_ta_course_rows(lms)
    if course_code:
        code = str(course_code).strip()
        for row in rows:
            if str(row.get("course_code")) == code and _safe_int(row.get("pass_count")) >= REQUIRED_PASSES:
                return row
        return None
    for row in rows:
        if _safe_int(row.get("pass_count")) >= REQUIRED_PASSES:
            return row
    return None


def _rejection_map(extra: dict[str, Any]) -> dict[str, bool]:
    raw = extra.get("ta_upgrade_rejected_for_course")
    if isinstance(raw, dict):
        return {str(k): bool(v) for k, v in raw.items()}
    return {}


def is_auto_blocked_for_course(extra: dict[str, Any], course_code: str) -> bool:
    return bool(_rejection_map(extra).get(str(course_code)))


def mark_manual_retry_eligible(student: Student, course_code: str) -> None:
    extra = _as_mapping(student.extra_data)
    rejected = _rejection_map(extra)
    code = str(course_code or "").strip()
    if code:
        rejected[code] = True
        extra["ta_upgrade_rejected_for_course"] = rejected
        extra["ta_upgrade_manual_retry_course"] = code
    student.extra_data = extra
    flag_modified(student, "extra_data")


def mark_upgrade_applied(student: Student, course_code: str) -> None:
    extra = _as_mapping(student.extra_data)
    code = str(course_code or "").strip()
    rejected = _rejection_map(extra)
    if code and code in rejected:
        rejected.pop(code, None)
        extra["ta_upgrade_rejected_for_course"] = rejected
    extra["ta_upgrade_applied_at"] = datetime.now(timezone.utc).isoformat()
    if code:
        applied = _as_mapping(extra.get("ta_upgrade_applied_courses"))
        applied[code] = extra["ta_upgrade_applied_at"]
        extra["ta_upgrade_applied_courses"] = applied
    student.extra_data = extra
    flag_modified(student, "extra_data")


def evaluate_ta_assistant_faculty_eligibility(
    student: Student,
    user: Optional[User] = None,
    *,
    course_code: Optional[str] = None,
    manual_retry: bool = False,
) -> dict[str, Any]:
    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    rank = _resolve_rank(student, user)
    already_assistant = rank in ASSISTANT_RANK_CODES or extra.get("assistant_faculty_rank") is True

    qualifying = _pick_qualifying_course(lms, course_code=course_code)
    passes_ok = qualifying is not None
    source_code = str(qualifying.get("course_code")) if qualifying else (course_code or "")
    source_name = (
        qualifying.get("course_name")
        if qualifying and qualifying.get("course_name")
        else _course_label(source_code)
    )
    pass_count = _safe_int(qualifying.get("pass_count")) if qualifying else 0

    auto_blocked = (
        not manual_retry
        and source_code
        and is_auto_blocked_for_course(extra, source_code)
    )

    return {
        "eligible_for_review": passes_ok and not auto_blocked,
        "already_assistant_faculty": already_assistant,
        "passes_ok": passes_ok,
        "auto_blocked": auto_blocked,
        "required_passes": REQUIRED_PASSES,
        "ta_pass_count": pass_count,
        "course_code": source_code or None,
        "course_name": source_name or None,
        "course_name_fa": source_name or None,
        "current_rank": rank,
        "current_analytic_rank_fa": _rank_label_fa(rank),
        "manual_retry_available": bool(source_code and is_auto_blocked_for_course(extra, source_code)),
        "ta_upgrade_summary_fa": (
            f"درس: {source_name or '—'}؛ "
            f"تعداد پاس موفق TA: {pass_count}/{REQUIRED_PASSES}؛ "
            f"رتبه فعلی: {_rank_label_fa(rank)}"
        ),
        "student_portal_message_fa": (
            ALREADY_ASSISTANT_MESSAGE_FA if already_assistant else REJECT_MESSAGE_FA
        ),
    }


async def build_ta_assistant_faculty_context(
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

    merged = _as_mapping(existing)
    course_code = merged.get("course_code")
    manual_retry = bool(merged.get("manual_retry"))

    ev = evaluate_ta_assistant_faculty_eligibility(
        student,
        user,
        course_code=str(course_code) if course_code else None,
        manual_retry=manual_retry,
    )
    ctx = {**ev}
    if user and user.full_name_fa:
        ctx["student_name_fa"] = user.full_name_fa
    if student.student_code:
        ctx["student_code_display"] = student.student_code
    return {**merged, **ctx}


async def persist_ta_assistant_faculty_context(
    db: AsyncSession,
    instance: ProcessInstance,
    extra_fields: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ctx = await build_ta_assistant_faculty_context(
        db,
        instance.student_id,
        {**_as_mapping(instance.context_data), **_as_mapping(extra_fields)},
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()
    return ctx


async def propagate_on_start(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    actor_id: uuid.UUID | None = None,
) -> Optional[str]:
    """Auto-advance from auto_or_manual_trigger via system triggers."""
    from app.core.engine import InvalidTransitionError, StateMachineEngine

    if instance.process_code != "ta_to_assistant_faculty":
        return None
    if instance.current_state_code != "auto_or_manual_trigger":
        return None
    if instance.is_completed or instance.is_cancelled:
        return None

    ctx = await persist_ta_assistant_faculty_context(db, instance)
    if ctx.get("already_assistant_faculty"):
        trigger = "already_has_rank"
    elif not ctx.get("eligible_for_review") and not ctx.get("manual_retry"):
        logger.info(
            "ta_to_assistant_faculty start skipped: not eligible instance=%s",
            instance.id,
        )
        return instance.current_state_code
    else:
        trigger = "request_sent"

    engine = StateMachineEngine(db)
    aid = actor_id or SYSTEM_ACTOR_ID
    try:
        res = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event=trigger,
            actor_id=aid,
            actor_role="system",
            payload={},
        )
        if res.success:
            return res.to_state
    except InvalidTransitionError as exc:
        logger.warning("ta_to_assistant_faculty propagate_on_start failed: %s", exc)
    return None


def _resolve_track_for_course(
    student: Student,
    lms: dict[str, Any],
    course_code: str,
    user: User | None = None,
) -> str | None:
    code = str(course_code or "").strip()
    if not code:
        return None
    tracks_map = lms.get("ta_course_tracks")
    if isinstance(tracks_map, dict) and tracks_map.get(code):
        return str(tracks_map[code]).strip() or None
    active = get_active_ta_tracks(student)
    if len(active) == 1:
        return active[0]
    if active:
        return active[0]
    if user and isinstance(user.profile_meta, dict):
        profile_tracks = user.profile_meta.get("course_committee_tracks") or []
        if isinstance(profile_tracks, list) and profile_tracks:
            return str(profile_tracks[0]).strip() or None
    return None


def _resolve_member_name(student: Student, user: User | None) -> str:
    if user and (user.full_name_fa or "").strip():
        return str(user.full_name_fa).strip()
    return (student.student_code or "").strip()


async def apply_instructor_roster_upgrade(
    db: AsyncSession,
    student: Student,
    *,
    course_code: str,
    user: User | None = None,
) -> None:
    """پس از اتمام موفق فرایند ۴۹ — حذف از کمک‌مدرسین و افزودن به مدرسین."""
    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    track_code = _resolve_track_for_course(student, lms, course_code, user=user)
    if not track_code:
        logger.warning(
            "apply_instructor_roster_upgrade: no track for student=%s course=%s",
            student.id,
            course_code,
        )
        return
    name_fa = _resolve_member_name(student, user)
    if not name_fa:
        return
    await promote_ta_to_instructor_on_roster(
        db,
        track=track_code,
        name_fa=name_fa,
        user=user,
    )
    if user and course_code:
        meta = dict(user.profile_meta or {})
        merge_course_grants(meta, "instructor", [course_code])
        user.profile_meta = meta
        flag_modified(user, "profile_meta")


async def chain_after_transition(
    db: AsyncSession,
    instance: ProcessInstance,
    to_state: str,
) -> None:
    if instance.process_code != "ta_to_assistant_faculty":
        return
    stmt = select(Student).where(Student.id == instance.student_id)
    student = (await db.execute(stmt)).scalars().first()
    if not student:
        return
    ctx = _as_mapping(instance.context_data)
    course_code = str(ctx.get("course_code") or "")
    if to_state == "supervision_rejected" and course_code:
        mark_manual_retry_eligible(student, course_code)
        ctx["student_portal_message_fa"] = REJECT_MESSAGE_FA
        instance.context_data = ctx
        flag_modified(instance, "context_data")
    elif to_state == "upgrade_applied" and course_code:
        mark_upgrade_applied(student, course_code)
        user: User | None = None
        if student.user_id:
            user = (await db.execute(select(User).where(User.id == student.user_id))).scalars().first()
        await apply_instructor_roster_upgrade(
            db,
            student,
            course_code=course_code,
            user=user,
        )
        ctx["student_portal_message_fa"] = UPGRADE_SUCCESS_HINT_FA
        instance.context_data = ctx
        flag_modified(instance, "context_data")
    elif to_state == "already_assistant":
        ctx["student_portal_message_fa"] = ALREADY_ASSISTANT_MESSAGE_FA
        instance.context_data = ctx
        flag_modified(instance, "context_data")
    await db.flush()


async def scan_ta_eligible_for_upgrade(
    db: AsyncSession,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """SOP step 1 — end-of-term scan for TA with 2+ passes in one course."""
    _ = today or date.today()
    out: list[dict[str, Any]] = []
    stmt = select(Student).where(Student.is_sample_data.is_(False))
    students = list((await db.execute(stmt)).scalars().all())

    for student in students:
        extra = _as_mapping(student.extra_data)
        lms = _as_mapping(extra.get("lms"))
        if not lms.get("end_of_term_ta_evaluation_done") and not _iter_ta_course_rows(lms):
            continue
        qualifying = _pick_qualifying_course(lms)
        if not qualifying:
            continue
        course_code = str(qualifying.get("course_code") or "")
        if not course_code or is_auto_blocked_for_course(extra, course_code):
            continue
        out.append({
            "student_id": student.id,
            "course_code": course_code,
            "pass_count": _safe_int(qualifying.get("pass_count")),
            "term": lms.get("ta_evaluation_term") or str(_.year),
        })
    return out
