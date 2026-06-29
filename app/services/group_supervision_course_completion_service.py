"""سرویس فرایند ۶۲ — خاتمه هر درس سوپرویژن گروهی."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student

logger = logging.getLogger(__name__)

PROCESS_CODE = "group_supervision_course_completion"

HOURS_PER_PASS = 33.3333
GROUP_SUPERVISION_HOURS_CAP = 100.0
ATTENDANCE_MAX = 8
ATTENDANCE_PENALTY = 2
TA_PASS_THRESHOLD = 74


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt_hours_display(hours: float) -> str:
    return f"{hours:.1f}"


def compute_attendance_score(absence_count: int) -> int:
    try:
        n = int(absence_count or 0)
    except (TypeError, ValueError):
        n = 0
    return max(0, ATTENDANCE_MAX - n * ATTENDANCE_PENALTY)


def normalize_pass_fail(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if raw in ("PASS", "P", "قبول", "پاس"):
        return "PASS"
    if raw in ("FAIL", "F", "رد", "مردود"):
        return "FAIL"
    return raw or "—"


def compute_ta_total(attendance: Any, duties: Any) -> float:
    try:
        return float(attendance or 0) + float(duties or 0)
    except (TypeError, ValueError):
        return 0.0


def label_ta_pass_fail(total: float) -> str:
    return "PASS" if total >= TA_PASS_THRESHOLD else "FAIL"


def group_supervision_hours_total(extra: dict[str, Any]) -> float:
    lms = _as_mapping(extra.get("lms"))
    try:
        return float(lms.get("group_supervision_hours") or 0)
    except (TypeError, ValueError):
        return 0.0


def course_code_from_context(ctx: dict[str, Any]) -> str:
    return str(
        ctx.get("course_code")
        or ctx.get("course_id")
        or ctx.get("lesson_name")
        or ctx.get("course_name")
        or "",
    ).strip()


def course_has_ta_from_roster(roster: list[dict[str, Any]]) -> bool:
    return any((r.get("role") or "student") == "teaching_assistant" for r in roster)


async def get_course_roster_ta_flag(db: AsyncSession, course_code: str) -> bool:
    from app.services.instructor_course_roster_service import get_course_roster

    roster = await get_course_roster(db, course_code)
    return course_has_ta_from_roster(roster)


def enrich_pass_fail_row(row: dict[str, Any], current_hours: float = 0.0) -> dict[str, Any]:
    merged = dict(row)
    pf = normalize_pass_fail(merged.get("pass_fail") or merged.get("grade"))
    merged["pass_fail"] = pf
    merged["grade"] = pf
    if pf == "PASS":
        merged["hours_added"] = HOURS_PER_PASS
        merged["hours_after"] = min(GROUP_SUPERVISION_HOURS_CAP, current_hours + HOURS_PER_PASS)
    else:
        merged["hours_added"] = 0.0
        merged["hours_after"] = current_hours
    return merged


def _merge_students_grades(existing: list, incoming: list) -> list:
    by_id: dict[str, dict] = {}
    for row in existing or []:
        if isinstance(row, dict) and row.get("student_id"):
            by_id[str(row["student_id"])] = dict(row)
    for row in incoming or []:
        if not isinstance(row, dict) or not row.get("student_id"):
            continue
        sid = str(row["student_id"])
        by_id[sid] = {**by_id.get(sid, {}), **row}
    return list(by_id.values())


async def fan_out_context(
    db: AsyncSession,
    course_code: str,
    patch: dict[str, Any],
    *,
    exclude_instance_id: Optional[uuid.UUID] = None,
) -> int:
    if not course_code:
        return 0
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == PROCESS_CODE,
        ProcessInstance.is_completed.is_(False),
    )
    rows = list((await db.execute(stmt)).scalars().all())
    count = 0
    for inst in rows:
        if exclude_instance_id and inst.id == exclude_instance_id:
            continue
        ctx = _as_mapping(inst.context_data)
        if course_code_from_context(ctx) != course_code:
            continue
        merged = {**ctx, **patch}
        if patch.get("students_grades"):
            merged["students_grades"] = _merge_students_grades(
                ctx.get("students_grades") or [],
                patch.get("students_grades") or [],
            )
        inst.context_data = merged
        flag_modified(inst, "context_data")
        count += 1
    return count


async def apply_pass_fail_to_student_lms(
    db: AsyncSession,
    student_id: uuid.UUID,
    course_code: str,
    grade_row: dict[str, Any],
) -> None:
    student = await db.get(Student, student_id)
    if not student:
        return
    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    pf = normalize_pass_fail(grade_row.get("pass_fail"))
    hours_before = group_supervision_hours_total(extra)
    hours_added = float(grade_row.get("hours_added") or 0)
    hours_after = min(GROUP_SUPERVISION_HOURS_CAP, hours_before + hours_added)

    gs_root = dict(_as_mapping(lms.get("group_supervision")))
    gs_root[course_code] = {
        "pass_fail": pf,
        "hours_added": hours_added,
        "completed_at": _utcnow_iso(),
        "status_fa": "پاس" if pf == "PASS" else "رد",
    }
    lms["group_supervision"] = gs_root
    if pf == "PASS" and hours_added > 0:
        lms["group_supervision_hours"] = hours_after

    enrolled = list(lms.get("enrolled_courses") or [])
    updated: list[Any] = []
    matched = False
    for row in enrolled:
        if not isinstance(row, dict):
            updated.append(row)
            continue
        code = str(row.get("code") or row.get("course_code") or row.get("course_name") or "")
        if code and code != course_code and course_code not in code:
            updated.append(row)
            continue
        merged = {**row, "status_fa": "پاس" if pf == "PASS" else "رد", "pass_fail": pf}
        if pf == "PASS":
            merged["grades_locked"] = True
        updated.append(merged)
        matched = True
    if not matched:
        updated.append({
            "code": course_code,
            "course_code": course_code,
            "status_fa": "پاس" if pf == "PASS" else "رد",
            "pass_fail": pf,
        })
    lms["enrolled_courses"] = updated
    extra["lms"] = lms
    student.extra_data = extra
    flag_modified(student, "extra_data")


async def fan_out_lms_pass_fail(db: AsyncSession, course_code: str, students_grades: list) -> None:
    for row in students_grades or []:
        if not isinstance(row, dict):
            continue
        sid = row.get("student_id")
        if not sid or str(sid).startswith("ta:"):
            continue
        try:
            uid = uuid.UUID(str(sid))
        except ValueError:
            continue
        await apply_pass_fail_to_student_lms(db, uid, course_code, row)


async def chain_hours_applied(db: AsyncSession, instance: ProcessInstance) -> None:
    """پس از pass_fail_applied، انتقال خودکار به TA یا ارزیابی کیفی."""
    from app.core.engine import StateMachineEngine, InvalidTransitionError
    from app.services.process_scheduler import SYSTEM_ACTOR_ID

    if instance.current_state_code != "pass_fail_applied":
        return
    engine = StateMachineEngine(db)
    try:
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="hours_applied",
            actor_id=SYSTEM_ACTOR_ID,
            actor_role="system",
        )
    except InvalidTransitionError as e:
        logger.debug("group_supervision hours_applied skipped: %s", e)


async def on_pass_fail_submit(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
) -> str:
    ctx = _as_mapping(instance.context_data)
    merged = {**ctx, **(context or {})}
    course_code = course_code_from_context(merged)
    rows_in = merged.get("students_grades") or []
    enriched = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        if (row.get("role") or "student") == "teaching_assistant":
            continue
        sid = row.get("student_id")
        current_hours = 0.0
        if sid:
            try:
                st = await db.get(Student, uuid.UUID(str(sid)))
                if st:
                    current_hours = group_supervision_hours_total(_as_mapping(st.extra_data))
            except ValueError:
                pass
        enriched.append(enrich_pass_fail_row(row, current_hours))
    has_ta = merged.get("course_has_ta")
    if has_ta is None and course_code:
        has_ta = await get_course_roster_ta_flag(db, course_code)
    patch = {
        "students_grades": enriched,
        "course_code": course_code,
        "course_has_ta": bool(has_ta),
        "pass_fail_submitted_at": _utcnow_iso(),
        "pass_fail_submitted_before_sla": merged.get("pass_fail_submitted_before_sla", True),
    }
    instance.context_data = {**merged, **patch}
    flag_modified(instance, "context_data")
    await fan_out_context(db, course_code, patch, exclude_instance_id=instance.id)
    await fan_out_lms_pass_fail(db, course_code, enriched)
    await db.flush()
    await chain_hours_applied(db, instance)
    return "pass_fail_recorded"


async def on_ta_grades_submit(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
) -> str:
    ctx = _as_mapping(instance.context_data)
    merged = {**ctx, **(context or {})}
    course_code = course_code_from_context(merged)
    att = merged.get("ta_attendance_score")
    if att in (None, ""):
        att = compute_attendance_score(int(merged.get("ta_absence_count") or 0))
    ta_total = compute_ta_total(att, merged.get("ta_duties_score"))
    patch = {
        "ta_attendance_score": att,
        "ta_duties_score": merged.get("ta_duties_score"),
        "ta_total_score": ta_total,
        "ta_pass_fail": label_ta_pass_fail(ta_total),
        "ta_grades_submitted_at": _utcnow_iso(),
    }
    instance.context_data = {**merged, **patch}
    flag_modified(instance, "context_data")
    await fan_out_context(db, course_code, patch, exclude_instance_id=instance.id)
    return "ta_grades_recorded"


async def on_qualitative_submit(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
) -> str:
    ctx = _as_mapping(instance.context_data)
    merged = {**ctx, **(context or {})}
    course_code = course_code_from_context(merged)
    patch = {
        "qualitative_submitted_at": _utcnow_iso(),
        "qualitative_submitted_before_sla": merged.get("qualitative_submitted_before_sla", True),
        "q7_has_positive": merged.get("q7_has_positive"),
        "q8_has_negative": merged.get("q8_has_negative"),
    }
    instance.context_data = {**merged, **patch}
    flag_modified(instance, "context_data")
    await fan_out_context(db, course_code, patch, exclude_instance_id=instance.id)
    return "qualitative_recorded"


async def get_grades_preview(
    db: AsyncSession,
    course_code: str,
    *,
    instance: Optional[ProcessInstance] = None,
) -> dict[str, Any]:
    from app.services.instructor_course_roster_service import get_course_roster

    code = str(course_code or "").strip()
    roster = await get_course_roster(db, code)
    ctx = _as_mapping(instance.context_data) if instance else {}
    prefilled = {
        str(r.get("student_id")): r
        for r in (ctx.get("students_grades") or [])
        if isinstance(r, dict) and r.get("student_id")
    }
    rows = []
    for entry in roster:
        if (entry.get("role") or "student") == "teaching_assistant":
            continue
        sid = str(entry.get("student_id") or "")
        base = {**entry, **prefilled.get(sid, {})}
        base["student_name"] = base.get("name_fa") or base.get("student_name") or sid
        current_hours = 0.0
        if sid:
            try:
                st = await db.get(Student, uuid.UUID(sid))
                if st:
                    current_hours = group_supervision_hours_total(_as_mapping(st.extra_data))
            except ValueError:
                pass
        base["group_supervision_hours_before"] = current_hours
        rows.append(enrich_pass_fail_row(base, current_hours))
    ta_rows = [r for r in roster if (r.get("role") or "") == "teaching_assistant"]
    ta_absence = ta_rows[0].get("absence_count", 0) if ta_rows else 0
    return {
        "course_code": code,
        "hours_per_pass": HOURS_PER_PASS,
        "hours_per_pass_display": fmt_hours_display(HOURS_PER_PASS),
        "hours_cap": GROUP_SUPERVISION_HOURS_CAP,
        "course_has_ta": course_has_ta_from_roster(roster),
        "ta_name": ta_rows[0].get("name_fa") if ta_rows else None,
        "ta_absence_count": ta_absence,
        "ta_attendance_suggested": compute_attendance_score(ta_absence),
        "students_grades": rows,
        "current_state": instance.current_state_code if instance else None,
    }
