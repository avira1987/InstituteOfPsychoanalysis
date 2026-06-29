"""Business logic for process 59 — full_education_leave."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student

logger = logging.getLogger(__name__)

THERAPY_COORD_PHONE_FA = "02122728000 داخلی 1"
THERAPY_COORD_SMS_FA = (
    "دانشجوی گرامی به دلیل تصمیم مرخصی از کل آموزش، درصورتی که میخواهید درمان خود را "
    "ادامه دهید، درمان آموزشی شما تا زمان بازگشت به آموزش در قالب درمان عموم قرار میگیرد. "
    "لذا تا مدت 3 روز از این پیامک وقت درمان آموشی شما جهت ارائه درمان عموم برای شما "
    "محفوظ می ماند برای اخذ وقت فعلی خود در طول این 3 روز با مسئول هماهنگی ها تماس "
    f"حاصل فرمایید. شماره مسئول هماهنگی ها: {THERAPY_COORD_PHONE_FA}"
)


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _is_intern_student(extra: dict[str, Any], student: Optional[Student] = None) -> bool:
    if student is not None and student.is_intern:
        return True
    if extra.get("is_intern") is True:
        return True
    if extra.get("internship_started") is True:
        return True
    lms = _as_mapping(extra.get("lms"))
    return lms.get("is_intern") is True


def _has_active_therapist(student: Student, extra: dict[str, Any]) -> bool:
    if student.therapist_id is not None:
        return True
    if student.therapy_started:
        return True
    if extra.get("has_active_therapist") is True:
        return True
    rel = extra.get("therapy_relationship")
    return rel in ("active", "ongoing", None) and extra.get("therapy_status") != "terminated"


def _leave_terms_label(terms: Any) -> str:
    try:
        n = int(terms)
        if n == 1:
            return "یک ترم"
        if n == 2:
            return "دو ترم"
    except (TypeError, ValueError):
        pass
    return str(terms or "—")


async def build_leave_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    stmt = select(Student).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        return {}

    extra = _as_mapping(student.extra_data)
    is_intern = _is_intern_student(extra, student)
    has_therapist = _has_active_therapist(student, extra)
    merged = _as_mapping(existing)

    therapist_name = (
        merged.get("current_therapist_display")
        or extra.get("therapist_name_fa")
        or extra.get("therapist_name")
        or (str(student.therapist_id) if student.therapist_id else None)
    )

    ctx = {
        "course_type": str(student.course_type or extra.get("course_type") or "introductory"),
        "is_intern": is_intern,
        "is_intern_display_fa": "انترن" if is_intern else "غیر انترن",
        "clinical_status_display": "انترن" if is_intern else "غیر انترن",
        "has_active_therapist": has_therapist,
        "student_name_display": extra.get("name_fa") or student.student_code or str(student.id),
        "current_therapist_display": therapist_name or "—",
        "current_session_times_display": merged.get("current_session_times_display")
        or extra.get("therapy_schedule_fa")
        or "—",
        "therapy_coord_phone_fa": THERAPY_COORD_PHONE_FA,
        "therapy_coord_sms_fa": THERAPY_COORD_SMS_FA,
    }
    if merged.get("leave_terms") is not None:
        ctx["leave_terms_display"] = _leave_terms_label(merged.get("leave_terms"))
    return {**merged, **ctx}


async def propagate_on_start(db: AsyncSession, instance: ProcessInstance) -> None:
    ctx = await build_leave_context(db, instance.student_id, _as_mapping(instance.context_data))
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()


async def maybe_skip_therapist_assignment(
    db: AsyncSession,
    engine: Any,
    instance: ProcessInstance,
    actor_id: uuid.UUID,
) -> Optional[str]:
    """If student has no active therapist, auto-advance to on_leave."""
    if instance.process_code != "full_education_leave":
        return None
    if instance.current_state_code != "therapist_assignment":
        return None

    ctx = await build_leave_context(db, instance.student_id, _as_mapping(instance.context_data))
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()

    if ctx.get("has_active_therapist"):
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(days=4)
        ctx["therapist_assignment_deadline_at"] = deadline.isoformat()
        ctx["therapist_deadline_display"] = deadline.strftime("%Y-%m-%d %H:%M UTC")
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db.flush()
        return "therapist_assignment_pending"

    res = await engine.execute_transition(
        instance_id=instance.id,
        trigger_event="skip_therapist_assignment",
        actor_id=actor_id,
        actor_role="system",
        payload={},
    )
    if not res.success:
        logger.error(
            "full_education_leave skip_therapist_assignment failed instance=%s err=%s",
            instance.id,
            res.error,
        )
        return f"skip_failed:{res.error}"
    return "skipped_to_on_leave"


async def complete_leave_on_return(
    db: AsyncSession,
    engine: Any,
    student_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> str:
    """When process 60 completes, close active full_education_leave instance."""
    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == "full_education_leave",
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
    )
    result = await db.execute(stmt)
    instance = result.scalars().first()
    if not instance:
        return "no_active_full_leave"

    state = instance.current_state_code
    if state not in ("on_leave", "return_reminder_sent"):
        return f"skip_state:{state}"

    res = await engine.execute_transition(
        instance_id=instance.id,
        trigger_event="return_process_completed",
        actor_id=actor_id,
        actor_role="system",
        payload={"completed_via": "return_to_full_education"},
    )
    if not res.success:
        logger.error(
            "full_education_leave return_process_completed failed instance=%s err=%s",
            instance.id,
            res.error,
        )
        return f"complete_failed:{res.error}"
    return "full_leave_completed"


async def apply_intern_effects(db: AsyncSession, instance: ProcessInstance) -> str:
    student = (
        await db.execute(select(Student).where(Student.id == instance.student_id))
    ).scalars().first()
    if not student:
        return "student_not_found"

    extra = _as_mapping(student.extra_data)
    if not _is_intern_student(extra, student):
        return "not_intern_skipped"

    ctx = _as_mapping(instance.context_data)
    ctx["intern_full_leave_applied_at"] = datetime.now(timezone.utc).isoformat()
    instance.context_data = ctx
    flag_modified(instance, "context_data")

    prev = str(student.supervisor_id) if student.supervisor_id else None
    student.supervisor_id = None
    student.is_intern = False
    extra["intern_revoked_at"] = datetime.now(timezone.utc).isoformat()
    extra["intern_revoked_reason"] = "full_education_leave"
    extra["supervisor_released_at"] = datetime.now(timezone.utc).isoformat()
    extra["supervisor_release_reason"] = "full_education_leave"
    if prev:
        extra["previous_supervisor_id"] = prev
    student.extra_data = extra
    flag_modified(student, "extra_data")
    await db.flush()
    return "intern_effects_applied"
