"""Business logic for process 71 — upgrade_to_educational_therapist."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student
from app.services.attendance_service import AttendanceService

logger = logging.getLogger(__name__)

ET_THERAPY_HOURS_TARGET = 50
ET_SUPERVISION_HOURS_TARGET = 50


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


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


async def build_et_upgrade_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Populate instance context fields for rules and UI."""
    stmt = select(Student).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        return {}

    extra = _as_mapping(student.extra_data)
    attendance = AttendanceService(db)
    hours_info = await attendance.get_completed_hours(student.id)
    therapy_metrics = await attendance.get_therapy_completion_metrics(student.id)

    therapy_hours = _safe_float(therapy_metrics.get("therapy_hours_2x"))
    supervision_hours = _safe_float(therapy_metrics.get("supervision_hours"))

    weekly_sessions = _safe_int(
        extra.get("weekly_sessions") or student.weekly_sessions,
        0,
    )
    supervision_monthly = _safe_int(
        extra.get("supervision_monthly_sessions") or extra.get("monthly_supervision_sessions"),
        0,
    )

    therapy_active = bool(student.therapy_started) or therapy_hours > 0
    supervision_active = supervision_hours > 0 or bool(extra.get("supervision_active"))

    therapy_hours_remaining = max(0, ET_THERAPY_HOURS_TARGET - therapy_hours)
    supervision_hours_remaining = max(0, ET_SUPERVISION_HOURS_TARGET - supervision_hours)

    # Eligibility: analytic rank B+, clinical experience, personal therapy baseline
    analytic_rank = str(extra.get("analytic_rank") or extra.get("gpa_rank") or "").upper()
    rank_ok = analytic_rank in ("B", "B+", "A", "A+") or extra.get("et_eligibility_rank_ok") is True
    clinical_ok = _safe_float(
        extra.get("clinical_hours")
        or therapy_metrics.get("clinical_hours")
        or hours_info.get("clinical_hours", 0)
    ) >= 100
    therapy_baseline_ok = therapy_hours >= 50 or extra.get("et_therapy_baseline_met") is True
    eligibility_met = rank_ok and clinical_ok and therapy_baseline_ok

    ctx = {
        "et_eligibility_met": eligibility_met,
        "et_eligibility_summary_fa": (
            f"رتبه تحلیلی: {'✓' if rank_ok else '✗'}؛ "
            f"تجربه بالینی: {'✓' if clinical_ok else '✗'}؛ "
            f"پایه درمان: {'✓' if therapy_baseline_ok else '✗'}"
        ),
        "et_therapy_active": therapy_active,
        "et_therapy_weekly_sessions": weekly_sessions,
        "et_therapy_hours_completed": therapy_hours,
        "et_therapy_hours_remaining": therapy_hours_remaining,
        "et_therapy_hours_target": ET_THERAPY_HOURS_TARGET,
        "et_supervision_active": supervision_active,
        "et_supervision_monthly_sessions": supervision_monthly,
        "et_supervision_hours_completed": supervision_hours,
        "et_supervision_hours_remaining": supervision_hours_remaining,
        "et_supervision_hours_target": ET_SUPERVISION_HOURS_TARGET,
    }

    merged = {**_as_mapping(existing), **ctx}
    return merged


def resolve_therapy_readiness_trigger(ctx: dict[str, Any]) -> str:
    """Pick system trigger after therapy_readiness_check."""
    if not ctx.get("et_therapy_active"):
        return "no_active_therapy"
    weekly = _safe_int(ctx.get("et_therapy_weekly_sessions"), 0)
    if weekly < 1:
        return "therapy_frequency_low"
    return "therapy_active"


def resolve_supervision_readiness_trigger(ctx: dict[str, Any]) -> str:
    """Pick system trigger after supervision_readiness_check."""
    monthly = _safe_int(ctx.get("et_supervision_monthly_sessions"), 0)
    if monthly < 1:
        return "supervision_restart_needed"
    if monthly == 1:
        return "frequency_increase_needed"
    if ctx.get("et_supervision_active"):
        return "supervision_active"
    return "supervision_restart_needed"


async def persist_et_context(
    db: AsyncSession,
    instance: ProcessInstance,
    extra_fields: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Merge ET context onto instance and flush."""
    ctx = await build_et_upgrade_context(
        db,
        instance.student_id,
        {**_as_mapping(instance.context_data), **_as_mapping(extra_fields)},
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()
    return ctx


async def run_auto_readiness_transition(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    phase: str,
    actor_id: uuid.UUID,
) -> Optional[str]:
    """Auto-fire system transition from readiness check states."""
    from app.core.engine import StateMachineEngine, InvalidTransitionError

    ctx = await persist_et_context(db, instance)
    if phase == "therapy":
        trigger = resolve_therapy_readiness_trigger(ctx)
        if instance.current_state_code != "therapy_readiness_check":
            return None
    elif phase == "supervision":
        trigger = resolve_supervision_readiness_trigger(ctx)
        if instance.current_state_code != "supervision_readiness_check":
            return None
    else:
        return None

    engine = StateMachineEngine(db)
    try:
        res = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event=trigger,
            actor_id=actor_id,
            actor_role="system",
            payload={},
        )
        if res.success:
            return res.to_state
    except InvalidTransitionError as exc:
        logger.warning("ET auto readiness transition failed: %s", exc)
    return None


async def register_et_availability_slots(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
) -> str:
    """Record two ET availability slots from form/context."""
    ctx = _as_mapping(instance.context_data)
    merged = {**ctx, **_as_mapping(context)}

    slot_1 = {
        "day": merged.get("slot_1_day"),
        "time": merged.get("slot_1_time"),
    }
    slot_2 = {
        "day": merged.get("slot_2_day"),
        "time": merged.get("slot_2_time"),
    }
    merged["et_slot_1"] = slot_1
    merged["et_slot_2"] = slot_2
    merged["et_slots_registered_at"] = datetime.now(timezone.utc).isoformat()
    merged["et_slots_registered"] = True

    extra_et = _as_mapping(merged.get("educational_therapist_availability"))
    extra_et["slots"] = [slot_1, slot_2]
    merged["educational_therapist_availability"] = extra_et

    instance.context_data = merged
    flag_modified(instance, "context_data")
    await db.flush()
    return "et_availability_slots_registered"
