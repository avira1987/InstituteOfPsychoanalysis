"""Business logic for process 60 — return_to_full_education."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student
from app.services.attendance_service import AttendanceService
from app.services.financial_program_defaults_service import get_effective_financial_program_defaults

logger = logging.getLogger(__name__)


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


def _parse_iso_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def _course_type_label(course_type: str) -> str:
    if course_type == "comprehensive":
        return "دوره جامع"
    if course_type == "introductory":
        return "دوره آشنایی"
    return course_type or "—"


def _is_intern_student(extra: dict[str, Any]) -> bool:
    if extra.get("is_intern") is True:
        return True
    if extra.get("internship_started") is True:
        return True
    lms = _as_mapping(extra.get("lms"))
    if lms.get("is_intern") is True:
        return True
    return False


def validate_weekly_sessions(course_type: str, weekly_sessions: int) -> Optional[str]:
    if course_type == "comprehensive":
        if weekly_sessions != 2:
            return "در دوره جامع باید دقیقاً ۲ جلسه در هفته انتخاب شود."
    elif course_type == "introductory":
        if weekly_sessions not in (1, 2):
            return "در دوره آشنایی باید ۱ یا ۲ جلسه در هفته انتخاب شود."
    return None


async def build_return_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Populate instance context for UI and branching."""
    stmt = select(Student).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        return {}

    extra = _as_mapping(student.extra_data)
    course_type = str(student.course_type or extra.get("course_type") or "introductory")
    is_intern = _is_intern_student(extra)

    hours_hint = "۲ ساعت در هفته (ثابت)" if course_type == "comprehensive" else "۱ تا ۲ ساعت در هفته"

    ctx = {
        "course_type": course_type,
        "course_type_display_fa": _course_type_label(course_type),
        "is_intern": is_intern,
        "is_intern_display_fa": "انترن" if is_intern else "غیر انترن",
        "weekly_hours_hint_fa": hours_hint,
        "supervision_hours_hint_fa": "۱ ساعت در هفته (انترن)" if is_intern else "—",
        "student_name_fa": extra.get("name_fa") or student.student_code or str(student.id),
    }
    merged = {**_as_mapping(existing), **ctx}
    return merged


async def propagate_on_start(
    db: AsyncSession,
    instance: ProcessInstance,
) -> None:
    ctx = await build_return_context(db, instance.student_id, _as_mapping(instance.context_data))
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()


async def apply_24h_bump(first: date, student_id: uuid.UUID, db: AsyncSession) -> date:
    """Bump first session date until 24h rule satisfied."""
    attendance = AttendanceService(db)
    today = datetime.now(timezone.utc).date()
    candidate = first
    if candidate <= today:
        candidate = today + timedelta(days=1)
    for _ in range(8):
        hours = await attendance.get_hours_until_first_slot(student_id)
        if hours >= 24:
            return candidate
        candidate = candidate + timedelta(days=7)
    return candidate


async def branch_after_therapy_payment(
    db: AsyncSession,
    engine: Any,
    instance: ProcessInstance,
    actor_id: uuid.UUID,
) -> str:
    """Auto-advance therapy_completed → supervisor_selection or registration_unlocked."""
    ctx = _as_mapping(instance.context_data)
    trigger = "needs_supervisor" if ctx.get("is_intern") else "skip_supervisor"
    res = await engine.execute_transition(
        instance_id=instance.id,
        trigger_event=trigger,
        actor_id=actor_id,
        actor_role="system",
        payload={},
    )
    if not res.success:
        logger.error(
            "return_to_full_education branch after therapy failed instance=%s err=%s",
            instance.id,
            res.error,
        )
        return f"branch_failed:{res.error}"
    return f"branched:{trigger}"


async def finalize_registration_unlock(
    db: AsyncSession,
    engine: Any,
    instance: ProcessInstance,
    actor_id: uuid.UUID,
) -> str:
    """registration_unlocked → return_complete."""
    ctx = _as_mapping(instance.context_data)
    ctx["registration_unlocked_at"] = datetime.now(timezone.utc).isoformat()
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()

    res = await engine.execute_transition(
        instance_id=instance.id,
        trigger_event="finalize_return",
        actor_id=actor_id,
        actor_role="system",
        payload={},
    )
    if not res.success:
        logger.error(
            "return_to_full_education finalize failed instance=%s err=%s",
            instance.id,
            res.error,
        )
        return f"finalize_failed:{res.error}"
    return "finalized"


async def therapy_payment_fee_rial(db: AsyncSession, ctx: dict[str, Any]) -> int:
    if ctx.get("therapy_payment_amount_rial") is not None:
        try:
            return int(ctx["therapy_payment_amount_rial"])
        except (TypeError, ValueError):
            pass
    fd = await get_effective_financial_program_defaults(db)
    return int(fd["start_therapy_first_session_fee_rial"])


async def supervision_payment_fee_rial(db: AsyncSession, ctx: dict[str, Any]) -> int:
    if ctx.get("supervision_payment_amount_rial") is not None:
        try:
            return int(ctx["supervision_payment_amount_rial"])
        except (TypeError, ValueError):
            pass
    fd = await get_effective_financial_program_defaults(db)
    return int(fd.get("supervision_first_session_fee_rial") or fd["start_therapy_first_session_fee_rial"])
