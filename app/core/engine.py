"""State Machine Engine - The core engine that reads metadata and executes transitions.

No business logic is hardcoded. All rules, states, and transitions
are read from the metadata database at runtime.
"""

import json
import uuid
import logging
from datetime import date, datetime, timezone
from typing import Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.meta_models import ProcessDefinition, StateDefinition, TransitionDefinition, RuleDefinition
from app.models.operational_models import ProcessInstance, InterviewSlot, Student, StateHistory, TherapySession
from app.core.rule_engine import RuleEvaluator
from app.core.transition import TransitionManager, TransitionResult, TransitionError
from app.core.event_bus import event_bus, Event
from app.core.audit import AuditLogger
from app.services.attendance_service import AttendanceService
from app.core.gamification import merge_gamification_into_extra
from app.utils.date_utils import get_current_shamsi_year, get_current_term_week
from app.core.interview_result_access import (
    assert_can_submit_interview_result,
    can_submit_interview_result,
    is_interview_result_trigger,
)
from app.core.student_forbidden_triggers import STUDENT_FORBIDDEN_TRIGGER_EVENTS
from app.models.operational_models import User

logger = logging.getLogger(__name__)

# introductory_course_registration: چند ترنزیشن با trigger یکسان (interview_result_submitted)
_INTERVIEW_RESULT_BY_TO_STATE = {
    "result_conditional_therapy": "conditional_therapy",
    "result_single_course": "single_course",
    "result_full_admission": "full_admission",
    "rejected": "rejected",
}

# دانشجو/متقاضی فقط از رزرو اسلات (مسیر جدا)؛ نه با دکمهٔ trigger عمومی
_REGISTRATION_INTERVIEW_BOOKING_TRIGGERS = frozenset({"timeslot_selected", "interview_time_selected"})


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


class RestartProcessResult:
    """نتیجهٔ شروع دوباره فرایند (بایگانی + نمونهٔ جدید)."""

    def __init__(
        self,
        success: bool,
        old_instance_id: uuid.UUID,
        new_instance_id: uuid.UUID,
        process_code: str,
        current_state: str,
        error: Optional[str] = None,
    ):
        self.success = success
        self.old_instance_id = old_instance_id
        self.new_instance_id = new_instance_id
        self.process_code = process_code
        self.current_state = current_state
        self.error = error


def _normalize_json_list(raw) -> list:
    """JSONB گاهی به‌صورت رشتهٔ 'null' یا JSON رشته‌ای ذخیره می‌شود؛ همیشه لیست برگردان."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s or s.lower() in ("null", "none"):
            return []
        try:
            parsed = json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return []
        if parsed is None:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


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

        def _coerce_jsonb(val):
            # گاهی JSONB به‌صورت رشتهٔ JSON دوباره‌کدشده از DB برمی‌گردد
            if isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    return parsed
                except (json.JSONDecodeError, TypeError):
                    return val
            return val

        stmt = select(RuleDefinition).where(RuleDefinition.is_active == True)
        result = await self.db.execute(stmt)
        rules = result.scalars().all()
        return {
            r.code: {
                "code": r.code,
                "name_fa": r.name_fa,
                "rule_type": r.rule_type,
                "expression": _coerce_jsonb(r.expression),
                "parameters": _coerce_jsonb(r.parameters) if r.parameters is not None else None,
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

        if process_code == "therapy_changes":
            try:
                await self.db.flush()
                from app.services.therapy_changes_chaining import propagate_on_therapy_changes_started

                await propagate_on_therapy_changes_started(self.db, instance)
            except Exception:
                logger.exception(
                    "therapy_changes start propagation failed (instance=%s)",
                    instance.id,
                )

        if process_code in ("educational_leave", "full_education_leave"):
            try:
                await self.db.flush()
                from app.services.student_non_registration_chaining import (
                    maybe_advance_non_registration_on_leave_start,
                )

                await maybe_advance_non_registration_on_leave_start(
                    self.db, self, student_id, process_code, actor_id,
                )
            except Exception:
                logger.exception(
                    "student_non_registration leave chain on start failed (instance=%s)",
                    instance.id,
                )

        if process_code == "therapy_completion":
            try:
                await self.db.flush()
                await self._persist_therapy_completion_snapshot(instance)
            except Exception:
                logger.exception(
                    "therapy_completion initial snapshot failed (instance=%s)",
                    instance.id,
                )

        if process_code == "ta_to_assistant_faculty":
            try:
                await self.db.flush()
                from app.services.ta_to_assistant_faculty_service import propagate_on_start

                await propagate_on_start(self.db, instance, actor_id=actor_id)
            except Exception:
                logger.exception(
                    "ta_to_assistant_faculty propagate on start failed (instance=%s)",
                    instance.id,
                )

        if process_code == "return_to_full_education":
            try:
                await self.db.flush()
                from app.services.return_to_full_education_service import propagate_on_start

                await propagate_on_start(self.db, instance)
            except Exception:
                logger.exception(
                    "return_to_full_education propagate on start failed (instance=%s)",
                    instance.id,
                )

        if process_code == "full_education_leave":
            try:
                await self.db.flush()
                from app.services.full_education_leave_service import propagate_on_start

                await propagate_on_start(self.db, instance)
            except Exception:
                logger.exception(
                    "full_education_leave propagate on start failed (instance=%s)",
                    instance.id,
                )

        try:
            from app.services.manual_process_start_notification import notify_manual_process_started

            await notify_manual_process_started(self.db, instance, process_def)
        except Exception:
            logger.exception(
                "process start SMS failed (instance=%s process=%s)",
                instance.id,
                process_code,
            )

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

        if payload is None:
            payload = {}
        elif not isinstance(payload, dict):
            payload = {}
        if trigger_event == "interview_result_submitted":
            ts = payload.get("to_state") or payload.get("target_to_state")
            # همیشه از to_state هم‌راستا کن — مقدار قدیمی در context_data یا payload ممکن است مانع pass شدن قوانین شود
            if ts and ts in _INTERVIEW_RESULT_BY_TO_STATE:
                payload = {**payload, "interview_result": _INTERVIEW_RESULT_BY_TO_STATE[ts]}

        if instance.process_code in (
            "live_supervision_session_prep",
            "live_therapy_observation_session_prep",
        ):
            if trigger_event == "time_registered":
                payload = {**payload, "session_time_registered": True}
            elif trigger_event == "no_time_agreed":
                payload = {**payload, "session_time_registered": False}

        if (
            actor_role in ("student", "applicant")
            and trigger_event == "proceed_to_payment"
            and instance.process_code == "introductory_course_registration"
            and instance.current_state_code == "interview_scheduled"
        ):
            if not await self._instance_has_registration_interview_booking(instance.id, instance.student_id):
                raise InvalidTransitionError(
                    "اول باید زمان مصاحبه را از همین صفحه رزرو کنید؛ وقت رزروشده به این مسیر وصل نشده است."
                )

        if (
            instance.process_code == "upgrade_to_ta"
            and instance.current_state_code == "student_click"
            and trigger_event == "conditions_met"
        ):
            from app.services.ta_upgrade_service import (
                build_ta_upgrade_context,
                validate_conditions_met_trigger,
            )

            ta_ctx = await build_ta_upgrade_context(
                self.db, instance.student_id, instance.context_data or {}
            )
            err = validate_conditions_met_trigger(ta_ctx)
            if err:
                raise InvalidTransitionError(err)

        if instance.process_code == "introductory_course_registration":
            # ثبت نتیجهٔ مصاحبه/پیشروی مصاحبه‌گر نباید با قفل ثبت‌نام (انتشار تقویم) مسدود شود؛
            # قفل فقط برای پیشروی دانشجو (شروع/انتخاب درس/پرداخت) است.
            _gate_exempt_triggers = {
                "interview_result_submitted",
                "interview_time_reached",
            }
            if (
                actor_role != "interviewer"
                and trigger_event not in _gate_exempt_triggers
            ):
                from app.services.registration_readiness_service import check_intro_registration_gate

                gate = await check_intro_registration_gate(self.db)
                if not gate.allowed:
                    raise InvalidTransitionError(gate.reason_fa)

        # 2–3. همهٔ ترنزیشن‌های هم‌نام با trigger (به‌ترتیب priority)، تا اولین شاخه‌ای که قوانینش pass شود
        all_transitions = await self.transition_manager.find_transitions_for_state(
            process_def.id, current_state
        )
        candidates = [t for t in all_transitions if t.trigger_event == trigger_event]
        if not candidates:
            raise InvalidTransitionError(
                f"No transition found from '{current_state}' with trigger '{trigger_event}'"
            )
        candidates.sort(key=lambda t: t.priority or 0, reverse=True)

        # یک trigger چند شاخه: اگر UI مقصد را فرستاد، فقط همان ترنزیشن را بررسی کن
        p = payload if isinstance(payload, dict) else {}
        explicit_to = p.get("to_state") or p.get("target_to_state")
        if explicit_to:
            narrowed = [t for t in candidates if t.to_state_code == explicit_to]
            if narrowed:
                candidates = narrowed

        rules_map = await self.get_rules_map()
        context = await self._build_context(instance, payload)
        transition = None
        rule_results = []
        last_rule_results = []
        for t in candidates:
            rr = await self.transition_manager.evaluate_conditions(t, rules_map, context)
            last_rule_results = rr
            if self.rule_evaluator.all_passed(rr):
                transition = t
                rule_results = rr
                break
        if not transition:
            failed = [r for r in last_rule_results if not r.passed]
            error_msgs = [r.error_message or f"Rule '{r.rule_code}' failed" for r in failed]
            err = "; ".join(error_msgs) if error_msgs else "هیچ شاخه‌ای از قوانین عبور نکرد"
            if trigger_event == "interview_result_submitted" and len(candidates) > 1:
                err += (
                    " — برای دکمه‌های نتیجهٔ مصاحبه، «to_state» و «interview_result» باید با همان دکمه هماهنگ باشند؛ "
                    "اگر این خطا را می‌بینید، مقدار قدیمی در پرونده ممکن است جلوی شاخهٔ درست را گرفته باشد."
                )
            return TransitionResult(
                success=False,
                from_state=current_state,
                trigger_event=trigger_event,
                rule_results=last_rule_results,
                error=err,
            )

        if (
            instance.process_code == "therapy_session_reduction"
            and trigger_event == "sessions_selected"
            and transition.to_state_code in ("reduction_completed", "violation_warning")
        ):
            from app.services.action_handler import validate_therapy_reduction_preflight

            st_stmt = select(Student).where(Student.id == instance.student_id)
            st_res = await self.db.execute(st_stmt)
            st_student = st_res.scalars().first()
            if st_student:
                perr = await validate_therapy_reduction_preflight(
                    self.db, instance, payload or {}, st_student
                )
                if perr:
                    return TransitionResult(
                        success=False,
                        from_state=current_state,
                        trigger_event=trigger_event,
                        rule_results=rule_results,
                        error=perr,
                    )

        if (
            instance.process_code == "supervision_session_reduction"
            and trigger_event == "sessions_selected"
            and transition.to_state_code == "multi_reduction_completed"
        ):
            from app.services.action_handler import validate_supervision_reduction_preflight

            st_stmt = select(Student).where(Student.id == instance.student_id)
            st_res = await self.db.execute(st_stmt)
            st_student = st_res.scalars().first()
            if st_student:
                perr = await validate_supervision_reduction_preflight(
                    self.db, instance, payload or {}, st_student
                )
                if perr:
                    return TransitionResult(
                        success=False,
                        from_state=current_state,
                        trigger_event=trigger_event,
                        rule_results=rule_results,
                        error=perr,
                    )

        if instance.process_code == "supervisor_session_cancellation":
            from app.services.supervisor_session_cancellation_service import (
                validate_supervisor_makeup_time,
                validate_supervisor_session_selection,
            )

            merged_p = {**self._as_mapping(instance.context_data), **(payload or {})}
            sup_user_id = None
            st_row = await self.db.get(Student, instance.student_id)
            if st_row and st_row.supervisor_id:
                sup_user_id = st_row.supervisor_id

            if trigger_event == "session_selected":
                sel = merged_p.get("selected_session")
                serr = await validate_supervisor_session_selection(
                    self.db,
                    instance.student_id,
                    sel,
                    supervisor_user_id=sup_user_id,
                )
                if serr:
                    return TransitionResult(
                        success=False,
                        from_state=current_state,
                        trigger_event=trigger_event,
                        rule_results=rule_results,
                        error=serr,
                    )
            elif trigger_event in ("makeup_date_entered", "supervisor_entered_new_time"):
                if merged_p.get("makeup_option") == "no_makeup":
                    pass
                else:
                    pd = merged_p.get("proposed_date")
                    pt = merged_p.get("proposed_time")
                    merr = await validate_supervisor_makeup_time(pd, pt)
                    if merr:
                        return TransitionResult(
                            success=False,
                            from_state=current_state,
                            trigger_event=trigger_event,
                            rule_results=rule_results,
                            error=merr,
                        )
            elif trigger_event == "student_counter_proposed":
                if not str(merged_p.get("counter_proposal_text") or "").strip():
                    return TransitionResult(
                        success=False,
                        from_state=current_state,
                        trigger_event=trigger_event,
                        rule_results=rule_results,
                        error="لطفاً تاریخ و ساعت پیشنهادی خود را در توضیحات بنویسید.",
                    )

        if instance.process_code == "student_session_cancellation" and trigger_event in (
            "student_selects_sessions",
            "student_confirms",
        ):
            from app.services.action_handler import parse_therapy_session_id_list
            from app.services.student_session_cancellation_service import (
                get_cancellation_stats,
                validate_student_cancellation_selection,
            )

            merged_p = {**self._as_mapping(instance.context_data), **(payload or {})}
            selected_raw = merged_p.get("selected_sessions")
            require_ack = False
            if trigger_event == "student_confirms":
                pct = merged_p.get("cancellation_percent_after")
                if pct is None:
                    stats = await get_cancellation_stats(
                        self.db,
                        instance.student_id,
                        len(parse_therapy_session_id_list(selected_raw)),
                    )
                    pct = stats.get("cancellation_percent_after")
                try:
                    require_ack = float(pct or 0) > 12
                except (TypeError, ValueError):
                    require_ack = False
            serr = await validate_student_cancellation_selection(
                self.db,
                instance.student_id,
                selected_raw,
                require_violation_ack=require_ack,
                violation_ack=bool(merged_p.get("violation_ack")),
            )
            if serr:
                return TransitionResult(
                    success=False,
                    from_state=current_state,
                    trigger_event=trigger_event,
                    rule_results=rule_results,
                    error=serr,
                )

        if instance.process_code == "student_supervision_cancellation" and trigger_event in (
            "student_selects_sessions",
            "student_confirms",
        ):
            from app.services.student_supervision_cancellation_service import (
                get_supervision_cancellation_stats,
                parse_supervision_instance_id_list,
                validate_student_supervision_cancellation_selection,
            )

            merged_p = {**self._as_mapping(instance.context_data), **(payload or {})}
            selected_raw = merged_p.get("selected_sessions")
            require_ack = False
            if trigger_event == "student_confirms":
                pct = merged_p.get("cancellation_percent_after")
                if pct is None:
                    stats = await get_supervision_cancellation_stats(
                        self.db,
                        instance.student_id,
                        len(parse_supervision_instance_id_list(selected_raw)),
                    )
                    pct = stats.get("cancellation_percent_after")
                try:
                    require_ack = float(pct or 0) > 12
                except (TypeError, ValueError):
                    require_ack = False
            serr = await validate_student_supervision_cancellation_selection(
                self.db,
                instance.student_id,
                selected_raw,
                require_violation_ack=require_ack,
                violation_ack=bool(merged_p.get("violation_ack")),
            )
            if serr:
                return TransitionResult(
                    success=False,
                    from_state=current_state,
                    trigger_event=trigger_event,
                    rule_results=rule_results,
                    error=serr,
                )

        # 3b. DB ممکن است required_role قدیمی داشته باشد؛ لیست انحصاری «فقط system» در متادیتا را اعمال کن.
        if actor_role == "student" and trigger_event in STUDENT_FORBIDDEN_TRIGGER_EVENTS:
            raise UnauthorizedError(
                f"Trigger '{trigger_event}' is not available for students (system/callback only)."
            )

        actor_user = await self.db.get(User, actor_id)
        if actor_user and is_interview_result_trigger(trigger_event):
            await assert_can_submit_interview_result(
                self.db,
                instance=instance,
                user=actor_user,
                trigger_event=trigger_event,
            )

        # 4. Check RBAC
        if not self.transition_manager.validate_role(
            transition, actor_role, trigger_event=trigger_event
        ):
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
        if payload and isinstance(payload, dict):
            ctx = dict(self._as_mapping(instance.context_data))
            ctx.update(payload)
            if instance.process_code == "educational_leave" and "leave_terms" in ctx:
                try:
                    ctx["leave_terms"] = int(ctx["leave_terms"])
                except (TypeError, ValueError):
                    pass
            if instance.process_code == "full_education_leave" and "leave_terms" in ctx:
                try:
                    ctx["leave_terms"] = int(ctx["leave_terms"])
                except (TypeError, ValueError):
                    pass
            if trigger_event == "documents_approved":
                ctx.pop("__documents_resubmit_fields", None)
                ctx.pop("__document_field_status", None)
                ctx.pop("__document_field_rejection_notes", None)
            elif trigger_event == "documents_resubmitted":
                ctx.pop("__documents_resubmit_fields", None)
                ctx.pop("__document_field_status", None)
                ctx.pop("__document_field_rejection_notes", None)
            elif (
                trigger_event == "documents_rejected"
                and instance.process_code == "introductory_course_registration"
            ):
                from datetime import timedelta
                from app.meta.process_forms import get_process_forms

                resubmit = ctx.get("__documents_resubmit_fields") or []
                labels: dict[str, str] = {}
                for form in get_process_forms(instance.process_code, "documents_upload"):
                    for field in form.get("fields") or []:
                        name = field.get("name")
                        if name:
                            labels[str(name)] = str(field.get("label_fa") or name)
                lines = [
                    f"{i}- {labels.get(str(fname), str(fname))}"
                    for i, fname in enumerate(resubmit, 1)
                ]
                ctx["__document_field_labels_fa"] = labels
                ctx["deficiency_list"] = "\n".join(lines) if lines else "—"
                ctx["documents_correction_deadline"] = (
                    datetime.now(timezone.utc) + timedelta(hours=48)
                ).date().isoformat()
            instance.context_data = ctx
            flag_modified(instance, "context_data")

        if instance.process_code == "ta_track_change" and trigger_event == "approved":
            try:
                from app.models.operational_models import Student
                from app.services.ta_track_change_service import apply_track_change

                student = await self.db.get(Student, instance.student_id)
                ctx_apply = dict(self._as_mapping(instance.context_data))
                path = str(ctx_apply.get("path") or (payload or {}).get("path") or "")
                new_tracks = ctx_apply.get("new_tracks") or (payload or {}).get("new_tracks") or []
                ta_user = None
                if student and student.user_id:
                    ta_user = await self.db.get(User, student.user_id)
                if student:
                    result_apply = await apply_track_change(
                        self.db,
                        student,
                        path=path,
                        new_tracks=new_tracks if isinstance(new_tracks, list) else [new_tracks],
                        ta_user=ta_user,
                    )
                    ctx_apply["applied_tracks"] = result_apply.get("applied_tracks")
                    instance.context_data = ctx_apply
                    flag_modified(instance, "context_data")
            except ValueError as e:
                raise InvalidTransitionError(str(e)) from e
            except Exception:
                logger.exception(
                    "ta_track_change apply failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code == "supervisor_session_cancellation" and payload:
            try:
                from app.services.supervisor_session_cancellation_service import (
                    resolve_selected_supervision_session,
                )
                sel = (payload or {}).get("selected_session") or self._as_mapping(
                    instance.context_data
                ).get("selected_session")
                if sel:
                    detail = await resolve_selected_supervision_session(
                        self.db, instance.student_id, sel
                    )
                    if detail:
                        ctx_sc = dict(self._as_mapping(instance.context_data))
                        ctx_sc.update(detail)
                        instance.context_data = ctx_sc
                        flag_modified(instance, "context_data")
            except Exception:
                logger.exception(
                    "supervisor_session_cancellation enrich after transition failed"
                )

        if instance.process_code == "therapy_changes" and transition.to_state_code in (
            "change_approved",
            "restart_activated",
        ):
            ctx2 = dict(self._as_mapping(instance.context_data))
            if transition.to_state_code == "restart_activated":
                ctx2["therapy_changes_next_step_fa"] = (
                    "جلسات آینده از تقویم حذف شدند. در صورت نیاز برای بازآغازی و رزرو، از فرایند «آغاز درمان آموزشی» "
                    "یا مطابق راهنمای انستیتو اقدام کنید."
                )
            else:
                ctx2["therapy_changes_next_step_fa"] = (
                    "تغییر در سامانه ثبت شد. جلسات آتی را در بخش جلسات درمان بررسی کنید."
                )
            instance.context_data = ctx2
            flag_modified(instance, "context_data")

        if instance.process_code == "therapy_completion":
            try:
                await self._persist_therapy_completion_snapshot(instance)
            except Exception:
                logger.exception(
                    "therapy_completion snapshot after transition failed (instance=%s)",
                    instance.id,
                )

        try:
            await self.persist_registration_payment_defaults_if_needed(instance)
        except Exception:
            logger.exception(
                "registration payment default context after transition failed (instance=%s)",
                instance.id,
            )

        if (
            instance.process_code == "introductory_course_registration"
            and transition.to_state_code == "course_selection"
            and trigger_event == "student_logged_in"
        ):
            from app.services.registration_readiness_service import (
                merge_prep_courses_into_instance_context,
            )

            ctx_cs = await merge_prep_courses_into_instance_context(
                self.db,
                self._as_mapping(instance.context_data),
            )
            instance.context_data = ctx_cs
            flag_modified(instance, "context_data")

        # 6. Post-transition actions
        actions = _normalize_json_list(transition.actions)
        action_results = []
        if actions:
            from app.services.action_handler import ActionHandler
            handler = ActionHandler(self.db)
            action_results = await handler.handle_actions(actions, instance, payload or {})

        if instance.process_code == "therapy_session_reduction":
            ctx_tr = dict(self._as_mapping(instance.context_data))
            if transition.to_state_code == "violation_warning":
                ctx_tr["therapy_reduction_next_step_fa"] = (
                    "اگر می‌خواهید با وجود هشدار ادامه دهید، مرحلهٔ بعد را تأیید کنید؛ پس از آن کاهش در برنامه اعمال "
                    "می‌شود و در صورت نیاز فرایند ثبت تخلف نیز باز می‌شود."
                )
                instance.context_data = ctx_tr
                flag_modified(instance, "context_data")
            elif transition.to_state_code == "reduction_completed":
                ctx_tr["therapy_reduction_next_step_fa"] = (
                    "کاهش جلسات هفتگی در پرونده ثبت شد. جلسات انتخاب‌شده لغو شده‌اند. "
                    "برای پرداخت جلسات آتی در صورت نیاز از فرایند «پرداخت برای جلسات آتی درمان آموزشی» استفاده کنید."
                )
                instance.context_data = ctx_tr
                flag_modified(instance, "context_data")
            elif transition.to_state_code == "reduction_with_violation":
                vid = ctx_tr.get("violation_registration_instance_id")
                ctx_tr["therapy_reduction_next_step_fa"] = (
                    "کاهش با ثبت تخلف آموزشی ثبت شد. "
                    + (
                        f"فرایند «ثبت تخلف» باز شده است (شناسه: {vid}). در تب «فرایندها» آن را ببینید."
                        if vid
                        else "فرایند ثبت تخلف در سامانه باز شده است؛ در تب فرایندها پیگیری کنید."
                    )
                )
                instance.context_data = ctx_tr
                flag_modified(instance, "context_data")

        if instance.process_code == "fee_determination" and instance.is_completed:
            from app.services.fee_determination_runner import attach_fee_determination_completion_ui_hint

            await attach_fee_determination_completion_ui_hint(self.db, instance)

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

        await self._update_hidden_progress(instance, transition.to_state_code)

        if instance.process_code == "introductory_course_registration":
            try:
                from app.services.introductory_registration_chaining import (
                    chain_introductory_registration_after_transition,
                )

                await chain_introductory_registration_after_transition(
                    self.db,
                    self,
                    instance,
                    transition.to_state_code,
                    actor_id,
                )
                instance = await self.get_process_instance(instance_id)
            except Exception:
                logger.exception(
                    "introductory registration chain failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code == "lesson_start_per_term":
            try:
                from app.services.lesson_start_chaining import chain_lesson_start_after_transition

                await chain_lesson_start_after_transition(
                    self.db,
                    self,
                    instance,
                    transition.to_state_code,
                    actor_id,
                )
                instance = await self.get_process_instance(instance_id)
            except Exception:
                logger.exception(
                    "lesson_start chain failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code == "ta_track_change":
            try:
                from app.services.ta_track_change_chaining import chain_ta_track_change_after_transition

                await chain_ta_track_change_after_transition(
                    self.db,
                    self,
                    instance,
                    transition.to_state_code,
                    actor_id,
                )
                instance = await self.get_process_instance(instance_id)
            except Exception:
                logger.exception(
                    "ta_track_change chain failed (instance=%s)",
                    instance.id,
                )

        if (
            transition.to_state_code == "registration_complete"
            and instance.process_code == "introductory_course_registration"
            and instance.is_completed
        ):
            try:
                from app.services.student_service import StudentService

                await StudentService(self.db).maybe_start_followup_after_intro_registration(instance)
            except Exception:
                logger.exception(
                    "Follow-up after introductory registration_complete failed (instance=%s)",
                    instance.id,
                )

        if (
            transition.to_state_code == "therapy_active"
            and instance.process_code == "start_therapy"
            and instance.is_completed
        ):
            try:
                from app.services.student_service import StudentService

                await StudentService(self.db).maybe_start_session_payment_after_start_therapy(instance)
            except Exception:
                logger.exception(
                    "Follow-up after start_therapy therapy_active failed (instance=%s)",
                    instance.id,
                )

        if (
            transition.to_state_code == "therapy_completed"
            and instance.process_code == "return_to_full_education"
        ):
            try:
                from app.services.return_to_full_education_service import branch_after_therapy_payment

                actor = actor_id
                await branch_after_therapy_payment(self.db, self, instance, actor)
                instance = await self.get_process_instance(instance_id)
            except Exception:
                logger.exception(
                    "return_to_full_education branch after therapy failed (instance=%s)",
                    instance.id,
                )

        if (
            transition.to_state_code == "registration_unlocked"
            and instance.process_code == "return_to_full_education"
        ):
            try:
                from app.services.return_to_full_education_service import finalize_registration_unlock

                await finalize_registration_unlock(self.db, self, instance, actor_id)
                instance = await self.get_process_instance(instance_id)
            except Exception:
                logger.exception(
                    "return_to_full_education finalize failed (instance=%s)",
                    instance.id,
                )

        if (
            transition.to_state_code == "therapist_assignment"
            and instance.process_code == "full_education_leave"
        ):
            try:
                from app.services.full_education_leave_service import maybe_skip_therapist_assignment

                await maybe_skip_therapist_assignment(self.db, self, instance, actor_id)
                instance = await self.get_process_instance(instance_id)
            except Exception:
                logger.exception(
                    "full_education_leave therapist skip failed (instance=%s)",
                    instance.id,
                )

        if (
            transition.to_state_code == "payment_confirmed"
            and instance.process_code == "session_payment"
            and instance.is_completed
        ):
            try:
                from app.services.student_service import StudentService

                await StudentService(self.db).repoint_primary_after_session_payment_completed(instance)
            except Exception:
                logger.exception(
                    "repoint_primary_after_session_payment_completed failed (instance=%s)",
                    instance.id,
                )

        if (
            instance.process_code == "therapy_completion"
            and instance.is_completed
            and transition.to_state_code in ("therapy_completed", "conditions_not_met")
        ):
            try:
                from app.services.student_service import StudentService

                await StudentService(self.db).repoint_primary_after_therapy_completion_terminal(instance)
            except Exception:
                logger.exception(
                    "repoint_primary_after_therapy_completion_terminal failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code == "therapy_changes":
            try:
                from app.services.therapy_changes_chaining import propagate_therapy_changes_completed

                await propagate_therapy_changes_completed(
                    self.db, instance, transition.to_state_code
                )
            except Exception:
                logger.exception(
                    "therapy_changes parent propagation failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code == "student_non_registration":
            try:
                from app.services.student_non_registration_chaining import (
                    chain_student_non_registration_after_transition,
                )

                await chain_student_non_registration_after_transition(
                    self.db,
                    self,
                    instance,
                    transition.to_state_code,
                    actor_id,
                )
                instance = await self.get_process_instance(instance_id)
            except Exception:
                logger.exception(
                    "student_non_registration chain failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code == "intern_bulk_patient_referral":
            try:
                from app.services.intern_bulk_patient_referral_chaining import (
                    chain_intern_bulk_referral_after_transition,
                )

                await chain_intern_bulk_referral_after_transition(
                    self.db,
                    self,
                    instance,
                    transition.to_state_code,
                    actor_id,
                    payload,
                )
                instance = await self.get_process_instance(instance_id)
            except Exception:
                logger.exception(
                    "intern_bulk_patient_referral chain failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code == "ta_to_assistant_faculty":
            try:
                from app.services.ta_to_assistant_faculty_service import chain_after_transition

                await chain_after_transition(
                    self.db,
                    instance,
                    transition.to_state_code,
                )
            except Exception:
                logger.exception(
                    "ta_to_assistant_faculty chain failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code == "upgrade_to_ta":
            try:
                from app.services.ta_upgrade_service import chain_after_transition as ta_upgrade_chain

                await ta_upgrade_chain(
                    self.db,
                    instance,
                    transition.to_state_code,
                )
            except Exception:
                logger.exception(
                    "upgrade_to_ta chain failed (instance=%s)",
                    instance.id,
                )

        if instance.process_code in ("comprehensive_term_start", "intro_second_semester_registration"):
            try:
                from app.services.student_non_registration_chaining import (
                    maybe_advance_non_registration_on_term_registration,
                )

                await maybe_advance_non_registration_on_term_registration(
                    self.db, self, instance, actor_id,
                )
            except Exception:
                logger.exception(
                    "student_non_registration registration chain failed (instance=%s)",
                    instance.id,
                )

        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=transition.to_state_code,
            trigger_event=trigger_event,
            actions=actions,
            rule_results=rule_results,
        )

    async def _update_hidden_progress(self, instance: ProcessInstance, to_state: str) -> None:
        """Store lightweight gamification metrics in student.extra_data (hidden from default UI)."""
        stmt = select(Student).where(Student.id == instance.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return
        extra = dict(self._as_mapping(student.extra_data))
        hp = dict(self._as_mapping(extra.get("hidden_progress")))
        raw_map = hp.get("instances")
        instances_map = dict(raw_map) if isinstance(raw_map, dict) else {}
        iid = str(instance.id)
        cur_raw = instances_map.get(iid)
        cur = dict(cur_raw) if isinstance(cur_raw, dict) else {}
        cur["process_code"] = instance.process_code
        cur["transition_count"] = int(cur.get("transition_count", 0)) + 1
        cur["last_state"] = to_state
        cur["xp"] = int(cur.get("xp", 0)) + 15
        cur["updated_at"] = datetime.now(timezone.utc).isoformat()
        instances_map[iid] = cur
        hp["instances"] = instances_map
        hp["total_xp"] = sum(
            int(v.get("xp", 0)) for v in instances_map.values() if isinstance(v, dict)
        )
        extra["hidden_progress"] = hp
        student.extra_data = merge_gamification_into_extra(extra)
        flag_modified(student, "extra_data")

    # ─── Query Methods ──────────────────────────────────────────────

    async def _instance_has_registration_interview_booking(
        self,
        instance_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> bool:
        stmt = (
            select(InterviewSlot.id)
            .where(
                InterviewSlot.assigned_instance_id == instance_id,
                InterviewSlot.assigned_student_id == student_id,
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def get_available_transitions(
        self,
        instance_id: uuid.UUID,
        actor_role: str,
        actor_id: Optional[uuid.UUID] = None,
    ) -> list[dict]:
        """Get all transitions available from the current state for the given role."""
        instance = await self.get_process_instance(instance_id)
        process_def = await self.get_process_definition(instance.process_code)
        actor_user = await self.db.get(User, actor_id) if actor_id else None

        transitions = await self.transition_manager.find_transitions_for_state(
            process_id=process_def.id,
            from_state_code=instance.current_state_code,
        )

        if instance.process_code == "introductory_course_registration":
            from app.services.registration_readiness_service import check_intro_registration_gate

            gate = await check_intro_registration_gate(self.db)
            if not gate.allowed:
                return []

        portal_registration = actor_role in ("student", "applicant")
        has_booked_slot = False
        if portal_registration and (
            instance.process_code == "introductory_course_registration"
            and instance.current_state_code == "interview_scheduled"
        ):
            has_booked_slot = await self._instance_has_registration_interview_booking(
                instance.id, instance.student_id
            )

        available = []
        for t in transitions:
            if actor_role == "student" and t.trigger_event in STUDENT_FORBIDDEN_TRIGGER_EVENTS:
                continue
            if portal_registration and t.trigger_event in _REGISTRATION_INTERVIEW_BOOKING_TRIGGERS:
                continue
            if (
                portal_registration
                and t.trigger_event == "proceed_to_payment"
                and instance.process_code == "introductory_course_registration"
                and instance.current_state_code == "interview_scheduled"
                and not has_booked_slot
            ):
                continue
            if not self.transition_manager.validate_role(
                t, actor_role, trigger_event=t.trigger_event
            ):
                continue
            if actor_user and is_interview_result_trigger(t.trigger_event):
                allowed = await can_submit_interview_result(
                    self.db,
                    instance=instance,
                    user=actor_user,
                    trigger_event=t.trigger_event,
                )
                if not allowed:
                    continue
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

        ctx_out = self._as_mapping(instance.context_data)
        if instance.process_code == "session_payment":
            ctx_out = await self._merge_session_payment_financial_context(instance, ctx_out)
        if instance.process_code in (
            "introductory_course_registration",
            "comprehensive_course_registration",
        ):
            ctx_out = await self._merge_registration_payment_context_for_status(instance, ctx_out)
        if instance.process_code == "therapy_completion":
            try:
                fresh = await self._therapy_completion_resolved_fields(instance)
                ctx_out = {**ctx_out, **fresh}
            except Exception:
                logger.exception("therapy_completion fresh context for status failed (instance=%s)", instance.id)
        if instance.process_code == "therapy_session_reduction":
            try:
                ctx_out = await self._merge_therapy_session_reduction_instance_context(instance, ctx_out)
            except Exception:
                logger.exception(
                    "therapy_session_reduction context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "supervision_session_reduction":
            try:
                ctx_out = await self._merge_supervision_session_reduction_instance_context(instance, ctx_out)
            except Exception:
                logger.exception(
                    "supervision_session_reduction context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "student_session_cancellation":
            try:
                ctx_out = await self._merge_student_session_cancellation_context(instance, ctx_out)
            except Exception:
                logger.exception(
                    "student_session_cancellation context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "student_supervision_cancellation":
            try:
                ctx_out = await self._merge_student_supervision_cancellation_context(instance, ctx_out)
            except Exception:
                logger.exception(
                    "student_supervision_cancellation context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "supervisor_session_cancellation":
            try:
                ctx_out = await self._merge_supervisor_session_cancellation_context(instance, ctx_out)
            except Exception:
                logger.exception(
                    "supervisor_session_cancellation context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "class_session_cancellation":
            try:
                ctx_out = await self._merge_class_session_cancellation_context(instance, ctx_out)
            except Exception:
                logger.exception(
                    "class_session_cancellation context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "upgrade_to_educational_therapist":
            try:
                from app.services.educational_therapist_upgrade_service import build_et_upgrade_context

                et_ctx = await build_et_upgrade_context(
                    self.db, instance.student_id, ctx_out
                )
                ctx_out = {**ctx_out, **et_ctx}
            except Exception:
                logger.exception(
                    "upgrade_to_educational_therapist context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "upgrade_to_ta":
            try:
                from app.services.ta_upgrade_service import build_ta_upgrade_context

                ta_ctx = await build_ta_upgrade_context(
                    self.db, instance.student_id, ctx_out
                )
                ctx_out = {**ctx_out, **ta_ctx}
            except Exception:
                logger.exception(
                    "upgrade_to_ta context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "ta_track_change":
            try:
                from app.services.ta_track_change_service import build_ta_track_change_context

                ttc_ctx = await build_ta_track_change_context(
                    self.db, instance.student_id, ctx_out
                )
                ctx_out = {**ctx_out, **ttc_ctx}
            except Exception:
                logger.exception(
                    "ta_track_change context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "ta_to_assistant_faculty":
            try:
                from app.services.ta_to_assistant_faculty_service import build_ta_assistant_faculty_context

                taf_ctx = await build_ta_assistant_faculty_context(
                    self.db, instance.student_id, ctx_out
                )
                ctx_out = {**ctx_out, **taf_ctx}
            except Exception:
                logger.exception(
                    "ta_to_assistant_faculty context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "intern_bulk_patient_referral":
            try:
                ctx_out = self._merge_intern_bulk_patient_referral_context(ctx_out)
            except Exception:
                logger.exception(
                    "intern_bulk_patient_referral context for status failed (instance=%s)", instance.id
                )
        if instance.process_code == "thesis_defense_request":
            try:
                fresh = await self._thesis_defense_resolved_fields(instance)
                ctx_out = {**ctx_out, **fresh}
            except Exception:
                logger.exception(
                    "thesis_defense_request fresh context for status failed (instance=%s)", instance.id
                )

        student_extra_data = None
        if instance.process_code == "violation_registration" and instance.student_id:
            st_row = await self.db.get(Student, instance.student_id)
            if st_row and st_row.extra_data:
                extra = self._as_mapping(st_row.extra_data)
                student_extra_data = {
                    "monitoring_performance_log": extra.get("monitoring_performance_log") or [],
                }

        result = {
            "instance_id": str(instance.id),
            "process_code": instance.process_code,
            "current_state": instance.current_state_code,
            "is_completed": instance.is_completed,
            "is_cancelled": instance.is_cancelled,
            "context_data": ctx_out,
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
        if student_extra_data is not None:
            result["student_extra_data"] = student_extra_data
        return result

    async def rollback_to_previous_state(
        self,
        instance_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: str,
        reason: Optional[str] = None,
    ) -> TransitionResult:
        """
        بازگرداندن نمونه به وضعیت قبلی بر اساس آخرین رکورد تاریخچه (اصلاح اشتباه کلیک / تصمیم).
        رکورد جدید در state_history با trigger manual_rollback ثبت می‌شود.
        """
        instance = await self.get_process_instance(instance_id)
        if instance.is_cancelled:
            raise InvalidTransitionError("فرایند لغوشده قابل بازگشت نیست.")

        stmt = (
            select(StateHistory)
            .where(StateHistory.instance_id == instance_id)
            .order_by(StateHistory.entered_at)
        )
        result = await self.db.execute(stmt)
        history = list(result.scalars().all())

        if len(history) < 2:
            raise InvalidTransitionError("مرحلهٔ قبلی برای بازگشت وجود ندارد.")

        last = history[-1]
        if last.from_state_code is None:
            raise InvalidTransitionError("امکان بازگشت از وضعیت اولیهٔ فرایند نیست.")

        if last.to_state_code != instance.current_state_code:
            raise InvalidTransitionError(
                "وضعیت فعلی نمونه با آخرین رکورد تاریخچه هم‌خوان نیست؛ با پشتیبانی تماس بگیرید."
            )

        target_state = last.from_state_code
        from_current = instance.current_state_code
        now = datetime.now(timezone.utc)

        process_def = await self.get_process_definition(instance.process_code)
        is_target_terminal = await self.transition_manager.check_terminal_state(
            process_def.id, target_state
        )

        instance.current_state_code = target_state
        instance.last_transition_at = now
        instance.is_completed = bool(is_target_terminal)
        instance.completed_at = datetime.now(timezone.utc) if is_target_terminal else None

        ctx = dict(self._as_mapping(instance.context_data))
        log_entries = ctx.get("__rollback_log")
        if not isinstance(log_entries, list):
            log_entries = []
        log_entries.append(
            {
                "at": now.isoformat(),
                "from_state": from_current,
                "to_state": target_state,
                "reason": (reason or "").strip()[:2000],
                "actor_id": str(actor_id),
                "actor_role": actor_role,
            }
        )
        ctx["__rollback_log"] = log_entries

        # پاک‌سازی سبک دادهٔ نتیجهٔ مصاحبه هنگام برگشت از شاخهٔ نتیجه
        if from_current in (
            "result_conditional_therapy",
            "result_single_course",
            "result_full_admission",
            "rejected",
        ) or from_current.startswith("result_"):
            for k in (
                "interview_result",
                "allowed_course_count",
                "interviewer_notes",
                "result",
            ):
                ctx.pop(k, None)

        instance.context_data = ctx
        flag_modified(instance, "context_data")

        rb = StateHistory(
            id=uuid.uuid4(),
            instance_id=instance.id,
            from_state_code=from_current,
            to_state_code=target_state,
            trigger_event="manual_rollback",
            actor_id=actor_id,
            actor_role=actor_role,
            payload={"reason": reason} if reason else None,
            entered_at=now,
        )
        self.db.add(rb)

        await self.audit_logger.log_transition(
            instance_id=instance.id,
            process_code=instance.process_code,
            from_state=from_current,
            to_state=target_state,
            trigger_event="manual_rollback",
            actor_id=actor_id,
            actor_role=actor_role,
            payload={"reason": reason} if reason else None,
        )

        await event_bus.publish_transition(
            process_code=instance.process_code,
            instance_id=str(instance.id),
            from_state=from_current,
            to_state=target_state,
            trigger_event="manual_rollback",
            actor_id=str(actor_id),
            actions=[],
        )

        logger.info(
            "Rollback: %s [%s] --manual_rollback--> [%s] (instance=%s)",
            instance.process_code,
            from_current,
            target_state,
            instance.id,
        )

        return TransitionResult(
            success=True,
            from_state=from_current,
            to_state=target_state,
            trigger_event="manual_rollback",
            actions=[],
            rule_results=[],
        )

    async def restart_process_instance(
        self,
        instance_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: str,
        reason: Optional[str] = None,
        *,
        is_own_instance: bool = False,
    ) -> RestartProcessResult:
        """
        بایگانی نمونهٔ فعلی و ساخت نمونهٔ جدید از مرحلهٔ اول (شروع دوباره).
        """
        from app.meta.process_restart_policy import (
            build_restart_initial_context,
            can_actor_restart_process,
            student_restart_reason_required,
        )

        instance = await self.get_process_instance(instance_id)
        if instance.is_cancelled:
            raise InvalidTransitionError("این پرونده قبلاً بایگانی شده است؛ از منوی شروع فرایند استفاده کنید.")

        process_def = await self.get_process_definition(instance.process_code)
        process_config = self._as_mapping(process_def.config) if process_def.config else None

        allowed, deny_msg = can_actor_restart_process(
            actor_role=actor_role,
            process_code=instance.process_code,
            is_own_instance=is_own_instance,
            process_config=process_config,
        )
        if not allowed:
            role_norm = (actor_role or "").strip().lower()
            from app.meta.process_restart_policy import RESTART_STAFF_ROLES

            if role_norm == "student" and not is_own_instance:
                raise UnauthorizedError(deny_msg)
            if role_norm not in RESTART_STAFF_ROLES and role_norm != "student":
                raise UnauthorizedError(deny_msg)
            raise InvalidTransitionError(deny_msg)

        if student_restart_reason_required(actor_role) and not (reason or "").strip():
            raise InvalidTransitionError("لطفاً دلیل شروع دوباره را بنویسید.")

        now = datetime.now(timezone.utc)
        from_state = instance.current_state_code
        reason_clean = (reason or "").strip()[:2000]

        ctx = dict(self._as_mapping(instance.context_data))
        ctx["__archived_reason"] = "user_restart"
        ctx["__restarted_by"] = str(actor_id)
        ctx["__restarted_at"] = now.isoformat()
        if reason_clean:
            ctx["__restart_reason"] = reason_clean

        instance.is_cancelled = True
        instance.is_completed = False
        instance.completed_at = None
        instance.last_transition_at = now
        instance.context_data = ctx
        flag_modified(instance, "context_data")

        archive_history = StateHistory(
            id=uuid.uuid4(),
            instance_id=instance.id,
            from_state_code=from_state,
            to_state_code=from_state,
            trigger_event="process_restarted_archive",
            actor_id=actor_id,
            actor_role=actor_role,
            payload={"reason": reason_clean} if reason_clean else None,
            entered_at=now,
        )
        self.db.add(archive_history)

        await self.audit_logger.log(
            action_type="process_restart_archive",
            actor_id=actor_id,
            actor_role=actor_role,
            instance_id=instance.id,
            process_code=instance.process_code,
            from_state=from_state,
            to_state=from_state,
            trigger_event="process_restarted_archive",
            details={
                "reason": reason_clean,
                "archived_instance_id": str(instance.id),
            },
        )

        new_initial_context = build_restart_initial_context(
            old_context=ctx,
            old_instance_id=str(instance.id),
            process_config=process_config,
        )

        new_instance = await self.start_process(
            process_code=instance.process_code,
            student_id=instance.student_id,
            actor_id=actor_id,
            actor_role=actor_role,
            initial_context=new_initial_context,
        )

        await self.audit_logger.log(
            action_type="process_restart",
            actor_id=actor_id,
            actor_role=actor_role,
            instance_id=new_instance.id,
            process_code=instance.process_code,
            details={
                "reason": reason_clean,
                "old_instance_id": str(instance.id),
                "new_instance_id": str(new_instance.id),
            },
        )

        await event_bus.publish(Event(
            event_type=f"process.restarted.{instance.process_code}",
            payload={
                "old_instance_id": str(instance.id),
                "new_instance_id": str(new_instance.id),
                "process_code": instance.process_code,
                "student_id": str(instance.student_id),
                "actor_id": str(actor_id),
                "actor_role": actor_role,
                "reason": reason_clean,
            },
            source="state_machine_engine",
        ))

        logger.info(
            "Restart: %s archived instance=%s -> new instance=%s",
            instance.process_code,
            instance.id,
            new_instance.id,
        )

        return RestartProcessResult(
            success=True,
            old_instance_id=instance.id,
            new_instance_id=new_instance.id,
            process_code=instance.process_code,
            current_state=new_instance.current_state_code,
        )

    # ─── Internal Helpers ───────────────────────────────────────────

    @staticmethod
    def _as_mapping(val) -> dict:
        """JSONB / context payloads must be dicts for **unpacking; tolerate legacy str or bad rows."""
        if val is None:
            return {}
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    async def _merge_session_payment_financial_context(
        self, instance: ProcessInstance, merged: dict
    ) -> dict:
        """شمارش جلسات درمان بدون پرداخت از DB + پرچم تسویه از پرونده/فرم."""
        out = dict(merged)
        stmt = select(func.count()).select_from(TherapySession).where(
            TherapySession.student_id == instance.student_id,
            TherapySession.payment_status == "pending",
            TherapySession.status.in_(["scheduled", "completed"]),
        )
        r = await self.db.execute(stmt)
        out["debt_sessions_count"] = int(r.scalar() or 0)
        dsi = out.get("debt_settlement_included")
        if isinstance(dsi, str):
            out["debt_settlement_included"] = dsi.strip().lower() in ("1", "true", "yes", "on")
        elif dsi is None:
            out["debt_settlement_included"] = False
        else:
            out["debt_settlement_included"] = bool(dsi)
        try:
            from app.services.financial_program_defaults_service import get_effective_financial_program_defaults

            fd = await get_effective_financial_program_defaults(self.db)
            c = fd.get("class_session_fee_toman") or 0
            if float(c) > 0:
                out["reference_class_session_fee_toman"] = float(c)
            cr = fd.get("course_session_fee_toman") or 0
            if float(cr) > 0:
                out["reference_course_session_fee_toman"] = float(cr)
            th = fd.get("default_therapy_session_fee_toman") or 0
            if float(th) > 0:
                out["reference_therapy_session_fee_toman"] = float(th)
        except Exception:
            logger.exception("session_payment reference fee hints failed (instance=%s)", instance.id)
        return out

    @staticmethod
    def _apply_registration_payment_defaults_to_ctx(
        process_code: str,
        current_state: str,
        ctx: dict,
        *,
        registration_interview_fee_rial: int,
        registration_tuition_invoice_toman: float,
    ) -> Tuple[dict, bool]:
        """مبلغ پرداخت مصاحبه/شهریه اگر در context نباشد از پیش‌فرض‌های مالی سامانه پر می‌کند."""
        if process_code not in ("introductory_course_registration", "comprehensive_course_registration"):
            return ctx, False
        if current_state not in ("interview_payment", "payment"):
            return ctx, False

        def _valid_rial(v) -> bool:
            try:
                return int(v) >= 1000
            except (TypeError, ValueError):
                return False

        out = dict(ctx)
        changed = False
        if current_state == "interview_payment":
            if not _valid_rial(out.get("payment_amount_rial")):
                fee = int(registration_interview_fee_rial)
                out["payment_amount_rial"] = fee
                out["invoice_amount"] = float(fee) / 10.0
                changed = True
        elif current_state == "payment":
            if not _valid_rial(out.get("payment_amount_rial")):
                tom = float(registration_tuition_invoice_toman)
                out["invoice_amount"] = tom
                out["payment_amount_rial"] = int(round(tom * 10))
                changed = True
        return out, changed

    async def persist_registration_payment_defaults_if_needed(self, instance: ProcessInstance) -> bool:
        """پس از انتقال یا برای نمونهٔ قدیمی: ذخیرهٔ مبلغ در DB اگر خالی باشد."""
        from app.services.financial_program_defaults_service import get_effective_financial_program_defaults

        fd = await get_effective_financial_program_defaults(self.db)
        ctx = dict(self._as_mapping(instance.context_data))
        new_ctx, changed = self._apply_registration_payment_defaults_to_ctx(
            instance.process_code,
            instance.current_state_code,
            ctx,
            registration_interview_fee_rial=int(fd["registration_interview_fee_rial"]),
            registration_tuition_invoice_toman=float(fd["registration_tuition_invoice_toman"]),
        )
        if changed:
            instance.context_data = new_ctx
            flag_modified(instance, "context_data")
        return changed

    async def _merge_registration_payment_context_for_status(
        self, instance: ProcessInstance, merged: dict
    ) -> dict:
        """فقط برای پاسخ status/dashboard — بدون نوشتن DB."""
        from app.services.financial_program_defaults_service import get_effective_financial_program_defaults

        fd = await get_effective_financial_program_defaults(self.db)
        out, _ = self._apply_registration_payment_defaults_to_ctx(
            instance.process_code,
            instance.current_state_code,
            merged,
            registration_interview_fee_rial=int(fd["registration_interview_fee_rial"]),
            registration_tuition_invoice_toman=float(fd["registration_tuition_invoice_toman"]),
        )
        return out

    async def _merge_therapy_session_reduction_instance_context(
        self, instance: ProcessInstance, merged: dict
    ) -> dict:
        """ساعات/آستانه‌ها و لیست جلسات آتی برای فرم checkbox در پنل دانشجو."""
        out = dict(merged)
        stmt = select(Student).where(Student.id == instance.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return out
        extra = self._as_mapping(student.extra_data)
        att = AttendanceService(self.db)
        m = await att.get_therapy_completion_metrics(student.id)
        out.setdefault("therapy_hours_2x", float(m["therapy_hours_2x"]))
        out.setdefault("clinical_hours", float(m["clinical_hours"]))
        out.setdefault("supervision_hours", float(m["supervision_hours"]))
        out.setdefault("therapy_threshold", float(extra.get("therapy_threshold", 250)))
        out.setdefault("clinical_threshold", float(extra.get("clinical_threshold", 750)))
        out.setdefault("supervision_threshold", float(extra.get("supervision_threshold", 150)))
        out["student_weekly_sessions_before"] = int(student.weekly_sessions or 1)

        today = datetime.now(timezone.utc).date()
        sess_stmt = (
            select(TherapySession)
            .where(
                TherapySession.student_id == instance.student_id,
                TherapySession.session_date >= today,
                TherapySession.status == "scheduled",
                TherapySession.is_extra.is_(False),
            )
            .order_by(TherapySession.session_date.asc())
            .limit(80)
        )
        sr = await self.db.execute(sess_stmt)
        rows = list(sr.scalars().all())
        upcoming = [
            {
                "value": str(ts.id),
                "label_fa": f"{ts.session_date.isoformat()} — جلسهٔ درمان (برنامه‌ریزی‌شده)",
            }
            for ts in rows
        ]
        out["upcoming_therapy_sessions"] = upcoming
        ws = int(student.weekly_sessions or 1)
        # حداقل یک جلسه برای شروع کاهش؛ تطابق دقیق با «تعداد پس از کاهش» در سرور اعتبارسنجی می‌شود.
        out["therapy_reduction_min_remove_count"] = 1
        return out

    async def _merge_supervision_session_reduction_instance_context(
        self, instance: ProcessInstance, merged: dict
    ) -> dict:
        """ساعات/آستانه‌ها و لیست جلسات هفتگی سوپرویژن برای فرم checkbox در پنل دانشجو."""
        out = dict(merged)
        stmt = select(Student).where(Student.id == instance.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return out
        extra = self._as_mapping(student.extra_data)
        att = AttendanceService(self.db)
        m = await att.get_therapy_completion_metrics(student.id)
        out.setdefault("therapy_hours_2x", float(m["therapy_hours_2x"]))
        out.setdefault("clinical_hours", float(m["clinical_hours"]))
        out.setdefault("supervision_hours", float(m["supervision_hours"]))
        out.setdefault("therapy_threshold", float(extra.get("therapy_threshold", 250)))
        out.setdefault("clinical_threshold", float(extra.get("clinical_threshold", 750)))
        out.setdefault("supervision_threshold", float(extra.get("supervision_threshold", 150)))

        sup_weekly = out.get("supervision_weekly_sessions")
        if sup_weekly is None:
            sup_weekly = extra.get("supervision_weekly_sessions") or extra.get("weekly_supervision_sessions")
        try:
            ws = int(sup_weekly) if sup_weekly is not None else 1
        except (TypeError, ValueError):
            ws = 1
        out["supervision_weekly_sessions"] = ws

        lms = self._as_mapping(extra.get("lms"))
        slots_raw = lms.get("supervision_weekly_slots")
        upcoming: list[dict] = []
        if isinstance(slots_raw, list) and slots_raw:
            for i, slot in enumerate(slots_raw):
                if isinstance(slot, dict):
                    val = slot.get("id") or slot.get("value") or f"slot_{i + 1}"
                    label = slot.get("label_fa") or slot.get("label") or str(val)
                else:
                    val = f"slot_{i + 1}"
                    label = str(slot)
                upcoming.append({"value": str(val), "label_fa": str(label)})
        else:
            default_days = ["دوشنبه", "چهارشنبه", "شنبه", "یکشنبه", "سه‌شنبه"]
            default_times = ["10:00", "14:30", "16:00", "18:00", "11:00"]
            for i in range(max(1, ws)):
                day = default_days[i % len(default_days)]
                tm = default_times[i % len(default_times)]
                upcoming.append({
                    "value": f"slot_{i + 1}",
                    "label_fa": f"{day} — ساعت {tm} (جلسهٔ سوپرویژن هفتگی {i + 1})",
                })

        out["upcoming_supervision_sessions"] = upcoming
        max_remove = max(0, ws - 1)
        out["supervision_reduction_max_remove_count"] = max_remove
        out["supervision_reduction_min_remove_count"] = 1 if max_remove > 0 else 0
        return out

    @staticmethod
    def _merge_intern_bulk_patient_referral_context(merged: dict) -> dict:
        """اطمینان از وجود patient_referral_rows در context برای prefill فرم‌ها."""
        out = dict(merged)
        rows = out.get("patient_referral_rows")
        if not isinstance(rows, list):
            out["patient_referral_rows"] = []
        return out

    async def _merge_student_session_cancellation_context(
        self, instance: ProcessInstance, merged: dict
    ) -> dict:
        from app.services.student_session_cancellation_service import build_student_cancellation_context

        out = dict(merged)
        selected = out.get("selected_sessions")
        if not selected and isinstance(out.get("payload"), dict):
            selected = out["payload"].get("selected_sessions")
        extra = await build_student_cancellation_context(
            self.db,
            instance.student_id,
            selected_sessions_raw=selected,
            display_weeks=3,
        )
        out.update(extra)
        return out

    async def _merge_student_supervision_cancellation_context(
        self, instance: ProcessInstance, merged: dict
    ) -> dict:
        from app.services.student_supervision_cancellation_service import (
            build_student_supervision_cancellation_context,
        )

        out = dict(merged)
        selected = out.get("selected_sessions")
        if not selected and isinstance(out.get("payload"), dict):
            selected = out["payload"].get("selected_sessions")
        extra = await build_student_supervision_cancellation_context(
            self.db,
            instance.student_id,
            selected_sessions_raw=selected,
            display_weeks=3,
        )
        out.update(extra)
        return out

    async def _merge_supervisor_session_cancellation_context(
        self, instance: ProcessInstance, merged: dict
    ) -> dict:
        from app.services.supervisor_session_cancellation_service import (
            build_supervisor_cancellation_context,
        )

        out = dict(merged)
        extra = await build_supervisor_cancellation_context(self.db, instance)
        out.update(extra)
        return out

    async def _merge_class_session_cancellation_context(
        self, instance: ProcessInstance, merged: dict
    ) -> dict:
        from app.services.class_session_cancellation_service import (
            build_class_session_cancellation_context,
        )

        out = dict(merged)
        extra = await build_class_session_cancellation_context(
            self.db,
            None,
            out,
            student=await self.db.get(Student, instance.student_id),
        )
        out.update(extra)
        return out

    async def _therapy_completion_default_thresholds(self, process_def: ProcessDefinition) -> dict:
        cfg = self._as_mapping(process_def.config)
        d = cfg.get("default_thresholds") or {}
        return {
            "therapy_hours": float(d.get("therapy_hours") or 250),
            "clinical_hours": float(d.get("clinical_hours") or 750),
            "supervision_hours": float(d.get("supervision_hours") or 150),
        }

    async def _therapy_completion_resolved_fields(self, instance: ProcessInstance) -> dict:
        """مقادیر ساعات و آستانه‌ها برای قوانین therapy_completion و نمایش در پنل."""
        process_def = await self.get_process_definition(instance.process_code)
        defaults = await self._therapy_completion_default_thresholds(process_def)
        stmt = select(Student).where(Student.id == instance.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        extra = self._as_mapping(student.extra_data) if student else {}
        ov = self._as_mapping(extra.get("therapy_completion_threshold_overrides"))

        def _thr(ov_key: str, def_key: str) -> float:
            v = ov.get(ov_key)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
            return float(defaults.get(def_key) or 0)

        therapy_threshold = _thr("therapy_threshold", "therapy_hours")
        clinical_threshold = _thr("clinical_threshold", "clinical_hours")
        supervision_threshold = _thr("supervision_threshold", "supervision_hours")

        attendance = AttendanceService(self.db)
        m = await attendance.get_therapy_completion_metrics(instance.student_id)
        th = float(m["therapy_hours_2x"])
        ch = float(m["clinical_hours"])
        sh = float(m["supervision_hours"])

        preview_fa = (
            f"وضعیت ساعات (ایست بازرسی خاتمه): درمان آموزشی {th:g} از {therapy_threshold:g}؛ "
            f"تجربه بالینی {ch:g} از {clinical_threshold:g}؛ "
            f"سوپرویژن {sh:g} از {supervision_threshold:g}."
        )

        return {
            "therapy_hours_2x": th,
            "clinical_hours": ch,
            "supervision_hours": sh,
            "therapy_threshold": therapy_threshold,
            "clinical_threshold": clinical_threshold,
            "supervision_threshold": supervision_threshold,
            "therapy_hours": th,
            "therapy_completion_preview_fa": preview_fa,
        }

    async def _thesis_defense_resolved_fields(self, instance: ProcessInstance) -> dict:
        """شروط چهارگانه دفاع پایان‌نامه — برای قوانین و UI."""
        from app.services.thesis_defense_eligibility_service import (
            build_thesis_defense_eligibility_context,
        )

        return await build_thesis_defense_eligibility_context(self.db, instance.student_id)

    async def _persist_therapy_completion_snapshot(self, instance: ProcessInstance) -> None:
        """ذخیرهٔ snapshot روی context_data برای اعلان‌ها و UI."""
        fields = await self._therapy_completion_resolved_fields(instance)
        ctx = dict(self._as_mapping(instance.context_data))
        ctx.update(fields)
        if instance.current_state_code == "therapy_completed":
            ctx["therapy_completion_next_step_fa"] = (
                "درمان آموزشی شما در پرونده به‌عنوان «خاتمه‌یافته» ثبت شد. ادامهٔ مسیر آموزشی "
                "(سوپرویژن، دروس، کارورزی) را از داشبورد و فازهای مربوط پیگیری کنید."
            )
        elif instance.current_state_code == "conditions_not_met":
            ctx["therapy_completion_next_step_fa"] = (
                "حداقل یکی از حدنصاب‌های لازم برای خاتمهٔ رسمی هنوز کامل نیست. پس از تکمیل ساعات درمان، "
                "بالینی و سوپرویژن طبق اعلام انستیتو، می‌توانید دوباره همین فرایند را اجرا کنید."
            )
        instance.context_data = ctx
        flag_modified(instance, "context_data")

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
                "student_id": str(instance.student_id),
                "process_code": instance.process_code,
                "current_state": instance.current_state_code,
                **self._as_mapping(instance.context_data),
            },
            "student": {},
            "payload": payload if isinstance(payload, dict) else {},
        }

        if student:
            extra = self._as_mapping(student.extra_data)
            context["student"] = {
                "id": str(student.id),
                "student_code": student.student_code,
                "course_type": student.course_type,
                "is_intern": student.is_intern,
                "term_count": student.term_count,
                "current_term": student.current_term,
                "therapy_started": student.therapy_started,
                "weekly_sessions": student.weekly_sessions,
                **extra,
            }

            # Enrich instance for rules: absence quota, absences this year, completed/required hours,
            # current_week (week_9_deadline), hours_until_first_slot (24_hour_rule) — BUILD_TODO § د
            attendance = AttendanceService(self.db)
            shamsi_year = get_current_shamsi_year()
            context["instance"]["current_shamsi_year"] = shamsi_year
            context["instance"]["absence_quota"] = await attendance.calculate_absence_quota(student.id)
            context["instance"]["absences_this_year"] = await attendance.get_absence_count(
                student.id, shamsi_year=shamsi_year, status_filter="absent_unexcused"
            )
            hours_info = await attendance.get_completed_hours(student.id)
            context["instance"]["completed_hours"] = hours_info["total_hours"]
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

            # weeks_since_term_start — فرایند ۴۲ و قانون within_4_weeks_of_term_start
            term_start_for_weeks = None
            if extra.get("term_start_date"):
                try:
                    term_start_for_weeks = date.fromisoformat(str(extra["term_start_date"])[:10])
                except (TypeError, ValueError):
                    pass
            if term_start_for_weeks is not None:
                delta_days = (date.today() - term_start_for_weeks).days
                context["instance"]["weeks_since_term_start"] = max(0, delta_days // 7)

        # تاریخ امروز (UTC) برای قوانین مقایسهٔ سررسید اقساط و مشابه
        context["instance"]["calendar_today"] = datetime.now(timezone.utc).date().isoformat()

        # دادهٔ همین ترنزیشن (مثلاً interview_result) در payload است؛ قوانین با مسیر instance.* ارزیابی می‌شوند
        # و context_data تا بعد از موفقیت ترنزیشن ذخیره نمی‌شود — بدون این ادغام، شرط‌های نتیجهٔ مصاحبه همیشه fail می‌شوند.
        if payload and isinstance(payload, dict):
            context["instance"].update(payload)

        if instance.process_code == "theory_course_completion" and payload and isinstance(payload, dict):
            from app.services.theory_course_completion_service import enrich_transition_context

            enrich_transition_context(context["instance"], payload)

        # introductory_course_registration: چهار شاخه با یک trigger — اگر UI فقط to_state بفرستد
        if (
            instance.process_code == "introductory_course_registration"
            and instance.current_state_code == "interview_completed"
        ):
            _branch_to_interview = {
                "result_conditional_therapy": "conditional_therapy",
                "result_single_course": "single_course",
                "result_full_admission": "full_admission",
                "rejected": "rejected",
            }
            ts = None
            if isinstance(payload, dict):
                ts = payload.get("to_state") or payload.get("target_to_state")
            if not ts:
                ts = context["instance"].get("to_state")
            inferred = _branch_to_interview.get(ts) if ts else None
            if inferred:
                context["instance"]["interview_result"] = inferred

        # قوانین مثل schedule_valid_for_course از instance.weekly_sessions استفاده می‌کنند؛
        # مقدار پیش‌فرض روی student است نه context_data — بدون این، None >= int خطا می‌دهد.
        if student and context["instance"].get("weekly_sessions") is None:
            context["instance"]["weekly_sessions"] = student.weekly_sessions
        ws_inst = context["instance"].get("weekly_sessions")
        if isinstance(ws_inst, str):
            s = ws_inst.strip()
            if s.isdigit():
                try:
                    context["instance"]["weekly_sessions"] = int(s)
                except (TypeError, ValueError):
                    pass

        # session_payment: بدهی از روی جلسات واقعی + پرچم تسویه از فرم/پرونده
        if instance.process_code == "session_payment":
            context["instance"] = await self._merge_session_payment_financial_context(
                instance, context["instance"]
            )

        if instance.process_code == "therapy_completion":
            tc = await self._therapy_completion_resolved_fields(instance)
            context["instance"].update(tc)

        if instance.process_code == "student_session_cancellation":
            from app.services.student_session_cancellation_service import build_student_cancellation_context

            sel = context["instance"].get("selected_sessions")
            if not sel and isinstance(payload, dict):
                sel = payload.get("selected_sessions")
            sc_ctx = await build_student_cancellation_context(
                self.db,
                instance.student_id,
                selected_sessions_raw=sel,
                display_weeks=3,
            )
            context["instance"].update(sc_ctx)

        if instance.process_code == "student_supervision_cancellation":
            from app.services.student_supervision_cancellation_service import (
                build_student_supervision_cancellation_context,
            )

            sel = context["instance"].get("selected_sessions")
            if not sel and isinstance(payload, dict):
                sel = payload.get("selected_sessions")
            ssc_ctx = await build_student_supervision_cancellation_context(
                self.db,
                instance.student_id,
                selected_sessions_raw=sel,
                display_weeks=3,
            )
            context["instance"].update(ssc_ctx)

        if instance.process_code == "supervisor_session_cancellation":
            from app.services.supervisor_session_cancellation_service import (
                build_supervisor_cancellation_context,
            )

            scc_ctx = await build_supervisor_cancellation_context(self.db, instance)
            context["instance"].update(scc_ctx)

        if instance.process_code == "attendance_tracking":
            inst = context["instance"]
            raw_sid = inst.get("therapy_session_id") or inst.get("session_id")
            if raw_sid:
                try:
                    suid = uuid.UUID(str(raw_sid))
                except (TypeError, ValueError):
                    suid = None
                if suid:
                    ts_row = await self.db.get(TherapySession, suid)
                    if ts_row:
                        inst["session_paid"] = ts_row.payment_status in ("paid", "waived")
                        inst["session_cancelled"] = ts_row.status == "cancelled"
                        inst["session_date"] = ts_row.session_date.isoformat()
            if student:
                stmt_lv = select(ProcessInstance).where(
                    ProcessInstance.student_id == student.id,
                    ProcessInstance.process_code == "educational_leave",
                    ProcessInstance.current_state_code.in_(["on_leave", "return_reminder_sent"]),
                    ProcessInstance.is_completed == False,
                    ProcessInstance.is_cancelled == False,
                )
                rlv = await self.db.execute(stmt_lv)
                inst["student_on_leave"] = rlv.scalars().first() is not None

        # fee_determination: قوانین session_paid؛ برای سوپرویژن supervision_session_paid را هم‌راستا کن
        if instance.process_code == "fee_determination":
            inst = context["instance"]
            if inst.get("session_paid") is None and inst.get("supervision_session_paid") is not None:
                inst["session_paid"] = bool(inst.get("supervision_session_paid"))
            if inst.get("context") == "supervision" and inst.get("session_paid") is None:
                sp = inst.get("supervision_session_paid")
                if sp is not None:
                    inst["session_paid"] = bool(sp)

        if instance.process_code == "upgrade_to_educational_therapist":
            from app.services.educational_therapist_upgrade_service import build_et_upgrade_context

            et_ctx = await build_et_upgrade_context(
                self.db,
                instance.student_id,
                context["instance"],
            )
            context["instance"].update(et_ctx)

        if instance.process_code == "upgrade_to_ta":
            from app.services.ta_upgrade_service import build_ta_upgrade_context

            ta_ctx = await build_ta_upgrade_context(
                self.db,
                instance.student_id,
                context["instance"],
            )
            context["instance"].update(ta_ctx)

        if instance.process_code == "ta_to_assistant_faculty":
            from app.services.ta_to_assistant_faculty_service import build_ta_assistant_faculty_context

            taf_ctx = await build_ta_assistant_faculty_context(
                self.db,
                instance.student_id,
                context["instance"],
            )
            context["instance"].update(taf_ctx)

        if instance.process_code == "thesis_defense_request":
            td_ctx = await self._thesis_defense_resolved_fields(instance)
            context["instance"].update(td_ctx)

        return context
