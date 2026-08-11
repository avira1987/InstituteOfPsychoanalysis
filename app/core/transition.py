"""Transition Manager - Validates and applies state transitions."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_models import TransitionDefinition, StateDefinition
from app.models.operational_models import ProcessInstance, StateHistory
from app.core.interview_result_access import is_interview_result_trigger
from app.core.rule_engine import RuleEvaluator, RuleResult


# گام‌های ۷ و ۸ آماده‌سازی ترم در رابط کاربری یک مرحلهٔ واحد («مصاحبه‌ها») هستند
SEMESTER_PREP_INTERVIEW_SETUP_TRIGGERS = frozenset(
    {"interviewers_assigned", "interview_times_set"}
)

# نتیجهٔ درگاه پرداخت — فقط callback با actor_role=system (بدون bypass ادمین)
PAYMENT_GATEWAY_TRIGGER_EVENTS = frozenset(
    {
        "payment_confirmed",
        "payment_failed",
        "payment_successful",
        "payment_unsuccessful",
        "payment_success",
        "interview_payment_confirmed",
        "interview_payment_failed",
        "tuition_payment_confirmed",
        "tuition_payment_failed",
    }
)

# نقش‌هایی که می‌توانند interview_time_reached را دستی بزنند (استثنای system)
_INTERVIEW_TIME_REACHED_OPERATOR_ROLES = frozenset(
    {
        "interviewer",
        "staff",
        "site_manager",
        "deputy_education",
    }
)


def is_payment_gateway_trigger(trigger_event: str | None) -> bool:
    return bool(trigger_event) and trigger_event in PAYMENT_GATEWAY_TRIGGER_EVENTS


def human_may_list_system_transition(trigger_event: str | None, actor_role: str) -> bool:
    """آیا transition با required_role=system برای نقش انسانی در لیست اقدامات دیده شود؟"""
    if actor_role == "system":
        return True
    return (
        trigger_event == "interview_time_reached"
        and actor_role in _INTERVIEW_TIME_REACHED_OPERATOR_ROLES
    )


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

    def validate_role(
        self,
        transition: TransitionDefinition,
        actor_role: str,
        trigger_event: str | None = None,
    ) -> bool:
        """Check if the actor's role is authorized for this transition."""
        required = transition.required_role
        te = trigger_event or transition.trigger_event
        # نتیجهٔ درگاه: فقط system — حتی ادمین نباید دستی بزند
        if is_payment_gateway_trigger(te):
            return actor_role == "system"
        # Allow admin to do everything else
        if actor_role == "admin":
            return True
        # ثبت نتیجهٔ مصاحبه: فقط مصاحبه‌گر (مالکیت در engine بررسی می‌شود) یا ادمین
        if is_interview_result_trigger(te):
            return actor_role == "interviewer"
        # Legacy metadata: missing required_role used to mean «everyone» — that exposed
        # system/webhook transitions (e.g. payment_successful) to the student portal.
        if not required:
            if actor_role == "student":
                return False
            return True
        # Callbacks/cron only (e.g. payment gateway uses actor_role="system")
        if required == "system":
            if actor_role == "system":
                return True
            if te == "interview_time_reached" and actor_role in _INTERVIEW_TIME_REACHED_OPERATOR_ROLES:
                return True
            return False
        if actor_role == required:
            return True
        if required == "interviewer" and actor_role in (
            "interviewer",
            "staff",
            "site_manager",
            "deputy_education",
        ):
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
        # کمیته پیشرفت — نقش‌های پروژه/علمی با حساب واحد progress_committee یکی‌اند
        _PROGRESS = (
            "progress_committee",
            "progress_committee_project",
            "progress_committee_scientific",
        )
        if required in _PROGRESS and actor_role in _PROGRESS:
            return True
        # کمیته نظارت + مسئول علمی اجرایی — حساب واحد
        _SUPERVISION = (
            "supervision_committee",
            "monitoring_committee_officer",
        )
        if required in _SUPERVISION and actor_role in _SUPERVISION:
            return True
        # کمیته درمان — مسئول پروژه + مجری روی حساب واحد
        _THERAPY = (
            "therapy_committee_chair",
            "therapy_committee_executor",
        )
        if required in _THERAPY and actor_role in _THERAPY:
            return True
        # کمیته پیشرفت — در پنل همان کارمندان/معاون
        if required == "progress_committee" and actor_role in (
            "staff",
            "site_manager",
            "deputy_education",
        ):
            return True
        # آماده‌سازی ترم پاییز/زمستان (فرایند ۲۹ و ۳۰):
        # معاون آموزش: شهریه، پروانه، مصاحبه‌گران — نه مراحل کمیته دروس.
        if required == "deputy_education_director" and actor_role == "deputy_education":
            return True
        # مرحلهٔ یکپارچهٔ «مصاحبه‌ها»: تعیین مصاحبه‌گر و زمان‌بندی در یک اقدام ثبت
        # می‌شود، پس معاون آموزش و مدیر داخلی هر دو ترنزیشن را می‌زنند.
        if te in SEMESTER_PREP_INTERVIEW_SETUP_TRIGGERS and actor_role in (
            "staff",
            "site_manager",
            "deputy_education",
        ):
            return True
        # کمیته دروس — اجرایی + علمی روی حساب واحد
        _COURSE = (
            "course_committee",
            "course_committee_executive",
            "course_committee_scientific",
            "scientific_officer_course_committee",
        )
        if required in _COURSE and actor_role in _COURSE:
            return True
        # کمیته دروس (پنل course_committee): تقویم، لیست دروس، نهایی‌سازی.
        if required == "course_committee_executive" and actor_role == "course_committee":
            return True
        if required == "scientific_officer_course_committee" and actor_role in (
            "course_committee",
            "staff",
        ):
            return True
        if required == "course_committee_scientific" and actor_role in (
            "course_committee",
            "scientific_officer_course_committee",
            "staff",
        ):
            return True
        if required == "teaching_assistant" and actor_role in (
            "teaching_assistant",
            "staff",
        ):
            return True
        # مدیر داخلی (staff): زمان‌بندی مصاحبه آماده‌سازی ترم و سایر مراحل site_manager در SOP
        if required == "site_manager" and actor_role in ("staff", "site_manager"):
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
