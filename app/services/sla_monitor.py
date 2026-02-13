"""SLA Monitoring Service - Monitors process instances for SLA breaches."""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_models import StateDefinition, ProcessDefinition
from app.models.operational_models import ProcessInstance
from app.services.notification_service import notification_service
from app.core.audit import AuditLogger

logger = logging.getLogger(__name__)


class SLABreachInfo:
    """Information about an SLA breach."""
    def __init__(self, instance_id: str, process_code: str, state_code: str,
                 sla_hours: int, elapsed_hours: float, breach_event: Optional[str] = None):
        self.instance_id = instance_id
        self.process_code = process_code
        self.state_code = state_code
        self.sla_hours = sla_hours
        self.elapsed_hours = elapsed_hours
        self.breach_event = breach_event

    def to_dict(self):
        return {
            "instance_id": self.instance_id,
            "process_code": self.process_code,
            "state_code": self.state_code,
            "sla_hours": self.sla_hours,
            "elapsed_hours": round(self.elapsed_hours, 2),
            "breach_event": self.breach_event,
        }


class SLAMonitor:
    """Monitors process instances for SLA breaches and triggers alerts."""

    def __init__(self):
        self._running = False
        self._breaches: list[SLABreachInfo] = []

    async def check_sla_breaches(self, db: AsyncSession) -> list[SLABreachInfo]:
        """Check all active instances for SLA breaches."""
        now = datetime.now(timezone.utc)
        breaches = []

        # Get all active (non-completed) instances
        stmt = select(ProcessInstance).where(
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        result = await db.execute(stmt)
        instances = result.scalars().all()

        for instance in instances:
            # Load the process definition
            proc_stmt = select(ProcessDefinition).where(
                ProcessDefinition.code == instance.process_code,
                ProcessDefinition.is_active == True,
            )
            proc_result = await db.execute(proc_stmt)
            process_def = proc_result.scalars().first()
            if not process_def:
                continue

            # Load the current state definition
            state_stmt = select(StateDefinition).where(
                StateDefinition.process_id == process_def.id,
                StateDefinition.code == instance.current_state_code,
            )
            state_result = await db.execute(state_stmt)
            state_def = state_result.scalars().first()
            if not state_def or not state_def.sla_hours:
                continue

            # Calculate elapsed time
            elapsed = now - instance.last_transition_at
            elapsed_hours = elapsed.total_seconds() / 3600

            if elapsed_hours > state_def.sla_hours:
                breach = SLABreachInfo(
                    instance_id=str(instance.id),
                    process_code=instance.process_code,
                    state_code=instance.current_state_code,
                    sla_hours=state_def.sla_hours,
                    elapsed_hours=elapsed_hours,
                    breach_event=state_def.on_sla_breach_event,
                )
                breaches.append(breach)

                # Log the breach
                logger.warning(
                    f"SLA BREACH: Instance {instance.id} in state '{instance.current_state_code}' "
                    f"has exceeded SLA of {state_def.sla_hours}h (elapsed: {elapsed_hours:.1f}h)"
                )

                # Send alert notifications
                await self._handle_breach(breach, db)

        self._breaches = breaches
        return breaches

    async def _handle_breach(self, breach: SLABreachInfo, db: AsyncSession):
        """Handle an SLA breach by sending notifications and logging."""
        # Send SLA breach notification
        await notification_service.send_notification(
            notification_type="sms",
            template_name="sla_breach",
            recipient_contact="admin",
            context={
                "instance_id": breach.instance_id,
                "process_code": breach.process_code,
                "state_code": breach.state_code,
                "sla_hours": str(breach.sla_hours),
                "elapsed_hours": str(round(breach.elapsed_hours, 1)),
            },
        )

        # Log audit entry
        audit = AuditLogger(db)
        await audit.log(
            action_type="sla_breach",
            process_code=breach.process_code,
            details=breach.to_dict(),
        )

    async def check_approaching_sla(self, db: AsyncSession, warning_threshold: float = 0.8) -> list[dict]:
        """Check for instances approaching their SLA deadline (warning)."""
        now = datetime.now(timezone.utc)
        warnings = []

        stmt = select(ProcessInstance).where(
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        result = await db.execute(stmt)
        instances = result.scalars().all()

        for instance in instances:
            proc_stmt = select(ProcessDefinition).where(
                ProcessDefinition.code == instance.process_code,
            )
            proc_result = await db.execute(proc_stmt)
            process_def = proc_result.scalars().first()
            if not process_def:
                continue

            state_stmt = select(StateDefinition).where(
                StateDefinition.process_id == process_def.id,
                StateDefinition.code == instance.current_state_code,
            )
            state_result = await db.execute(state_stmt)
            state_def = state_result.scalars().first()
            if not state_def or not state_def.sla_hours:
                continue

            elapsed = now - instance.last_transition_at
            elapsed_hours = elapsed.total_seconds() / 3600
            ratio = elapsed_hours / state_def.sla_hours

            if warning_threshold <= ratio < 1.0:
                warnings.append({
                    "instance_id": str(instance.id),
                    "process_code": instance.process_code,
                    "state_code": instance.current_state_code,
                    "sla_hours": state_def.sla_hours,
                    "elapsed_hours": round(elapsed_hours, 2),
                    "remaining_hours": round(state_def.sla_hours - elapsed_hours, 2),
                    "usage_percent": round(ratio * 100, 1),
                })

        return warnings

    def get_recent_breaches(self) -> list[dict]:
        """Get the most recent breaches found."""
        return [b.to_dict() for b in self._breaches]

    async def start_monitoring_loop(self, db_factory, interval_seconds: int = 300):
        """Start the SLA monitoring loop (background task)."""
        self._running = True
        logger.info(f"SLA Monitor started (interval: {interval_seconds}s)")

        while self._running:
            try:
                async with db_factory() as db:
                    breaches = await self.check_sla_breaches(db)
                    if breaches:
                        logger.warning(f"Found {len(breaches)} SLA breach(es)")
                    await db.commit()
            except Exception as e:
                logger.error(f"SLA Monitor error: {e}", exc_info=True)

            await asyncio.sleep(interval_seconds)

    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self._running = False
        logger.info("SLA Monitor stopped")


# Singleton
sla_monitor = SLAMonitor()
