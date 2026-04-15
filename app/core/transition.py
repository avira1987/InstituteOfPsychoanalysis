"""Transition Manager - Validates and applies state transitions."""

import json
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
        if actor_role == required:
            return True
        # متادیتای ثبت‌نام: «applicant» همان نقش دانشجو در پنل است
        if required == "applicant" and actor_role == "student":
            return True
        # پذیرش: در متادیتا «admissions_officer» است؛ در UI نقش‌های دفتر همان کار را انجام می‌دهند
        if required == "admissions_officer" and actor_role in (
            "staff",
            "site_manager",
            "deputy_education",
        ):
            return True
        # کمیته پیشرفت — در پنل همان کارمندان/معاون
        if required == "progress_committee" and actor_role in (
            "staff",
            "site_manager",
            "deputy_education",
        ):
            return True
        return False

    async def evaluate_conditions(
        self,
        transition: TransitionDefinition,
        rules_map: dict,
        context: dict,
    ) -> list[RuleResult]:
        """Evaluate all condition rules for a transition."""
        raw = transition.condition_rules
        if raw is None:
            return []
        if isinstance(raw, str):
            s = raw.strip().lower()
            if s in ("", "null", "none", "[]"):
                return []
            if s.startswith("["):
                try:
                    parsed = json.loads(raw)
                    condition_codes = list(parsed) if isinstance(parsed, list) else [raw]
                except (json.JSONDecodeError, TypeError):
                    condition_codes = [raw]
            else:
                condition_codes = [raw]
        else:
            try:
                condition_codes = list(raw)
            except TypeError:
                return []
        if not condition_codes:
            return []

        # هر کد شرط باید در rules_map باشد؛ در غیر این صورت قبلاً [] برمی‌گشت و all_passed([])==True
        # و اولین ترنزیشنِ eligibility (مثلاً therapy_check_failed) بدون ارزیابی واقعی انتخاب می‌شد.
        results: list[RuleResult] = []
        for code in condition_codes:
            rule_def = rules_map.get(code)
            if not rule_def:
                results.append(
                    RuleResult(
                        rule_code=code,
                        passed=False,
                        error_message=f"Rule '{code}' not found in registry",
                    )
                )
            else:
                results.append(self.rule_evaluator.evaluate_rule(rule_def, context))
        return results

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
