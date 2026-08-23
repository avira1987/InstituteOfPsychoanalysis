"""Action Handler - Executes transition actions from process metadata.

This is the bridge between the state machine engine (which reads metadata and
changes states) and the actual business logic (SMS, session management, etc.).

When a transition fires, its `actions` list is published via EventBus.
This handler subscribes to those events and dispatches each action to
the appropriate service method."""

# The action implementations live in app/services/actions/, one module per domain.
# ActionHandler composes those mixins and merges their registries; only the
# dispatch loop lives here.
from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from app.services.attendance_service import AttendanceService
from app.services.payment_service import PaymentService
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any, List
import logging

from app.services.actions import (
    _base,
    notifications,
    process_control,
    sessions,
    therapy,
    attendance,
    payments,
    supervision,
    records,
)
from app.services.actions._shared import (  # noqa: F401  (kept importable from here)
    _as_mapping,
    parse_therapy_session_id_list,
    validate_supervision_reduction_preflight,
    validate_therapy_reduction_preflight,
)

from app.services.actions._base import ActionHandlerBase
from app.services.actions.notifications import NotificationActionsMixin
from app.services.actions.process_control import ProcessControlActionsMixin
from app.services.actions.sessions import SessionActionsMixin
from app.services.actions.therapy import TherapyActionsMixin
from app.services.actions.attendance import AttendanceActionsMixin
from app.services.actions.payments import PaymentActionsMixin
from app.services.actions.supervision import SupervisionActionsMixin
from app.services.actions.records import RecordActionsMixin

logger = logging.getLogger(__name__)


class ActionHandler(
    ActionHandlerBase,
    NotificationActionsMixin,
    ProcessControlActionsMixin,
    SessionActionsMixin,
    TherapyActionsMixin,
    AttendanceActionsMixin,
    PaymentActionsMixin,
    SupervisionActionsMixin,
    RecordActionsMixin,
):
    """Executes the `actions` declared on a transition.

    Handlers are contributed by the domain mixins in app/services/actions/ and
    looked up by `action.type` in `_registry`.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.payment = PaymentService(db)
        self.attendance = AttendanceService(db)

    async def handle_actions(
        self,
        actions: list[dict],
        instance: ProcessInstance,
        context: dict,
    ) -> list[dict]:
        """Execute a list of actions from a transition and return results."""
        results = []
        for action in actions:
            if not isinstance(action, dict):
                logger.warning(
                    "Skipping invalid action (expected dict, got %s): %r",
                    type(action).__name__,
                    action,
                )
                results.append({"action": "invalid_action_shape", "success": True, "detail": "skipped"})
                continue
            action_type = action.get("type", "unknown")
            try:
                result = await self._dispatch(action_type, action, instance, context)
                results.append({"action": action_type, "success": True, "detail": result})
                logger.info(f"Action OK: {action_type} | instance={instance.id}")
            except Exception as e:
                results.append({"action": action_type, "success": False, "error": str(e)})
                logger.error(f"Action FAIL: {action_type} | instance={instance.id} | {e}", exc_info=True)
                try:
                    from app.services.failed_action_service import record_failed_action

                    await record_failed_action(
                        self.db,
                        instance,
                        action_type,
                        action if isinstance(action, dict) else None,
                        str(e),
                    )
                except Exception:
                    logger.exception("Failed to persist failed_action for %s", action_type)
        return results

    async def _dispatch(
        self,
        action_type: str,
        action: dict,
        instance: ProcessInstance,
        context: dict,
    ) -> Optional[str]:
        handler = self._registry.get(action_type)
        if handler:
            return await handler(self, action, instance, context)

        if action_type.startswith("record_"):
            return await self._handle_record_process_artifact(action, instance, context)

        logger.warning(f"No handler for action type '{action_type}', skipping.")
        return f"no_handler_for_{action_type}"

    # ─── Action Registry ─────────────────────────────────────────
    # Assembled from the per-domain registries; see app/services/actions/.
    _registry = {
        **notifications.REGISTRY,
        **process_control.REGISTRY,
        **sessions.REGISTRY,
        **therapy.REGISTRY,
        **attendance.REGISTRY,
        **payments.REGISTRY,
        **supervision.REGISTRY,
        **records.REGISTRY,
    }
