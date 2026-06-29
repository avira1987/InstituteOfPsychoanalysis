"""سرویس فرایند ۶۳ — خاتمه دروس تکنیک: تمرین مهارت‌ها."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student

logger = logging.getLogger(__name__)

PROCESS_CODE = "skills_course_completion"

PARTICIPATION_MAX = 10
ATTENDANCE_MAX = 8
ATTENDANCE_PENALTY = 2
PASS_THRESHOLD = 74
TOTAL_MAX = 100

PRACTICAL_MAX_NORMAL = 60
PRACTICAL_MAX_SKILLS_4 = 42
TEST_MAX_NORMAL = 22
TEST_MAX_SKILLS_4 = 40

VARIANT_NORMAL = "normal"
VARIANT_SKILLS_4 = "skills_4"


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_skills_4_course(course_code: str = "", course_name: str = "") -> bool:
    text = f"{course_code} {course_name}".lower()
    if "skills_4" in text or "مهارت‌های ۴" in text or "مهارتهای ۴" in text:
        return True
    if re.search(r"مهارت[^\d]*۴", f"{course_code} {course_name}"):
        return True
    return False


def resolve_skills_variant(course_code: str = "", course_name: str = "", ctx: Optional[dict] = None) -> str:
    ctx = ctx or {}
    explicit = str(ctx.get("skills_variant") or "").strip().lower()
    if explicit in (VARIANT_SKILLS_4, VARIANT_NORMAL):
        return explicit
    return VARIANT_SKILLS_4 if is_skills_4_course(course_code, course_name) else VARIANT_NORMAL


def practical_max(variant: str) -> int:
    return PRACTICAL_MAX_SKILLS_4 if variant == VARIANT_SKILLS_4 else PRACTICAL_MAX_NORMAL


def max_test_score(variant: str) -> int:
    return TEST_MAX_SKILLS_4 if variant == VARIANT_SKILLS_4 else TEST_MAX_NORMAL


def compute_attendance_score(absence_count: int) -> int:
    try:
        n = int(absence_count or 0)
    except (TypeError, ValueError):
        n = 0
    return max(0, ATTENDANCE_MAX - n * ATTENDANCE_PENALTY)


def is_incomplete_row(row: dict[str, Any]) -> bool:
    if row.get("incomplete") is True:
        return True
    if row.get("session_17_absent") is True or row.get("session_18_absent") is True:
        return True
    if row.get("practical_absent") is True or row.get("test_absent") is True:
        return True
    return False


def compute_total_score(
    participation: Any,
    practical: Any,
    test: Any,
    attendance: Any,
    *,
    incomplete: bool = False,
) -> Optional[int]:
    if incomplete:
        return None
    try:
        p = float(participation or 0)
        pr = float(practical or 0)
        t = float(test or 0)
        a = float(attendance or 0)
    except (TypeError, ValueError):
        return None
    total = p + pr + t + a
    return int(min(TOTAL_MAX, max(0, round(total))))


def label_pass_fail(total: Optional[int], *, incomplete: bool = False) -> str:
    if incomplete:
        return "I"
    if total is None:
        return "—"
    if total >= PASS_THRESHOLD:
        return "PASS"
    return "FAIL"


def enrich_grade_row(row: dict[str, Any], variant: str, absence_count: int = 0) -> dict[str, Any]:
    merged = dict(row)
    incomplete = is_incomplete_row(merged)
    attendance = merged.get("attendance_score")
    if attendance in (None, ""):
        attendance = compute_attendance_score(
            merged.get("absence_count") if merged.get("absence_count") is not None else absence_count,
        )
        merged["attendance_score"] = attendance
    total = compute_total_score(
        merged.get("participation_score"),
        merged.get("practical_score"),
        merged.get("test_score"),
        attendance,
        incomplete=incomplete,
    )
    merged["incomplete"] = incomplete
    merged["total_score"] = total
    merged["pass_fail"] = label_pass_fail(total, incomplete=incomplete)
    merged["grade"] = total if total is not None else merged.get("grade")
    return merged


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
    """همگام‌سازی context روی همه instanceهای فعال یک درس."""
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
        inst_code = course_code_from_context(ctx)
        if inst_code != course_code:
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


async def apply_grades_to_student_lms(
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
        merged = {**row}
        pf = grade_row.get("pass_fail")
        total = grade_row.get("total_score")
        if pf == "I" or grade_row.get("incomplete"):
            merged["status_fa"] = "ناقص (I)"
            merged["incomplete"] = True
        elif total is not None:
            merged["grade"] = total
            merged["status_fa"] = pf or label_pass_fail(int(total))
            merged["grades_locked"] = True
            merged["grade_locked"] = True
        updated.append(merged)
        matched = True
    if not matched and grade_row.get("total_score") is not None:
        updated.append({
            "code": course_code,
            "course_code": course_code,
            "grade": grade_row.get("total_score"),
            "status_fa": grade_row.get("pass_fail"),
            "grades_locked": True,
        })
    lms["enrolled_courses"] = updated
    extra["lms"] = lms
    student.extra_data = extra
    flag_modified(student, "extra_data")


async def fan_out_lms_grades(db: AsyncSession, course_code: str, students_grades: list) -> None:
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
        await apply_grades_to_student_lms(db, uid, course_code, row)


async def on_session_17_submit(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
) -> str:
    ctx = _as_mapping(instance.context_data)
    merged = {**ctx, **(context or {})}
    course_code = course_code_from_context(merged)
    variant = resolve_skills_variant(course_code, str(merged.get("course_name") or ""), merged)
    rows_in = merged.get("students_grades") or []
    enriched = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        if (row.get("role") or "student") == "teaching_assistant":
            continue
        enriched.append(enrich_grade_row(row, variant))
    has_ta = merged.get("course_has_ta")
    if has_ta is None and course_code:
        has_ta = await get_course_roster_ta_flag(db, course_code)
    patch = {
        "students_grades": enriched,
        "skills_variant": variant,
        "course_code": course_code,
        "course_has_ta": bool(has_ta),
        "session_17_submitted_at": _utcnow_iso(),
        "session_17_submitted_before_sla": merged.get("session_17_submitted_before_sla", True),
    }
    instance.context_data = {**merged, **patch}
    flag_modified(instance, "context_data")
    await fan_out_context(db, course_code, patch, exclude_instance_id=instance.id)
    return "session_17_recorded"


async def on_session_18_submit(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
) -> str:
    ctx = _as_mapping(instance.context_data)
    merged = {**ctx, **(context or {})}
    course_code = course_code_from_context(merged)
    variant = resolve_skills_variant(course_code, str(merged.get("course_name") or ""), merged)
    existing = {str(r.get("student_id")): dict(r) for r in (ctx.get("students_grades") or []) if isinstance(r, dict)}
    rows_in = merged.get("students_grades") or []
    enriched = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        if (row.get("role") or "student") == "teaching_assistant":
            continue
        sid = str(row.get("student_id") or "")
        base = {**existing.get(sid, {}), **row}
        absence = base.get("absence_count", 0)
        enriched.append(enrich_grade_row(base, variant, absence_count=absence))
    patch = {
        "students_grades": enriched,
        "session_18_submitted_at": _utcnow_iso(),
        "test_exam_id": merged.get("test_exam_id"),
    }
    instance.context_data = {**merged, **patch}
    flag_modified(instance, "context_data")
    await fan_out_context(db, course_code, patch, exclude_instance_id=instance.id)
    return "session_18_recorded"


async def auto_compute_grades(
    db: AsyncSession,
    instance: ProcessInstance,
) -> str:
    ctx = _as_mapping(instance.context_data)
    course_code = course_code_from_context(ctx)
    variant = resolve_skills_variant(course_code, str(ctx.get("course_name") or ""), ctx)
    rows = []
    for row in ctx.get("students_grades") or []:
        if not isinstance(row, dict):
            continue
        if (row.get("role") or "student") == "teaching_assistant":
            continue
        rows.append(enrich_grade_row(row, variant, absence_count=row.get("absence_count") or 0))
    has_ta = ctx.get("course_has_ta")
    if has_ta is None and course_code:
        has_ta = await get_course_roster_ta_flag(db, course_code)
    patch = {
        "students_grades": rows,
        "grades_computed_at": _utcnow_iso(),
        "course_has_ta": bool(has_ta),
    }
    instance.context_data = {**ctx, **patch}
    flag_modified(instance, "context_data")
    await fan_out_context(db, course_code, patch, exclude_instance_id=instance.id)
    return "grades_computed"


async def on_ta_grades_submit(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
) -> str:
    ctx = _as_mapping(instance.context_data)
    merged = {**ctx, **(context or {})}
    course_code = course_code_from_context(merged)
    try:
        att = float(merged.get("ta_attendance_score") or 0)
        duties = float(merged.get("ta_duties_score") or 0)
        ta_total = att + duties
    except (TypeError, ValueError):
        ta_total = 0
    patch = {
        "ta_attendance_score": merged.get("ta_attendance_score"),
        "ta_duties_score": merged.get("ta_duties_score"),
        "ta_total_score": ta_total,
        "ta_pass_fail": "PASS" if ta_total >= PASS_THRESHOLD else "FAIL",
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
    students_grades = merged.get("students_grades") or ctx.get("students_grades") or []
    await fan_out_lms_grades(db, course_code, students_grades)
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
    variant = resolve_skills_variant(code, str(ctx.get("course_name") or ""), ctx)
    prefilled = {
        str(r.get("student_id")): r
        for r in (ctx.get("students_grades") or [])
        if isinstance(r, dict) and r.get("student_id")
    }
    rows = []
    for entry in roster:
        sid = str(entry.get("student_id") or "")
        base = {**entry, **prefilled.get(sid, {})}
        base["student_name"] = base.get("name_fa") or base.get("student_name") or sid
        rows.append(enrich_grade_row(base, variant, absence_count=base.get("absence_count") or 0))
    ta_rows = [r for r in roster if (r.get("role") or "") == "teaching_assistant"]
    return {
        "course_code": code,
        "skills_variant": variant,
        "practical_max": practical_max(variant),
        "test_max": max_test_score(variant),
        "course_has_ta": course_has_ta_from_roster(roster),
        "ta_name": ta_rows[0].get("name_fa") if ta_rows else None,
        "students_grades": rows,
        "current_state": instance.current_state_code if instance else None,
    }


async def dispatch_skills_session_calendar(
    db: AsyncSession,
    student: Student,
    course_code: str,
    session_index: int,
    session_date_iso: str,
) -> Optional[dict]:
    """ماشه تقویمی جلسه ۱۷/۱۸ برای skills_course_completion."""
    from app.core.engine import StateMachineEngine
    from app.services.process_scheduler import SYSTEM_ACTOR_ID, _start_process_if_absent

    if session_index not in (17, 18):
        return None
    engine = StateMachineEngine(db)
    fp = f"skills_cc:{course_code}:s{session_index}"
    extra = _as_mapping(student.extra_data)
    fps = _as_mapping(extra.get("scheduler_fingerprints"))
    if fps.get(fp) == session_date_iso:
        return None

    initial_context = {
        "course_code": course_code,
        "course_name": course_code,
        "session_index": session_index,
        "skills_variant": VARIANT_SKILLS_4 if is_skills_4_course(course_code) else VARIANT_NORMAL,
    }
    hit = await _start_process_if_absent(
        db,
        student_id=student.id,
        process_code=PROCESS_CODE,
        initial_context=initial_context,
        fingerprint_key=fp,
        fingerprint_val=session_date_iso,
    )
    if not hit:
        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.process_code == PROCESS_CODE,
            ProcessInstance.is_completed.is_(False),
        )
        inst = (await db.execute(stmt)).scalars().first()
        if inst:
            hit = {"instance_id": str(inst.id), "student_id": str(student.id), "process_code": PROCESS_CODE}
    if not hit:
        return None

    trigger = "calendar_session_17_reached" if session_index == 17 else "calendar_session_18_reached"
    try:
        await engine.execute_transition(
            instance_id=uuid.UUID(hit["instance_id"]),
            trigger_event=trigger,
            actor_id=SYSTEM_ACTOR_ID,
            actor_role="system",
        )
    except Exception as e:
        logger.debug("skills calendar transition %s: %s", trigger, e)
        return None
    return {**hit, "trigger": trigger, "session_index": session_index}
