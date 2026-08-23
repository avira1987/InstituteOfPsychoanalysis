"""Starting sub-processes and seeding their initial context.

Part of the ActionHandler split. Every method below runs as a mixin method
on ActionHandler, so `self` exposes the whole handler surface.
"""

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from datetime import datetime, timezone, date, timedelta
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, Any, List
import uuid

from app.services.actions._shared import (
    _as_mapping,
)


class ProcessControlActionsMixin:
    """Starting sub-processes and seeding their initial context."""

    def _eval_start_process_run_if(self, action: dict, instance: ProcessInstance, transition_context: dict) -> bool:
        code = action.get("run_if")
        if not code:
            return True
        merged = {**_as_mapping(instance.context_data), **(transition_context or {})}
        if code == "session_not_cancelled":
            return merged.get("session_cancelled") is not True
        return True

    @staticmethod
    def _notification_action_condition_matches(action: dict, notif_context: dict) -> bool:
        raw = (action.get("condition") or "").strip()
        if not raw:
            return True
        if "==" not in raw:
            return True
        left, right = raw.split("==", 1)
        key = left.strip()
        expect = right.strip().strip("'").strip('"')
        return str(notif_context.get(key)) == str(expect)

    async def _merge_fee_determination_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        from app.services.fee_determination_runner import enrich_fee_determination_payload_from_therapy_session

        merged = dict(base or {})
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        for key in (
            "session_paid",
            "supervision_session_paid",
            "student_on_leave",
            "session_cancelled",
            "cancelled_by",
            "context",
            "reason",
            "therapy_session_id",
            "session_id",
        ):
            if key in pctx and merged.get(key) is None:
                merged[key] = pctx[key]
        for key in ("session_paid", "student_on_leave", "therapy_session_id", "selected_sessions"):
            if key in tc and merged.get(key) is None:
                merged[key] = tc[key]
        if merged.get("context") == "supervision" or merged.get("supervision_session_paid") is not None:
            if merged.get("session_paid") is None and merged.get("supervision_session_paid") is not None:
                merged["session_paid"] = bool(merged.get("supervision_session_paid"))
        merged["parent_instance_id"] = str(parent.id)
        merged = await enrich_fee_determination_payload_from_therapy_session(
            self.db, parent.student_id, merged
        )
        return merged

    async def _merge_committees_review_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        """زمینهٔ اولیهٔ زیرفرایند ب — علت درمانگر و مسیر ورود از والد."""
        merged = dict(base or {})
        merged["parent_instance_id"] = str(parent.id)
        merged["parent_process_code"] = parent.process_code
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        for key in (
            "reason",
            "label",
            "reason_code",
            "termination_reason_code",
            "termination_note",
            "commission_opinion_fa",
            "commission_meeting_notes_fa",
            "therapist_id",
        ):
            if pctx.get(key) is not None and merged.get(key) is None:
                merged[key] = pctx[key]
        if parent.process_code == "specialized_commission_review":
            merged.setdefault("entry_reason", "ineligibility_specialized_commission")
            gp_raw = pctx.get("parent_instance_id")
            if gp_raw:
                try:
                    gp = await self.db.get(ProcessInstance, uuid.UUID(str(gp_raw)))
                except (ValueError, TypeError):
                    gp = None
                if gp:
                    gctx = _as_mapping(gp.context_data)
                    for key in ("termination_reason_code", "termination_note", "reason_code"):
                        if gctx.get(key) is not None and merged.get(key) is None:
                            merged[key] = gctx[key]
                    merged["grandparent_process_code"] = gp.process_code
        elif parent.process_code == "therapy_early_termination":
            merged.setdefault("entry_reason", "termination_reason_4")
            if merged.get("termination_reason_code") is None:
                merged["termination_reason_code"] = (
                    pctx.get("termination_reason_code") or pctx.get("reason_code") or 4
                )
        for key, val in tc.items():
            if merged.get(key) is None and val is not None:
                merged[key] = val
        return merged

    async def _merge_commission_review_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        """زمینهٔ اولیهٔ زیرفرایند الف از فرایند قطع زودرس."""
        merged = dict(base or {})
        merged["parent_instance_id"] = str(parent.id)
        merged["parent_process_code"] = parent.process_code
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        for key in ("termination_reason_code", "termination_note", "reason_code", "therapist_id"):
            if pctx.get(key) is not None and merged.get(key) is None:
                merged[key] = pctx[key]
        for key, val in tc.items():
            if merged.get(key) is None and val is not None:
                merged[key] = val
        return merged

    async def _merge_violation_registration_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        """زمینهٔ اولیهٔ فرایند ثبت تخلف از فرایند مبدأ."""
        merged = dict(base or {})
        merged["parent_instance_id"] = str(parent.id)
        merged["source_process_code"] = parent.process_code
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        reason = merged.get("reason") or pctx.get("reason") or pctx.get("reason_code")
        if reason is not None:
            merged.setdefault("source_reason", str(reason))
        for key in (
            "description",
            "violation_description",
            "termination_note",
            "occurrence_date",
            "reporter_name",
            "title_fa",
        ):
            if pctx.get(key) is not None and merged.get(key) is None:
                merged[key] = pctx[key]
        if merged.get("description") is None and merged.get("violation_description"):
            merged["description"] = merged["violation_description"]
        for key, val in tc.items():
            if merged.get(key) is None and val is not None:
                merged[key] = val
        if merged.get("description") is None:
            title = merged.get("title_fa")
            if title:
                merged["description"] = str(title)
            elif merged.get("source_reason"):
                merged["description"] = str(merged["source_reason"])
        if merged.get("source_reason") is None and merged.get("reason") is not None:
            merged["source_reason"] = str(merged["reason"])
        merged["violation_reported_at"] = datetime.now(timezone.utc).isoformat()
        return merged

    async def _merge_patient_referral_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        """زمینهٔ اولیهٔ هاب ارجاع بیمار از مرخصی/وقفه."""
        merged = dict(base or {})
        merged["parent_instance_id"] = str(parent.id)
        merged["source_process_code"] = parent.process_code
        merged["student_id"] = str(parent.student_id)
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        for key in ("leave_terms", "reason", "source_reason"):
            if merged.get(key) is None:
                if pctx.get(key) is not None:
                    merged[key] = pctx[key]
                elif tc.get(key) is not None:
                    merged[key] = tc[key]
        if merged.get("leave_terms") is not None:
            try:
                merged["leave_terms"] = int(merged["leave_terms"])
            except (TypeError, ValueError):
                pass
        reason = merged.get("reason") or merged.get("source_reason")
        if reason is not None:
            merged.setdefault("source_reason", str(reason))
        if merged.get("source_reason") is None and parent.process_code == "educational_leave":
            merged["source_reason"] = "educational_leave_intern_2term"
            merged.setdefault("reason", "educational_leave_intern_2term")
        from app.services.hub_patient_referral import normalize_referral_patients

        rows = normalize_referral_patients(
            merged.get("referral_patients") or pctx.get("referral_patients")
        )
        merged["referral_patients"] = rows
        return merged

    async def _handle_persist_patient_referral_rows(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        from app.services.hub_patient_referral import normalize_referral_patients

        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        rows = normalize_referral_patients(
            ctx.get("referral_patients") or ctx.get("patient_referral_rows")
        )
        stored = _as_mapping(instance.context_data)
        stored["referral_patients"] = rows
        instance.context_data = stored
        flag_modified(instance, "context_data")
        return f"referral_patients={len(rows)}"

    async def _handle_close_patient_referral_hub(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        if instance.process_code != "patient_referral":
            return "skipped_not_patient_referral"
        if instance.current_state_code != "notifications_sent":
            return f"skipped_state={instance.current_state_code}"
        from app.core.engine import StateMachineEngine
        from app.services.fee_determination_runner import SYSTEM_ACTOR_ID

        engine = StateMachineEngine(self.db)
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="closed",
            actor_id=SYSTEM_ACTOR_ID,
            actor_role="system",
        )
        return f"patient_referral_closed success={result.success} err={result.error}"

    async def _handle_start_process(self, action: dict, instance: ProcessInstance, context: dict):
        from app.core.engine import StateMachineEngine
        from app.services.fee_determination_runner import complete_fee_determination_instance

        sub_code = action.get("process_code", "")
        if action.get("run_if_intern"):
            st = await self._get_student(instance.student_id)
            if not st or not getattr(st, "is_intern", False):
                return f"sub_process_skipped run_if_intern ({sub_code})"

        if not self._eval_start_process_run_if(action, instance, context or {}):
            return f"sub_process_skipped run_if ({sub_code})"

        engine = StateMachineEngine(self.db)
        actor_id = instance.started_by or instance.student_id
        base_payload = dict(action.get("payload") or {})
        base_payload["parent_instance_id"] = str(instance.id)

        payloads: list[dict] = []
        if sub_code == "fee_determination" and action.get("run_for_each_session"):
            pctx = _as_mapping(instance.context_data)
            tc = context or {}
            sessions = pctx.get("selected_sessions") or tc.get("selected_sessions") or []
            if not sessions:
                payloads.append(
                    await self._merge_fee_determination_initial_payload(instance, base_payload, context)
                )
            else:
                for item in sessions:
                    unit = dict(base_payload)
                    if isinstance(item, dict):
                        unit.update(item)
                    else:
                        unit["therapy_session_id"] = str(item)
                    payloads.append(
                        await self._merge_fee_determination_initial_payload(instance, unit, context)
                    )
        else:
            if sub_code == "fee_determination":
                payloads.append(
                    await self._merge_fee_determination_initial_payload(instance, base_payload, context)
                )
            elif sub_code == "committees_review":
                payloads.append(
                    await self._merge_committees_review_initial_payload(instance, base_payload, context)
                )
            elif sub_code == "specialized_commission_review":
                payloads.append(
                    await self._merge_commission_review_initial_payload(instance, base_payload, context)
                )
            elif sub_code == "violation_registration":
                payloads.append(
                    await self._merge_violation_registration_initial_payload(
                        instance, base_payload, context
                    )
                )
            elif sub_code == "patient_referral":
                payloads.append(
                    await self._merge_patient_referral_initial_payload(
                        instance, base_payload, context
                    )
                )
            else:
                payloads.append(base_payload)

        ids: list[str] = []
        for payload in payloads:
            sub_instance = await engine.start_process(
                process_code=sub_code,
                student_id=instance.student_id,
                actor_id=actor_id,
                actor_role="system",
                initial_context=payload,
            )
            await self.db.flush()
            if sub_code == "fee_determination":
                await complete_fee_determination_instance(self.db, sub_instance.id)
            ids.append(str(sub_instance.id))
        if ids:
            pctx = _as_mapping(instance.context_data)
            pctx["last_child_process_code"] = sub_code
            pctx["last_child_process_instance_id"] = ids[-1]
            if sub_code == "violation_registration":
                pctx["violation_registration_instance_id"] = ids[-1]
            if sub_code == "patient_referral":
                pctx["patient_referral_instance_id"] = ids[-1]
            instance.context_data = pctx
            flag_modified(instance, "context_data")
        return f"sub_process={sub_code}, sub_instances={','.join(ids)}"

    async def _handle_start_sub_process(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """BPMS-style spelling used by the course-completion processes.

        Identical semantics to ``start_process``; the only difference is that the
        target is named ``sub_process_code``.
        """
        sub_code = action.get("sub_process_code") or action.get("process_code") or ""
        if not sub_code:
            raise ValueError("start_sub_process requires 'sub_process_code'")
        normalized = {**action, "type": "start_process", "process_code": sub_code}
        return await self._handle_start_process(normalized, instance, context)


# action type -> handler; merged into ActionHandler._registry
REGISTRY = {
    'start_process': ProcessControlActionsMixin._handle_start_process,
    'start_sub_process': ProcessControlActionsMixin._handle_start_sub_process,
    'persist_patient_referral_rows': ProcessControlActionsMixin._handle_persist_patient_referral_rows,
    'close_patient_referral_hub': ProcessControlActionsMixin._handle_close_patient_referral_hub,
}
