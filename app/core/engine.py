"""State Machine Engine - The core engine that reads metadata and executes transitions.

No business logic is hardcoded. All rules, states, and transitions
are read from the metadata database at runtime.
"""

import uuid
import logging
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_models import ProcessDefinition, StateDefinition, TransitionDefinition, RuleDefinition
from app.models.operational_models import ProcessInstance, Student, StateHistory
from app.core.rule_engine import RuleEvaluator
from app.core.transition import TransitionManager, TransitionResult, TransitionError
from app.core.event_bus import event_bus, Event
from app.core.audit import AuditLogger
from app.services.attendance_service import AttendanceService
from app.utils.date_utils import get_current_shamsi_year, get_current_term_week

logger = logging.getLogger(__name__)


class EngineError(Exception):
    """Base exception for engine errors."""
    pass


class ProcessNotFoundError(EngineError):
    pass


class InstanceNotFoundError(EngineError):
    pass


class InvalidTransitionError(EngineError):
    pass


class UnauthorizedError(EngineError):
    pass


class StateMachineEngine:
    """
    Core state machine engine.
    Reads all process definitions, states, transitions, and rules from metadata.
    No business logic is hardcoded in this class.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.rule_evaluator = RuleEvaluator()
        self.transition_manager = TransitionManager(db, self.rule_evaluator)
        self.audit_logger = AuditLogger(db)

    # ─── Process Loading ────────────────────────────────────────────

    async def get_process_definition(self, process_code: str) -> ProcessDefinition:
        """Load a process definition by its code."""
        stmt = select(ProcessDefinition).where(
            ProcessDefinition.code == process_code,
            ProcessDefinition.is_active == True,
        )
        result = await self.db.execute(stmt)
        process_def = result.scalars().first()
        if not process_def:
            raise ProcessNotFoundError(f"Process '{process_code}' not found or inactive")
        return process_def

    async def get_process_instance(self, instance_id: uuid.UUID) -> ProcessInstance:
        """Load a process instance by ID."""
        stmt = select(ProcessInstance).where(ProcessInstance.id == instance_id)
        result = await self.db.execute(stmt)
        instance = result.scalars().first()
        if not instance:
            raise InstanceNotFoundError(f"Instance '{instance_id}' not found")
        return instance

    async def get_rules_map(self) -> dict[str, dict]:
        """Load all active rules as a code->definition map."""
        stmt = select(RuleDefinition).where(RuleDefinition.is_active == True)
        result = await self.db.execute(stmt)
        rules = result.scalars().all()
        return {
            r.code: {
                "code": r.code,
                "name_fa": r.name_fa,
                "rule_type": r.rule_type,
                "expression": r.expression,
                "parameters": r.parameters,
                "error_message_fa": r.error_message_fa,
            }
            for r in rules
        }

    # ─── Process Start ──────────────────────────────────────────────

    async def start_process(
        self,
        process_code: str,
        student_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: str,
        initial_context: Optional[dict] = None,
    ) -> ProcessInstance:
        """Start a new process instance for a student."""
        process_def = await self.get_process_definition(process_code)

        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code=process_code,
            student_id=student_id,
            current_state_code=process_def.initial_state_code,
            context_data=initial_context or {},
            started_by=actor_id,
        )
        self.db.add(instance)

        # Record initial state in history
        history = StateHistory(
            id=uuid.uuid4(),
            instance_id=instance.id,
            from_state_code=None,
            to_state_code=process_def.initial_state_code,
            trigger_event="process_started",
            actor_id=actor_id,
            actor_role=actor_role,
            entered_at=datetime.now(timezone.utc),
        )
        self.db.add(history)

        # Audit
        await self.audit_logger.log_process_start(
            instance_id=instance.id,
            process_code=process_code,
            student_id=student_id,
            actor_id=actor_id,
            actor_role=actor_role,
        )

        # Event
        await event_bus.publish(Event(
            event_type=f"process.started.{process_code}",
            payload={
                "instance_id": str(instance.id),
                "process_code": process_code,
                "student_id": str(student_id),
                "initial_state": process_def.initial_state_code,
            },
            source="state_machine_engine",
        ))

        logger.info(f"Started process '{process_code}' for student {student_id}, instance={instance.id}")
        return instance

    # ─── Transition Execution ───────────────────────────────────────

    async def execute_transition(
        self,
        instance_id: uuid.UUID,
        trigger_event: str,
        actor_id: uuid.UUID,
        actor_role: str,
        payload: Optional[dict] = None,
    ) -> TransitionResult:
        """
        Execute a state transition for a process instance.

        Steps:
        1. Load process instance + current state
        2. Find matching transition from metadata
        3. Evaluate all condition_rules via RuleEngine
        4. Check RBAC (actor.role must match transition.required_role)
        5. Apply the transition (update state)
        6. Execute post-actions
        7. Log to audit_logs
        8. Publish event to EventBus
        """
        # 1. Load instance
        instance = await self.get_process_instance(instance_id)
        if instance.is_completed or instance.is_cancelled:
            raise InvalidTransitionError("Process instance is already completed or cancelled")

        process_def = await self.get_process_definition(instance.process_code)
        current_state = instance.current_state_code

        # 2. Find matching transition
        transition = await self.transition_manager.find_matching_transition(
            process_id=process_def.id,
            from_state_code=current_state,
            trigger_event=trigger_event,
        )
        if not transition:
            raise InvalidTransitionError(
                f"No transition found from '{current_state}' with trigger '{trigger_event}'"
            )

        # 3. Evaluate condition rules
        rules_map = await self.get_rules_map()
        context = await self._build_context(instance, payload)
        rule_results = await self.transition_manager.evaluate_conditions(
            transition, rules_map, context
        )
        if not self.rule_evaluator.all_passed(rule_results):
            failed = [r for r in rule_results if not r.passed]
            error_msgs = [r.error_message or f"Rule '{r.rule_code}' failed" for r in failed]
            return TransitionResult(
                success=False,
                from_state=current_state,
                trigger_event=trigger_event,
                rule_results=rule_results,
                error="; ".join(error_msgs),
            )

        # 4. Check RBAC
        if not self.transition_manager.validate_role(transition, actor_role):
            raise UnauthorizedError(
                f"Role '{actor_role}' is not authorized to trigger '{trigger_event}' "
                f"(requires '{transition.required_role}')"
            )

        # 5. Apply transition
        from_state = instance.current_state_code
        await self.transition_manager.apply_transition(
            instance=instance,
            transition=transition,
            actor_id=actor_id,
            actor_role=actor_role,
            payload=payload,
        )

        # Check if new state is terminal
        is_terminal = await self.transition_manager.check_terminal_state(
            process_def.id, transition.to_state_code
        )
        if is_terminal:
            instance.is_completed = True
            instance.completed_at = datetime.now(timezone.utc)

        # Update context data if payload provided
        if payload:
            ctx = instance.context_data or {}
            ctx.update(payload)
            instance.context_data = ctx

        # 6. Post-transition actions
        actions = transition.actions or []
        action_results = []
        if actions:
            from app.services.action_handler import ActionHandler
            handler = ActionHandler(self.db)
            action_results = await handler.handle_actions(actions, instance, payload or {})

        # 7. Audit
        await self.audit_logger.log_transition(
            instance_id=instance.id,
            process_code=instance.process_code,
            from_state=from_state,
            to_state=transition.to_state_code,
            trigger_event=trigger_event,
            actor_id=actor_id,
            actor_role=actor_role,
            payload=payload,
        )

        # 8. Publish events
        await event_bus.publish_transition(
            process_code=instance.process_code,
            instance_id=str(instance.id),
            from_state=from_state,
            to_state=transition.to_state_code,
            trigger_event=trigger_event,
            actor_id=str(actor_id),
            actions=actions,
        )

        logger.info(
            f"Transition: {instance.process_code} [{from_state}] --{trigger_event}--> "
            f"[{transition.to_state_code}] (instance={instance.id})"
        )

        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=transition.to_state_code,
            trigger_event=trigger_event,
            actions=actions,
            rule_results=rule_results,
        )

    # ─── Query Methods ──────────────────────────────────────────────

    async def get_available_transitions(
        self,
        instance_id: uuid.UUID,
        actor_role: str,
    ) -> list[dict]:
        """Get all transitions available from the current state for the given role."""
        instance = await self.get_process_instance(instance_id)
        process_def = await self.get_process_definition(instance.process_code)

        transitions = await self.transition_manager.find_transitions_for_state(
            process_id=process_def.id,
            from_state_code=instance.current_state_code,
        )

        available = []
        for t in transitions:
            if self.transition_manager.validate_role(t, actor_role):
                available.append({
                    "trigger_event": t.trigger_event,
                    "to_state": t.to_state_code,
                    "required_role": t.required_role,
                    "description": t.description_fa,
                    "has_conditions": bool(t.condition_rules),
                })
        return available

    async def get_instance_status(self, instance_id: uuid.UUID) -> dict:
        """Get the full status of a process instance."""
        instance = await self.get_process_instance(instance_id)

        # Get state history
        stmt = (
            select(StateHistory)
            .where(StateHistory.instance_id == instance_id)
            .order_by(StateHistory.entered_at)
        )
        result = await self.db.execute(stmt)
        history = result.scalars().all()

        return {
            "instance_id": str(instance.id),
            "process_code": instance.process_code,
            "current_state": instance.current_state_code,
            "is_completed": instance.is_completed,
            "is_cancelled": instance.is_cancelled,
            "context_data": instance.context_data,
            "started_at": instance.started_at.isoformat() if instance.started_at else None,
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
            "last_transition_at": instance.last_transition_at.isoformat() if instance.last_transition_at else None,
            "history": [
                {
                    "from_state": h.from_state_code,
                    "to_state": h.to_state_code,
                    "trigger_event": h.trigger_event,
                    "actor_role": h.actor_role,
                    "entered_at": h.entered_at.isoformat() if h.entered_at else None,
                }
                for h in history
            ],
        }

    # ─── Internal Helpers ───────────────────────────────────────────

    async def _build_context(self, instance: ProcessInstance, payload: Optional[dict] = None) -> dict:
        """Build the evaluation context for rule evaluation.

        Enriches instance with: absence_quota, absences_this_year (current Shamsi year),
        completed_hours, required_hours for rule evaluation (see BUILD_TODO § د).
        """
        # Load student data
        stmt = select(Student).where(Student.id == instance.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()

        context = {
            "instance": {
                "id": str(instance.id),
                "process_code": instance.process_code,
                "current_state": instance.current_state_code,
                **(instance.context_data or {}),
            },
            "student": {},
            "payload": payload or {},
        }

        if student:
            context["student"] = {
                "id": str(student.id),
                "student_code": student.student_code,
                "course_type": student.course_type,
                "is_intern": student.is_intern,
                "term_count": student.term_count,
                "current_term": student.current_term,
                "therapy_started": student.therapy_started,
                "weekly_sessions": student.weekly_sessions,
                **(student.extra_data or {}),
            }

            # Enrich instance for rules: absence quota, absences this year, completed/required hours,
            # current_week (week_9_deadline), hours_until_first_slot (24_hour_rule) — BUILD_TODO § د
            attendance = AttendanceService(self.db)
            shamsi_year = get_current_shamsi_year()
            context["instance"]["absence_quota"] = await attendance.calculate_absence_quota(student.id)
            context["instance"]["absences_this_year"] = await attendance.get_absence_count(
                student.id, shamsi_year=shamsi_year, status_filter="absent_unexcused"
            )
            hours_info = await attendance.get_completed_hours(student.id)
            context["instance"]["completed_hours"] = hours_info["total_hours"]
            extra = student.extra_data or {}
            context["instance"]["required_hours"] = extra.get("required_hours", 250)

            # current_week: from term_start in extra_data (ISO date) or default fall term
            term_start = None
            if extra.get("term_start_date"):
                try:
                    term_start = date.fromisoformat(extra["term_start_date"])
                except (TypeError, ValueError):
                    pass
            context["instance"]["current_week"] = get_current_term_week(term_start=term_start)

            # hours_until_first_slot: for 24_hour_rule (use_first_slot vs use_next_slot)
            context["instance"]["hours_until_first_slot"] = await attendance.get_hours_until_first_slot(student.id)

        return context
