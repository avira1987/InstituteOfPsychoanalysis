"""Action Handler - Executes transition actions from process metadata.

This is the bridge between the state machine engine (which reads metadata and
changes states) and the actual business logic (SMS, session management, etc.).

When a transition fires, its `actions` list is published via EventBus.
This handler subscribes to those events and dispatches each action to
the appropriate service method.
"""

import uuid
import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
)
from app.services.notification_service import notification_service
from app.services.payment_service import PaymentService
from app.services.attendance_service import AttendanceService

logger = logging.getLogger(__name__)


class ActionHandler:
    """Dispatches transition actions to the correct service."""

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
            action_type = action.get("type", "unknown")
            try:
                result = await self._dispatch(action_type, action, instance, context)
                results.append({"action": action_type, "success": True, "detail": result})
                logger.info(f"Action OK: {action_type} | instance={instance.id}")
            except Exception as e:
                results.append({"action": action_type, "success": False, "error": str(e)})
                logger.error(f"Action FAIL: {action_type} | instance={instance.id} | {e}", exc_info=True)
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

        logger.warning(f"No handler for action type '{action_type}', skipping.")
        return f"no_handler_for_{action_type}"

    # ─── Notification ────────────────────────────────────────────

    async def _handle_notification(self, action: dict, instance: ProcessInstance, context: dict):
        ntype = action.get("notification_type", "sms")
        template = action.get("template", "")
        recipients = action.get("recipients", [])

        notif_context = await self._build_notification_context(instance, context)

        sent = []
        for role in recipients:
            contact = await self._resolve_contact(role, instance, ntype)
            if contact:
                result = await notification_service.send_notification(
                    ntype, template, contact, notif_context,
                )
                sent.append(f"{role}:{contact}:{result.success}")
            else:
                sent.append(f"{role}:no_contact")
                logger.warning(f"No contact for role '{role}' in instance {instance.id}")

        return f"sent={','.join(sent)}"

    # ─── Sub-process Start ───────────────────────────────────────

    async def _handle_start_process(self, action: dict, instance: ProcessInstance, context: dict):
        from app.core.engine import StateMachineEngine
        engine = StateMachineEngine(self.db)
        sub_code = action.get("process_code", "")
        payload = action.get("payload", {})
        payload["parent_instance_id"] = str(instance.id)

        sub_instance = await engine.start_process(
            process_code=sub_code,
            student_id=instance.student_id,
            actor_id=instance.started_by or instance.student_id,
            actor_role="system",
            initial_context=payload,
        )
        return f"sub_process={sub_code}, sub_instance={sub_instance.id}"

    # ─── Session Management ──────────────────────────────────────

    async def _handle_add_recurring_session(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = instance.context_data or {}
        return f"recurring_session_scheduled: day={ctx.get('day')}, time={ctx.get('time')}"

    async def _handle_remove_selected_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = instance.context_data or {}
        removed = ctx.get("selected_sessions", [])
        return f"sessions_removed: {removed}"

    async def _handle_release_slots(self, action: dict, instance: ProcessInstance, context: dict):
        return "slots_released_to_available_sheet"

    async def _handle_create_extra_session_record(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = instance.context_data or {}
        session = TherapySession(
            id=uuid.uuid4(),
            student_id=instance.student_id,
            session_date=datetime.now(timezone.utc).date(),
            status="scheduled",
            is_extra=True,
            notes=f"Extra supervision: {ctx.get('date', '')} {ctx.get('time', '')}",
        )
        self.db.add(session)
        return f"extra_session_created: {session.id}"

    async def _handle_create_attendance_field(self, action: dict, instance: ProcessInstance, context: dict):
        return "attendance_field_created_for_session"

    async def _handle_activate_online_link(self, action: dict, instance: ProcessInstance, context: dict):
        return "online_session_link_activated"

    async def _handle_record_attendance(self, action: dict, instance: ProcessInstance, context: dict):
        return "supervision_attendance_recorded"

    async def _handle_add_hour_to_block(self, action: dict, instance: ProcessInstance, context: dict):
        return "hour_added_to_supervision_block"

    async def _handle_update_schedule_frequency(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = instance.context_data or {}
        return f"schedule_updated: frequency={ctx.get('frequency')}, day={ctx.get('day')}, time={ctx.get('time')}"

    async def _handle_remove_weekly_session(self, action: dict, instance: ProcessInstance, context: dict):
        return "weekly_session_removed_from_student_schedule"

    async def _handle_connect_to_50h(self, action: dict, instance: ProcessInstance, context: dict):
        return "connected_to_supervision_50h_completion"

    # ─── Therapy-Specific ────────────────────────────────────────

    async def _handle_remove_therapy_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = instance.context_data or {}
        return f"therapy_sessions_removed: {ctx.get('selected_sessions', [])}"

    async def _handle_release_therapist_slots(self, action: dict, instance: ProcessInstance, context: dict):
        return "therapist_slots_released_to_available_sheet"

    async def _handle_record_change_history(self, action: dict, instance: ProcessInstance, context: dict):
        return "therapy_change_history_recorded"

    async def _handle_cancel_session(self, action: dict, instance: ProcessInstance, context: dict):
        return "session_cancelled"

    async def _handle_add_credit(self, action: dict, instance: ProcessInstance, context: dict):
        await self.payment.process_refund(
            student_id=instance.student_id,
            amount=self.payment.DEFAULT_SESSION_FEE,
            reason="بستانکاری - لغو جلسه توسط درمانگر",
            reference_id=instance.id,
        )
        return "credit_added_for_cancelled_session"

    async def _handle_register_makeup(self, action: dict, instance: ProcessInstance, context: dict):
        return "makeup_session_registered"

    async def _handle_enable_online_link(self, action: dict, instance: ProcessInstance, context: dict):
        return "online_session_link_enabled"

    # ─── Attendance & Hours ──────────────────────────────────────

    async def _handle_mark_cancelled(self, action: dict, instance: ProcessInstance, context: dict):
        return "sessions_marked_cancelled_by_student"

    async def _handle_block_attendance(self, action: dict, instance: ProcessInstance, context: dict):
        return "attendance_blocked_for_cancelled_sessions"

    # ─── Financial ───────────────────────────────────────────────

    async def _handle_add_to_credit_balance(self, action: dict, instance: ProcessInstance, context: dict):
        amount = action.get("amount", self.payment.DEFAULT_SESSION_FEE)
        await self.payment.process_refund(
            student_id=instance.student_id,
            amount=amount,
            reason="اعتبار جلسه",
            reference_id=instance.id,
        )
        return f"credit_added: {amount}"

    async def _handle_forfeit_payment(self, action: dict, instance: ProcessInstance, context: dict):
        return "session_payment_forfeited"

    async def _handle_create_debt(self, action: dict, instance: ProcessInstance, context: dict):
        amount = action.get("amount", self.payment.DEFAULT_SESSION_FEE)
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=amount,
            description="بدهی غیبت جلسه",
            reference_id=instance.id,
        )
        return f"debt_created: {amount}"

    async def _handle_increment_absence(self, action: dict, instance: ProcessInstance, context: dict):
        return "absence_counter_incremented"

    # ─── Session payment (BUILD_TODO § ب — استاب تا پیاده‌سازی واقعی) ─────

    async def _handle_generate_payment_invoice(self, action: dict, instance: ProcessInstance, context: dict):
        """Stub: درگاه پرداخت — تا اتصال واقعی."""
        return "payment_invoice_generated_stub"

    async def _handle_zero_debt_if_paid(self, action: dict, instance: ProcessInstance, context: dict):
        """Stub: صفر کردن بدهی پس از پرداخت."""
        return "zero_debt_if_paid_stub"

    async def _handle_allocate_credit_to_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """Stub: تخصیص اعتبار به جلسات."""
        return "allocate_credit_to_sessions_stub"

    async def _handle_unlock_session_links(self, action: dict, instance: ProcessInstance, context: dict):
        """Stub: باز کردن لینک جلسات."""
        return "unlock_session_links_stub"

    async def _handle_unlock_attendance_registration(self, action: dict, instance: ProcessInstance, context: dict):
        """Stub: باز کردن ثبت حضور."""
        return "unlock_attendance_registration_stub"

    async def _handle_suspend_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """Stub: تعلیق جلسات (مثلاً عدم پرداخت)."""
        return "suspend_sessions_stub"

    # ─── Therapy Lifecycle ───────────────────────────────────────

    async def _handle_activate_therapy(self, action: dict, instance: ProcessInstance, context: dict):
        """Set student.therapy_started = True and optionally therapist_id from context (BUILD_TODO § ب)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        student.therapy_started = True
        ctx = instance.context_data or {}
        ctx.update(context or {})
        if ctx.get("therapist_id"):
            student.therapist_id = uuid.UUID(ctx["therapist_id"]) if isinstance(ctx["therapist_id"], str) else ctx["therapist_id"]
        if ctx.get("weekly_sessions") is not None:
            student.weekly_sessions = int(ctx["weekly_sessions"])
        return "therapy_activated"

    async def _handle_block_class_access(self, action: dict, instance: ProcessInstance, context: dict):
        """Block student access to class/attendance (e.g. week 9 deadline). Stored in extra_data (BUILD_TODO § ب)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        extra["class_access_blocked"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "class_access_blocked"

    async def _handle_resolve_access(self, action: dict, instance: ProcessInstance, context: dict):
        """Clear class/attendance block (inverse of block_class_access)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        extra["class_access_blocked"] = False
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "access_restrictions_resolved"

    async def _handle_create_session_link(self, action: dict, instance: ProcessInstance, context: dict):
        return "session_link_created"

    async def _handle_delete_future_appointments(self, action: dict, instance: ProcessInstance, context: dict):
        return "future_therapy_appointments_deleted"

    async def _handle_update_therapy_status(self, action: dict, instance: ProcessInstance, context: dict):
        return "therapy_status_updated"

    async def _handle_mark_terminated(self, action: dict, instance: ProcessInstance, context: dict):
        return "therapy_relationship_terminated"

    async def _handle_log_termination(self, action: dict, instance: ProcessInstance, context: dict):
        return "termination_request_logged"

    async def _handle_set_student_status(self, action: dict, instance: ProcessInstance, context: dict):
        return "student_status_updated"

    # ─── Supervision ─────────────────────────────────────────────

    async def _handle_send_reminder(self, action: dict, instance: ProcessInstance, context: dict):
        return "45_48_reminder_sent_if_applicable"

    async def _handle_unlock_payment_50th(self, action: dict, instance: ProcessInstance, context: dict):
        return "payment_unlocked_for_50th_session"

    async def _handle_display_supervision_history(self, action: dict, instance: ProcessInstance, context: dict):
        return "supervision_history_displayed"

    async def _handle_remove_slot_from_available(self, action: dict, instance: ProcessInstance, context: dict):
        return "slot_removed_from_available_sheet"

    # ─── Contact Resolution ──────────────────────────────────────

    async def _resolve_contact(self, role: str, instance: ProcessInstance, ntype: str) -> Optional[str]:
        """Resolve a contact (phone/email) for a role in the context of an instance."""
        student = await self._get_student(instance.student_id)
        if not student:
            return None

        if role == "student":
            user = await self._get_user(student.user_id)
            return user.phone or user.email if user else None

        if role == "supervisor" and student.supervisor_id:
            user = await self._get_user_direct(student.supervisor_id)
            return user.phone or user.email if user else None

        if role == "therapist" and student.therapist_id:
            user = await self._get_user_direct(student.therapist_id)
            return user.phone or user.email if user else None

        if role in ("site_manager", "deputy_education", "monitoring_committee_officer",
                     "therapy_committee_chair", "therapy_committee_executor"):
            stmt = select(User).where(User.role == role, User.is_active == True).limit(1)
            result = await self.db.execute(stmt)
            user = result.scalars().first()
            return user.phone or user.email if user else None

        ctx = instance.context_data or {}
        if role == "new_supervisor" and ctx.get("new_supervisor_id"):
            user = await self._get_user_direct(uuid.UUID(ctx["new_supervisor_id"]))
            return user.phone or user.email if user else None

        return None

    async def _build_notification_context(self, instance: ProcessInstance, context: dict) -> dict:
        """Build template variable context for notifications."""
        student = await self._get_student(instance.student_id)
        student_user = await self._get_user(student.user_id) if student else None

        notif_ctx = {
            "student_name": student_user.full_name_fa if student_user else "دانشجو",
            "student_code": student.student_code if student else "",
            "process_code": instance.process_code,
            **(instance.context_data or {}),
            **(context or {}),
        }

        if student and student.supervisor_id:
            sup_user = await self._get_user_direct(student.supervisor_id)
            if sup_user:
                notif_ctx["supervisor_name"] = sup_user.full_name_fa or "سوپروایزر"

        if student and student.therapist_id:
            th_user = await self._get_user_direct(student.therapist_id)
            if th_user:
                notif_ctx["therapist_name"] = th_user.full_name_fa or "درمانگر"

        return notif_ctx

    async def _get_student(self, student_id) -> Optional[Student]:
        stmt = select(Student).where(Student.id == student_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _get_user(self, user_id) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _get_user_direct(self, user_id) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    # ─── Action Registry ─────────────────────────────────────────

    _registry = {
        "notification": _handle_notification,
        "start_process": _handle_start_process,

        "add_recurring_therapy_session": _handle_add_recurring_session,
        "add_recurring_supervision_session": _handle_add_recurring_session,
        "remove_selected_therapy_sessions": _handle_remove_therapy_sessions,
        "remove_selected_supervision_sessions": _handle_remove_selected_sessions,
        "release_therapist_slots_to_available_sheet": _handle_release_therapist_slots,
        "release_supervisor_slots_to_available_sheet": _handle_release_slots,
        "record_therapy_change_history": _handle_record_change_history,

        "create_extra_supervision_session_record": _handle_create_extra_session_record,
        "create_attendance_field_for_session": _handle_create_attendance_field,
        "activate_online_session_link": _handle_activate_online_link,
        "record_supervision_attendance": _handle_record_attendance,
        "add_hour_to_supervision_block": _handle_add_hour_to_block,
        "connect_to_supervision_50h_completion": _handle_connect_to_50h,

        "update_supervision_schedule_frequency": _handle_update_schedule_frequency,
        "remove_weekly_session_from_student_schedule": _handle_remove_weekly_session,

        "cancel_session": _handle_cancel_session,
        "add_credit_if_paid": _handle_add_credit,
        "deduct_credit_session": _handle_add_credit,
        "register_makeup_session": _handle_register_makeup,
        "enable_online_session_link": _handle_enable_online_link,

        "mark_sessions_cancelled_by_student": _handle_mark_cancelled,
        "block_attendance_for_cancelled_sessions": _handle_block_attendance,

        "add_to_credit_balance": _handle_add_to_credit_balance,
        "forfeit_session_payment": _handle_forfeit_payment,
        "create_debt_or_deduct_credit": _handle_create_debt,
        "increment_absence_counter": _handle_increment_absence,

        "generate_payment_invoice": _handle_generate_payment_invoice,
        "zero_debt_if_paid": _handle_zero_debt_if_paid,
        "allocate_credit_to_sessions": _handle_allocate_credit_to_sessions,
        "unlock_session_links": _handle_unlock_session_links,
        "unlock_attendance_registration": _handle_unlock_attendance_registration,
        "suspend_sessions": _handle_suspend_sessions,

        "activate_therapy": _handle_activate_therapy,
        "block_class_access": _handle_block_class_access,
        "resolve_access_restrictions": _handle_resolve_access,
        "create_session_link": _handle_create_session_link,
        "delete_future_therapy_appointments": _handle_delete_future_appointments,
        "release_therapist_slots": _handle_release_therapist_slots,
        "update_therapy_status": _handle_update_therapy_status,
        "mark_therapy_relationship_terminated": _handle_mark_terminated,
        "log_termination_request": _handle_log_termination,
        "set_student_status": _handle_set_student_status,

        "send_45_48_reminder_if_applicable": _handle_send_reminder,
        "unlock_payment_for_50th_session": _handle_unlock_payment_50th,
        "display_supervision_history": _handle_display_supervision_history,
        "remove_slot_from_available": _handle_remove_slot_from_available,
    }
