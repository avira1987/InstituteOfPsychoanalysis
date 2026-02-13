"""Transition Manager - Validates and applies state transitions."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_models import TransitionDefinition, StateDefinition
from app.models.operational_models import ProcessInstance, StateHistory
from app.core.rule_engine import RuleEvaluator, RuleResult


class TransitionError(Exception):
    """Raised when a transition cannot be performed."""
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class TransitionResult:
    """Result of a state transition."""
    def __init__(
        self,
        success: bool,
        from_state: str,
        to_state: Optional[str] = None,
        trigger_event: Optional[str] = None,
        actions: Optional[list[dict]] = None,
        rule_results: Optional[list[RuleResult]] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.from_state = from_state
        self.to_state = to_state
        self.trigger_event = trigger_event
        self.actions = actions or []
        self.rule_results = rule_results or []
        self.error = error

    def to_dict(self):
        return {
            "success": self.success,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "trigger_event": self.trigger_event,
            "actions": self.actions,
            "rule_results": [r.to_dict() for r in self.rule_results],
            "error": self.error,
        }


class TransitionManager:
    """Validates and applies state transitions based on metadata definitions."""

    def __init__(self, db: AsyncSession, rule_evaluator: RuleEvaluator):
        self.db = db
        self.rule_evaluator = rule_evaluator

    async def find_matching_transition(
        self,
        process_id: uuid.UUID,
        from_state_code: str,
        trigger_event: str,
    ) -> Optional[TransitionDefinition]:
        """Find a transition definition matching the current state and trigger event."""
        stmt = (
            select(TransitionDefinition)
            .where(
                TransitionDefinition.process_id == process_id,
                TransitionDefinition.from_state_code == from_state_code,
                TransitionDefinition.trigger_event == trigger_event,
            )
            .order_by(TransitionDefinition.priority.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def find_transitions_for_state(
        self,
        process_id: uuid.UUID,
        from_state_code: str,
    ) -> list[TransitionDefinition]:
        """Find all available transitions from a given state."""
        stmt = (
            select(TransitionDefinition)
            .where(
                TransitionDefinition.process_id == process_id,
                TransitionDefinition.from_state_code == from_state_code,
            )
            .order_by(TransitionDefinition.priority.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    def validate_role(self, transition: TransitionDefinition, actor_role: str) -> bool:
        """Check if the actor's role is authorized for this transition."""
        required = transition.required_role
        if not required:
            return True
        # Allow admin to do everything
        if actor_role == "admin":
            return True
        # Allow system transitions
        if required == "system":
            return True
        return actor_role == required

    async def evaluate_conditions(
        self,
        transition: TransitionDefinition,
        rules_map: dict,
        context: dict,
    ) -> list[RuleResult]:
        """Evaluate all condition rules for a transition."""
        condition_codes = transition.condition_rules or []
        if not condition_codes:
            return []

        rules_to_evaluate = []
        for code in condition_codes:
            if code in rules_map:
                rules_to_evaluate.append(rules_map[code])

        return self.rule_evaluator.evaluate_rules(rules_to_evaluate, context)

    async def apply_transition(
        self,
        instance: ProcessInstance,
        transition: TransitionDefinition,
        actor_id: uuid.UUID,
        actor_role: str,
        payload: Optional[dict] = None,
    ) -> None:
        """Apply a transition: update instance state and record history."""
        from_state = instance.current_state_code
        to_state = transition.to_state_code
        now = datetime.now(timezone.utc)

        # Update the process instance
        instance.current_state_code = to_state
        instance.last_transition_at = now

        # Check if we've reached a terminal state
        # (We'll check via state definitions in the engine)

        # Record state history
        history = StateHistory(
            id=uuid.uuid4(),
            instance_id=instance.id,
            from_state_code=from_state,
            to_state_code=to_state,
            trigger_event=transition.trigger_event,
            actor_id=actor_id,
            actor_role=actor_role,
            payload=payload,
            entered_at=now,
        )
        self.db.add(history)

    async def check_terminal_state(
        self,
        process_id: uuid.UUID,
        state_code: str,
    ) -> bool:
        """Check if a state is a terminal state."""
        stmt = (
            select(StateDefinition)
            .where(
                StateDefinition.process_id == process_id,
                StateDefinition.code == state_code,
            )
        )
        result = await self.db.execute(stmt)
        state_def = result.scalars().first()
        if state_def:
            return state_def.state_type == "terminal"
        return False
