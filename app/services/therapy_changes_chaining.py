"""اتصال فرایند therapy_changes به نمونه‌های باز «مهلت بازگشت» و «وضعیت مبهم غیبت»."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance

logger = logging.getLogger(__name__)

SYSTEM_ACTOR = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def propagate_on_therapy_changes_started(
    db: AsyncSession,
    instance: ProcessInstance,
) -> None:
    """اگر برای همین دانشجو فرایند واکنش غیبت در وضعیت مبهم باز باشد، تریگر بازگشت را بزن."""
    if instance.process_code != "therapy_changes":
        return
    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == instance.student_id,
        ProcessInstance.process_code == "unannounced_absence_reaction",
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
        ProcessInstance.current_state_code == "ambiguous_3week_wait",
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    if not rows:
        return
    from app.core.engine import StateMachineEngine

    engine = StateMachineEngine(db)
    for parent in rows:
        try:
            res = await engine.execute_transition(
                instance_id=parent.id,
                trigger_event="student_started_therapy_changes",
                actor_id=SYSTEM_ACTOR,
                actor_role="system",
                payload={"child_therapy_changes_instance_id": str(instance.id)},
            )
            if not res.success:
                logger.warning(
                    "student_started_therapy_changes failed parent=%s err=%s",
                    parent.id,
                    res.error,
                )
        except Exception:
            logger.exception("student_started_therapy_changes exception parent=%s", parent.id)


async def propagate_therapy_changes_completed(
    db: AsyncSession,
    instance: ProcessInstance,
    to_state: str,
) -> None:
    """پس از تایید تغییر یا آغاز مجدد، نمونه‌های در انتظار بازگشت به درمان را جلو ببر."""
    if instance.process_code != "therapy_changes":
        return
    if to_state not in ("change_approved", "restart_activated"):
        return

    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == instance.student_id,
        ProcessInstance.process_code.in_(
            ("therapy_early_termination", "specialized_commission_review", "committees_review")
        ),
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
        ProcessInstance.current_state_code == "awaiting_student_restart",
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    if not rows:
        return

    from app.core.engine import StateMachineEngine

    engine = StateMachineEngine(db)
    payload = {"therapy_changes_instance_id": str(instance.id), "completed_to_state": to_state}
    for parent in rows:
        try:
            res = await engine.execute_transition(
                instance_id=parent.id,
                trigger_event="student_restarted_therapy",
                actor_id=SYSTEM_ACTOR,
                actor_role="system",
                payload=payload,
            )
            if not res.success:
                logger.warning(
                    "student_restarted_therapy failed parent=%s (%s) err=%s",
                    parent.id,
                    parent.process_code,
                    res.error,
                )
        except Exception:
            logger.exception(
                "student_restarted_therapy exception parent=%s code=%s",
                parent.id,
                parent.process_code,
            )
