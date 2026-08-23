"""Supervision blocks, supervisor slots and committee records.

Part of the ActionHandler split. Every method below runs as a mixin method
on ActionHandler, so `self` exposes the whole handler surface.
"""

from app.config import get_settings
from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from app.services.alocom_client import AlocomAPIError
from app.services.alocom_provision import provision_therapy_session_alocom
from app.services.workflow import (
    portal_notifications as _svc_portal,
    lms_service as _svc_lms,
    document_service as _svc_document,
    evaluation_records as _svc_evaluation,
    capacity_service as _svc_capacity,
    termination_records as _svc_termination,
    calendar_service as _svc_calendar,
    registration_gate as _svc_gate,
    role_promotion as _svc_role,
)
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, Any, List
import uuid

from app.services.actions._shared import (
    _as_mapping,
    logger,
)


class SupervisionActionsMixin:
    """Supervision blocks, supervisor slots and committee records."""

    async def _handle_send_reminder(self, action: dict, instance: ProcessInstance, context: dict):
        await self._handle_notification(
            {
                "notification_type": action.get("notification_type", "sms"),
                "template": action.get("template", "supervision_45_48_reminder"),
                "recipients": action.get("recipients", ["student", "supervisor"]),
            },
            instance,
            context,
        )
        ctx = _as_mapping(instance.context_data)
        ctx["reminder_45_48_sent_at"] = datetime.now(timezone.utc).isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "45_48_reminder_sent_if_applicable"

    async def _handle_unlock_payment_50th(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if student:
            extra = _as_mapping(student.extra_data)
            extra["payment_unlocked_for_50th_session"] = True
            student.extra_data = extra
            flag_modified(student, "extra_data")
        ctx = _as_mapping(instance.context_data)
        ctx["payment_unlocked_for_50th_session"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "payment_unlocked_for_50th_session"

    async def _handle_display_supervision_history(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        ctx = _as_mapping(instance.context_data)
        blocks = []
        attendance = ctx.get("current_supervision_block_attendance")
        if student:
            extra = _as_mapping(student.extra_data)
            lms = _as_mapping(extra.get("lms"))
            blocks = list(lms.get("supervision_blocks") or [])
            if attendance is None:
                active = next(
                    (b for b in blocks if isinstance(b, dict) and b.get("status") == "active"),
                    blocks[-1] if blocks else None,
                )
                if isinstance(active, dict) and active.get("hours") is not None:
                    try:
                        attendance = int(active.get("hours") or 0)
                    except (TypeError, ValueError):
                        attendance = 0
                elif ctx.get("current_supervision_block_attendance") is None:
                    attendance = int(extra.get("supervision_block_attendance") or lms.get("current_block_hours") or 0)
        ctx["supervision_history"] = blocks
        ctx["supervision_blocks"] = blocks
        if attendance is not None:
            ctx["current_supervision_block_attendance"] = int(attendance)
        ctx.setdefault("ui_hints", []).append({"action": "display_supervision_history", "payload": {}})
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"supervision_history_displayed n={len(blocks)}"

    async def _handle_display_available_supervisor_slots(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        from app.services.educational_therapist_slot_service import list_available_grouped_by_supervisor
        from app.services.workflow import portal_notifications as _svc_portal

        student = await self._get_student(instance.student_id)
        course_type = (student.course_type if student else None) or "introductory"
        grouped = await list_available_grouped_by_supervisor(self.db, course_type=course_type)
        supervisors = grouped.get("supervisors") or grouped.get("therapists") or []
        by_sup: dict = {}
        for row in supervisors:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("id") or "")
            by_sup[sid or row.get("label_fa") or "supervisor"] = row.get("slots") or []
        ctx = _as_mapping(instance.context_data)
        ctx["available_supervisor_slots"] = by_sup
        ctx["supervisor_slots"] = by_sup
        ctx["displayed_supervisor_slots"] = by_sup
        ctx["available_supervisors"] = supervisors
        if not ctx.get("mandatory_message_fa"):
            ctx["mandatory_message_fa"] = (
                "دانشجوی گرامی، برای پرداخت جهت حضور در 50مین جلسه سوپرویژن باید اول زمان و "
                "سوپرویژن بعدی خود را انتخاب کنید تا قادر به پرداخت برای حضور در 50مین جلسه سوپرویژن باشید"
            )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await _svc_portal.handle(
            self.db,
            instance,
            {"type": "display_available_supervisor_slots"},
            context or {},
        )
        return f"supervisor_slots_loaded n={len(supervisors)}"

    async def _handle_remove_slot_from_available(self, action: dict, instance: ProcessInstance, context: dict):
        from app.services.educational_therapist_slot_service import (
            book_slots_from_context,
            build_slot_summary_for_context,
            _parse_slot_ids,
        )
        from app.models.operational_models import EducationalTherapistSlot
        from sqlalchemy import select

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        # Ensure weekly count for supervision = 1
        merged.setdefault("weekly_sessions", 1)
        merged.setdefault("selected_supervision_weekly_count", 1)
        result = await book_slots_from_context(
            self.db,
            instance_id=instance.id,
            student_id=instance.student_id,
            context=merged,
            therapist_id_key="new_supervisor_id",
            slot_ids_key="slot_ids",
            weekly_sessions_key="weekly_sessions",
            skip_weekly_course_rule=True,
        )
        ctx = _as_mapping(instance.context_data)
        ctx["supervisor_slot_removed_from_available"] = True
        slot_ids = merged.get("slot_ids")
        ids = _parse_slot_ids(slot_ids)
        if ids:
            rows = (
                await self.db.execute(
                    select(EducationalTherapistSlot).where(EducationalTherapistSlot.id.in_(ids))
                )
            ).scalars().all()
            summary = build_slot_summary_for_context(rows)
            ctx.update(summary)
            ctx["booked_slot_ids"] = summary.get("slot_ids")
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return result if result != "skip_no_slot_ids" else "slot_removed_from_available_sheet"

    async def _handle_prepare_supervision_block_payment(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """مبلغ جلسه اول بلوک جدید / جلسه ۵۰ام را برای SepPaymentPanel آماده می‌کند."""
        from app.services.return_to_full_education_service import supervision_payment_fee_rial

        if instance.process_code != "supervision_block_transition":
            return "skip"
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        fee_rial = await supervision_payment_fee_rial(self.db, merged)
        purpose = (action.get("purpose") or merged.get("supervision_payment_purpose") or "new_block_first").strip()
        ctx["payment_amount_rial"] = int(fee_rial)
        ctx["invoice_amount"] = float(fee_rial) / 10.0
        ctx["supervision_payment_amount_rial"] = int(fee_rial)
        ctx["supervision_payment_purpose"] = purpose
        if purpose == "session_50th":
            ctx["payment_unlocked_for_50th_session"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"supervision_block_payment_ready purpose={purpose} fee_rial={fee_rial}"

    async def _handle_book_supervision_block_slots(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """رزرو اسلات سوپروایزر هنگام انتخاب در supervision_block_transition."""
        from app.services.educational_therapist_slot_service import (
            book_slots_from_context,
            build_slot_summary_for_context,
            _parse_slot_ids,
        )
        from app.models.operational_models import EducationalTherapistSlot
        from sqlalchemy import select

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        merged.setdefault("weekly_sessions", 1)
        merged.setdefault("selected_supervision_weekly_count", 1)
        # Map supervisor picker field if form used therapist_id alias
        if not merged.get("new_supervisor_id") and merged.get("therapist_id"):
            merged["new_supervisor_id"] = merged["therapist_id"]
        result = await book_slots_from_context(
            self.db,
            instance_id=instance.id,
            student_id=instance.student_id,
            context=merged,
            therapist_id_key="new_supervisor_id",
            slot_ids_key="slot_ids",
            weekly_sessions_key="weekly_sessions",
            skip_weekly_course_rule=True,
        )
        ctx = _as_mapping(instance.context_data)
        if merged.get("new_supervisor_id"):
            ctx["new_supervisor_id"] = str(merged["new_supervisor_id"])
            ctx["supervisor_id"] = str(merged["new_supervisor_id"])
        ctx["weekly_sessions"] = 1
        ctx["selected_supervision_weekly_count"] = 1
        ids = _parse_slot_ids(merged.get("slot_ids"))
        if ids:
            rows = (
                await self.db.execute(
                    select(EducationalTherapistSlot).where(EducationalTherapistSlot.id.in_(ids))
                )
            ).scalars().all()
            summary = build_slot_summary_for_context(rows)
            ctx.update(summary)
            ctx["booked_slot_ids"] = summary.get("slot_ids")
            if rows:
                ctx["requested_start_date"] = ctx.get("requested_start_date") or ctx.get("first_session_date")
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return result

    async def _handle_add_hour_by_course_and_weekly_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """هر جلسهٔ حضور: +۱ ساعت در context نمونه؛ ساعات خاتمه از جلسات completed + متریک‌ها."""
        add = float(action.get("hours_per_unit", 1.0))
        ctx = _as_mapping(instance.context_data)
        prev = float(ctx.get("accumulated_therapy_hours", 0))
        ctx["accumulated_therapy_hours"] = prev + add
        prev_th = float(ctx.get("therapy_hours_2x", 0))
        ctx["therapy_hours_2x"] = prev_th + add
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"hours_accumulated instance={ctx['therapy_hours_2x']} (+{add})"

    async def _handle_record_attendance_action(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        sid_raw = action.get("session_id") or ctx.get("therapy_session_id") or ctx.get("session_id")
        session_id = uuid.UUID(sid_raw) if sid_raw else None
        rd = ctx.get("record_date")
        if isinstance(rd, str):
            record_date = date.fromisoformat(rd[:10])
        elif isinstance(rd, date):
            record_date = rd
        else:
            record_date = datetime.now(timezone.utc).date()
        status = action.get("status") or ctx.get("attendance_status") or "present"
        await self.attendance.record_attendance(
            student_id=instance.student_id,
            session_id=session_id,
            record_date=record_date,
            status=status,
            absence_type=ctx.get("absence_type"),
            notes=ctx.get("attendance_notes"),
        )
        return f"attendance_recorded status={status} date={record_date}"

    async def _handle_record_absence_auto(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        sid_raw = ctx.get("therapy_session_id") or ctx.get("session_id")
        session_id = uuid.UUID(sid_raw) if sid_raw else None
        record_date = datetime.now(timezone.utc).date()
        await self.attendance.record_attendance(
            student_id=instance.student_id,
            session_id=session_id,
            record_date=record_date,
            status="absent_unexcused",
            absence_type=ctx.get("absence_type") or "student",
            notes="record_absence_auto",
        )
        return "absence_recorded_auto"

    async def _handle_notify_committee(self, action: dict, instance: ProcessInstance, context: dict):
        recipients = action.get("recipients") or [
            "therapy_committee_chair",
            "monitoring_committee_officer",
            "deputy_education",
        ]
        await self._handle_notification(
            {
                "notification_type": action.get("notification_type", "in_app"),
                "template": action.get("template", "committee_notice"),
                "recipients": recipients,
            },
            instance,
            context,
        )
        return f"notify_committee sent_to={recipients}"

    async def _handle_update_record(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت نتیجه در پروندهٔ دانشجو (مثلاً ارزیابی TA) از روی payload/context."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        if instance.process_code == "ta_track_completion":
            from app.services.ta_track_portfolio_service import apply_track_completion_from_context

            result = apply_track_completion_from_context(student, merged)
            return result
        keys = (
            "total_score",
            "result_status",
            "average_score",
            "participation_rate",
            "grade",
            "course_name",
        )
        block = {k: merged[k] for k in keys if k in merged}
        extra = _as_mapping(student.extra_data)
        extra.setdefault("gradebook", {})[instance.process_code] = block
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"record_updated keys={list(block.keys())}"

    async def _handle_merge_instance_context(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت payment_method و شمارندهٔ اقساط در context_data؛ در صورت صفر، بستن خودکار با finalize_term2_registration."""
        from app.core.engine import StateMachineEngine, InvalidTransitionError
        from app.services.tuition_installment_service import (
            TUITION_INSTALLMENT_PROCESS_CODES,
            apply_tuition_payment_context,
            mark_installment_paid,
            refresh_instance_tuition_context,
            sync_installment_reminder_queue,
        )

        system_actor = uuid.UUID("00000000-0000-0000-0000-000000000001")
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        mode = action.get("mode", "initial_payment")

        from app.services.installment_settings_service import get_installment_policy

        policy = await get_installment_policy(self.db)
        term2_installment_gap_days = int(policy.get("term2_installment_gap_days") or 25)

        merged = await refresh_instance_tuition_context(
            self.db,
            instance.process_code,
            instance.current_state_code or "",
            merged,
        )

        if mode == "initial_payment":
            pm = merged.get("payment_method")
            ic = merged.get("installment_count")
            merged["payment_method"] = pm
            if pm == "cash":
                merged["pending_installments_remaining"] = 0
                merged.pop("next_installment_due_at", None)
            elif pm == "installment" and ic is not None:
                try:
                    n = int(ic)
                    merged["pending_installments_remaining"] = max(0, n - 1)
                except (TypeError, ValueError):
                    pass
                extra_st = {}
                stu = await self._get_student(instance.student_id)
                if stu:
                    extra_st = _as_mapping(stu.extra_data)
                term_start = merged.get("term_start_date") or extra_st.get("term_start_date")
                base_date = datetime.now(timezone.utc).date()
                if term_start:
                    try:
                        base_date = date.fromisoformat(str(term_start)[:10])
                    except (TypeError, ValueError):
                        pass
                merged["next_installment_due_at"] = (
                    base_date + timedelta(days=term2_installment_gap_days)
                ).isoformat()
                plan = merged.get("installment_plan") or []
                if plan and len(plan) > 1:
                    merged["next_installment_due_at"] = plan[1].get("due_at") or merged.get(
                        "next_installment_due_at"
                    )
        elif mode == "installment_paid":
            amount_rial = context.get("amount_rial")
            if amount_rial is None and context.get("amount") is not None:
                try:
                    amount_rial = int(round(float(context["amount"]) * 10))
                except (TypeError, ValueError):
                    amount_rial = 0
            else:
                try:
                    amount_rial = int(amount_rial or 0)
                except (TypeError, ValueError):
                    amount_rial = 0
            merged = mark_installment_paid(
                merged,
                str(context.get("ref_id") or context.get("payment_ref") or ""),
                amount_rial,
                gap_days=term2_installment_gap_days,
            )

        merged = apply_tuition_payment_context(merged, gap_days=term2_installment_gap_days)

        if mode == "initial_payment" and merged.get("payment_method") == "installment":
            plan = merged.get("installment_plan") or []
            paid_n = sum(1 for p in plan if isinstance(p, dict) and p.get("status") == "paid")
            if plan and paid_n == 0:
                ref = str(context.get("ref_id") or context.get("payment_ref") or "initial_payment")
                try:
                    amt = int((plan[0] or {}).get("amount_rial") or 0)
                except (TypeError, ValueError):
                    amt = 0
                merged = mark_installment_paid(
                    merged, ref, amt, gap_days=term2_installment_gap_days
                )

        instance.context_data = merged
        flag_modified(instance, "context_data")
        await self.db.flush()

        pending = merged.get("pending_installments_remaining")
        if instance.process_code in TUITION_INSTALLMENT_PROCESS_CODES:
            stu = await self._get_student(instance.student_id)
            if stu:
                sync_installment_reminder_queue(stu, instance, merged)
        if (
            pending == 0
            and instance.process_code == "intro_second_semester_registration"
            and instance.current_state_code == "registration_complete"
        ):
            try:
                engine = StateMachineEngine(self.db)
                await engine.execute_transition(
                    instance.id,
                    "finalize_term2_registration",
                    system_actor,
                    "system",
                )
            except InvalidTransitionError:
                pass

        return f"merge_instance_context mode={mode} pending={pending}"

    async def _handle_deactivate_student_account(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        user = await self._get_user(student.user_id)
        if user:
            user.is_active = False
        extra = _as_mapping(student.extra_data)
        extra["portal_blocked"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "student_account_deactivated"

    async def _handle_call_bpms_subprocess(self, action: dict, instance: ProcessInstance, context: dict):
        code = (
            action.get("process_code")
            or action.get("subprocess_code")
            or action.get("subprocess")
            or "violation_registration"
        )
        payload = dict(action.get("payload") or {})
        payload["parent_instance_id"] = str(instance.id)
        return await self._handle_start_process(
            {"process_code": code, "payload": payload},
            instance,
            context,
        )

    async def _handle_create_online_class_links(self, action: dict, instance: ProcessInstance, context: dict):
        """ایجاد رویداد کلاس در الوکام و ذخیرهٔ لینک روی جلسهٔ درمان؛ در نبود پیکربندی → همان استاب یکپارچه‌سازی."""
        settings = get_settings()
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        aid_raw = (
            action.get("agent_service_id")
            or merged.get("agent_service_id")
            or settings.ALOCOM_DEFAULT_AGENT_SERVICE_ID
        )
        try:
            agent_service_id = int(aid_raw) if aid_raw is not None else 0
        except (TypeError, ValueError):
            agent_service_id = 0

        use_alocom = (
            settings.ALOCOM_ENABLED
            and bool((settings.ALOCOM_USERNAME or "").strip())
            and bool((settings.ALOCOM_PASSWORD or "").strip())
            and agent_service_id > 0
        )
        if not use_alocom:
            if settings.ALOCOM_FALLBACK_TO_UI_HINTS:
                return await self._handle_external_integration(
                    {**action, "type": "create_online_class_links"},
                    instance,
                    context,
                )
            return "create_online_class_links_skipped_no_alocom_config"

        stmt = select(TherapySession).where(TherapySession.student_id == instance.student_id)
        sid_raw = action.get("therapy_session_id") or merged.get("therapy_session_id") or merged.get("session_id")
        sid_filter: Optional[uuid.UUID] = None
        if sid_raw:
            try:
                sid_filter = uuid.UUID(str(sid_raw))
            except (ValueError, TypeError):
                sid_filter = None
        if sid_filter:
            stmt = stmt.where(TherapySession.id == sid_filter)
        else:
            stmt = stmt.where(TherapySession.status == "scheduled").order_by(
                TherapySession.session_date.asc()
            )
        res = await self.db.execute(stmt)
        target = res.scalars().first()
        if not target:
            if settings.ALOCOM_FALLBACK_TO_UI_HINTS:
                return await self._handle_external_integration(
                    {**action, "type": "create_online_class_links"},
                    instance,
                    context,
                )
            return "create_online_class_links_no_therapy_session"

        st = await self._get_student(instance.student_id)
        title = (
            action.get("title")
            or action.get("title_fa")
            or merged.get("class_title")
            or merged.get("alocom_event_title")
            or (f"کلاس آنلاین — {st.student_code}" if st else "کلاس آنلاین")
        )
        duration_raw = action.get("duration_minutes") or merged.get("duration_minutes")
        try:
            duration_minutes = int(duration_raw) if duration_raw is not None else None
        except (TypeError, ValueError):
            duration_minutes = None
        try:
            sba = int(action.get("start_by_admin", merged.get("start_by_admin", 1)))
        except (TypeError, ValueError):
            sba = 1
        fetch_link = bool(action.get("fetch_student_event_link", merged.get("fetch_student_event_link", True)))

        starts_raw = merged.get("session_starts_at") or merged.get("class_starts_at")
        if isinstance(starts_raw, str) and starts_raw.strip():
            try:
                iso = starts_raw.replace("Z", "+00:00")
                target.session_starts_at = datetime.fromisoformat(iso)
            except ValueError:
                pass

        try:
            detail = await provision_therapy_session_alocom(
                self.db,
                session=target,
                agent_service_id=agent_service_id,
                title=str(title)[:500],
                duration_minutes=duration_minutes,
                start_by_admin=sba,
                fetch_student_event_link=fetch_link,
            )
        except AlocomAPIError as e:
            logger.error("Alocom provision failed: %s", e, exc_info=True)
            if settings.ALOCOM_FALLBACK_TO_UI_HINTS:
                ctx = _as_mapping(instance.context_data)
                ctx["alocom_last_error"] = str(e)
                instance.context_data = ctx
                flag_modified(instance, "context_data")
                return await self._handle_external_integration(
                    {**action, "type": "create_online_class_links", "alocom_error": str(e)},
                    instance,
                    context,
                )
            raise

        ctx = _as_mapping(instance.context_data)
        ctx["alocom_last_provision"] = detail
        ctx["last_session_link"] = detail.get("meeting_url")
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"create_online_class_links_ok event_id={detail.get('alocom_event_id')}"


# action type -> handler; merged into ActionHandler._registry
REGISTRY = {
    'send_45_48_reminder_if_applicable': SupervisionActionsMixin._handle_send_reminder,
    'unlock_payment_for_50th_session': SupervisionActionsMixin._handle_unlock_payment_50th,
    'display_supervision_history': SupervisionActionsMixin._handle_display_supervision_history,
    'display_available_supervisor_slots': SupervisionActionsMixin._handle_display_available_supervisor_slots,
    'remove_slot_from_available': SupervisionActionsMixin._handle_remove_slot_from_available,
    'prepare_supervision_block_payment': SupervisionActionsMixin._handle_prepare_supervision_block_payment,
    'book_supervision_block_slots': SupervisionActionsMixin._handle_book_supervision_block_slots,
    'record_attendance': SupervisionActionsMixin._handle_record_attendance_action,
    'record_absence_auto': SupervisionActionsMixin._handle_record_absence_auto,
    'add_hour_by_course_and_weekly_sessions': SupervisionActionsMixin._handle_add_hour_by_course_and_weekly_sessions,
    'notify_committee': SupervisionActionsMixin._handle_notify_committee,
    'update_record': SupervisionActionsMixin._handle_update_record,
    'merge_instance_context': SupervisionActionsMixin._handle_merge_instance_context,
    'deactivate_student_account': SupervisionActionsMixin._handle_deactivate_student_account,
    'call_bpms_subprocess': SupervisionActionsMixin._handle_call_bpms_subprocess,
    'display_available_supervisor_slots': SupervisionActionsMixin._handle_display_available_supervisor_slots,
    'create_online_class_links': SupervisionActionsMixin._handle_create_online_class_links,
}
