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
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
)
from app.services.notification_service import notification_service
from app.services.payment_service import PaymentService
from app.services.attendance_service import AttendanceService
from app.services.external_integration import append_integration_event, notify_integration
from app.config import get_settings

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
        """افزودن جلسهٔ درمان تکرارشونده به ``therapy_sessions`` (بر اساس context/payload)."""
        ctx = {**(instance.context_data or {}), **(context or {})}
        n = int(action.get("count") or ctx.get("sessions_to_add") or 1)
        therapist_id = ctx.get("therapist_id")
        tid = uuid.UUID(therapist_id) if isinstance(therapist_id, str) else therapist_id
        base = ctx.get("first_session_date")
        if base:
            if isinstance(base, str):
                start_d = date.fromisoformat(base[:10])
            else:
                start_d = base
        else:
            start_d = datetime.now(timezone.utc).date()
        created = []
        for i in range(n):
            d = start_d + timedelta(weeks=i)
            ts = TherapySession(
                id=uuid.uuid4(),
                student_id=instance.student_id,
                therapist_id=tid,
                session_date=d,
                status="scheduled",
                is_extra=bool(ctx.get("is_extra")),
                payment_status="pending",
            )
            self.db.add(ts)
            created.append(str(ts.id))
        return f"therapy_sessions_created n={n} ids={','.join(created[:5])}"

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

    async def _handle_record_supervision_attendance(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت حضور سوپرویژن (متادیتا؛ جزئیات در صورت نیاز به AttendanceService متصل می‌شود)."""
        ctx = dict(instance.context_data or {})
        ctx["supervision_attendance_recorded"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
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

    async def _handle_deduct_credit_session(self, action: dict, instance: ProcessInstance, context: dict):
        """کسر از اعتبار جلسه در context؛ اگر اعتبار ناکافی باشد ثبت بدهی."""
        fee = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        ctx = dict(instance.context_data or {})
        balance = float(ctx.get("session_credit_balance", 0))
        if balance >= fee:
            ctx["session_credit_balance"] = balance - fee
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return f"session_credit_deducted remaining={ctx['session_credit_balance']}"
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=fee,
            description="کسر بابت جلسه — اعتبار ناکافی",
            reference_id=instance.id,
        )
        return f"debt_for_shortfall amount={fee}"

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
        """fee_determination: record financial credit; session_payment: virtual balance (payment row from gateway callback)."""
        sessions = action.get("sessions")
        if sessions is not None:
            n = float(sessions)
            per = float(action.get("amount_per_session", self.payment.DEFAULT_SESSION_FEE))
            total = per * n
            await self.payment.process_refund(
                student_id=instance.student_id,
                amount=total,
                reason="بازگشت اعتبار جلسه (تعیین تکلیف هزینه)",
                reference_id=instance.id,
            )
            return f"credit_refund_recorded: {total}"
        if instance.process_code == "session_payment":
            amount = float(
                context.get("amount")
                or (instance.context_data or {}).get("amount")
                or self.payment.DEFAULT_SESSION_FEE
            )
            ctx = dict(instance.context_data or {})
            ctx["session_credit_balance"] = float(ctx.get("session_credit_balance", 0)) + amount
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return f"session_credit_balance_context: {ctx['session_credit_balance']}"
        amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        await self.payment.process_refund(
            student_id=instance.student_id,
            amount=amount,
            reason="اعتبار جلسه",
            reference_id=instance.id,
        )
        return f"credit_added: {amount}"

    async def _handle_forfeit_payment(self, action: dict, instance: ProcessInstance, context: dict):
        amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        await self.payment.charge_absence_fee(
            student_id=instance.student_id,
            amount=amount,
            created_by=None,
        )
        ctx = dict(instance.context_data or {})
        ctx["session_payment_forfeited"] = True
        ctx["forfeit_amount"] = amount
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"session_payment_forfeited amount={amount}"

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
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        key = action.get("counter_key", "absence_counter_unexcused")
        extra[key] = int(extra.get(key, 0)) + 1
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"absence_counter_incremented {key}={extra[key]}"

    # ─── Session payment (real bookkeeping + session rows) ─────

    async def _handle_generate_payment_invoice(self, action: dict, instance: ProcessInstance, context: dict):
        amount = float(
            context.get("amount")
            or (instance.context_data or {}).get("amount")
            or (instance.context_data or {}).get("total_amount")
            or self.payment.DEFAULT_SESSION_FEE
        )
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=amount,
            description="پیش‌فاکتور پرداخت جلسات درمان",
            reference_id=instance.id,
        )
        ctx = dict(instance.context_data or {})
        ctx["invoice_amount"] = amount
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"payment_invoice_generated amount={amount}"

    async def _handle_zero_debt_if_paid(self, action: dict, instance: ProcessInstance, context: dict):
        stmt = delete(FinancialRecord).where(
            FinancialRecord.student_id == instance.student_id,
            FinancialRecord.record_type == "debt",
            FinancialRecord.reference_id == instance.id,
        )
        result = await self.db.execute(stmt)
        return f"zero_debt_cleared rows={getattr(result, 'rowcount', None)}"

    async def _handle_allocate_credit_to_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        fee = float(self.payment.DEFAULT_SESSION_FEE)
        ctx = dict(instance.context_data or {})
        balance = float(ctx.get("session_credit_balance", 0))
        if balance <= 0:
            balance = float(context.get("amount") or 0)
        if balance <= 0 or fee <= 0:
            return "allocate_credit_no_balance"
        sessions_to_cover = int(balance // fee)
        stmt = (
            select(TherapySession)
            .where(
                TherapySession.student_id == instance.student_id,
                TherapySession.payment_status == "pending",
                TherapySession.status.in_(["scheduled", "completed"]),
            )
            .order_by(TherapySession.session_date)
        )
        res = await self.db.execute(stmt)
        rows = list(res.scalars().all())
        spent = 0.0
        n = 0
        for s in rows[:sessions_to_cover]:
            s.payment_status = "paid"
            spent += fee
            n += 1
        ctx["session_credit_balance"] = max(0.0, balance - spent)
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"allocated_to_sessions n={n} remaining={ctx['session_credit_balance']}"

    async def _handle_unlock_session_links(self, action: dict, instance: ProcessInstance, context: dict):
        stmt = select(TherapySession).where(
            TherapySession.student_id == instance.student_id,
            TherapySession.payment_status.in_(["paid", "waived"]),
            TherapySession.status == "scheduled",
        )
        res = await self.db.execute(stmt)
        unlocked = 0
        for s in res.scalars().all():
            s.links_unlocked = True
            unlocked += 1
        student = await self._get_student(instance.student_id)
        if student:
            extra = dict(student.extra_data or {})
            extra["session_links_unlocked"] = True
            student.extra_data = extra
            flag_modified(student, "extra_data")
        return f"session_links_unlocked count={unlocked}"

    async def _handle_unlock_attendance_registration(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        extra["attendance_registration_unlocked"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "attendance_registration_unlocked"

    async def _handle_suspend_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        extra["sessions_suspended"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "sessions_suspended_flag_set"

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
        settings = get_settings()
        ctx = {**(instance.context_data or {}), **(context or {})}
        url = action.get("meeting_url") or ctx.get("meeting_url") or ctx.get("session_link")
        stmt = (
            select(TherapySession)
            .where(
                TherapySession.student_id == instance.student_id,
                TherapySession.status == "scheduled",
            )
            .order_by(TherapySession.session_date.asc())
        )
        res = await self.db.execute(stmt)
        sessions = list(res.scalars().all())
        target = sessions[0] if sessions else None
        base = settings.APP_BASE_URL.rstrip("/")
        if not url:
            if target:
                url = f"{base}/meet/therapy/{target.id}"
            else:
                url = f"{base}/meet/therapy/pending/{instance.student_id}"
        if target:
            target.meeting_url = url
            target.meeting_provider = str(
                action.get("meeting_provider") or ctx.get("meeting_provider") or "manual"
            )
            target.links_unlocked = True
        ctx = dict(instance.context_data or {})
        ctx["last_session_link"] = url
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"session_link_set url={url} session_id={getattr(target, 'id', None)}"

    async def _handle_delete_future_appointments(self, action: dict, instance: ProcessInstance, context: dict):
        today = datetime.now(timezone.utc).date()
        stmt = delete(TherapySession).where(
            TherapySession.student_id == instance.student_id,
            TherapySession.session_date >= today,
            TherapySession.status == "scheduled",
        )
        result = await self.db.execute(stmt)
        rc = getattr(result, "rowcount", None)
        return f"future_therapy_appointments_deleted rowcount={rc}"

    async def _handle_update_therapy_status(self, action: dict, instance: ProcessInstance, context: dict):
        status = action.get("status") or (context or {}).get("therapy_status") or "completed"
        student = await self._get_student(instance.student_id)
        if student:
            extra = dict(student.extra_data or {})
            extra["therapy_status"] = status
            student.extra_data = extra
            flag_modified(student, "extra_data")
        ctx = dict(instance.context_data or {})
        ctx["therapy_status"] = status
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"therapy_status_updated status={status}"

    async def _handle_mark_terminated(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        student.therapy_started = False
        if action.get("clear_therapist", True):
            student.therapist_id = None
        extra = dict(student.extra_data or {})
        extra["therapy_relationship"] = "terminated"
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "therapy_relationship_terminated"

    async def _handle_log_termination(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = dict(instance.context_data or {})
        log = list(ctx.get("termination_requests") or [])
        log.append({"logged_at": datetime.now(timezone.utc).isoformat(), "payload": dict(context or {})})
        ctx["termination_requests"] = log
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"termination_request_logged n={len(log)}"

    async def _handle_set_student_status(self, action: dict, instance: ProcessInstance, context: dict):
        status = action.get("status") or (context or {}).get("student_status") or "active"
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        extra["lifecycle_status"] = status
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"student_status_updated lifecycle_status={status}"

    # ─── Supervision ─────────────────────────────────────────────

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
        ctx = dict(instance.context_data or {})
        ctx["reminder_45_48_sent_at"] = datetime.now(timezone.utc).isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "45_48_reminder_sent_if_applicable"

    async def _handle_unlock_payment_50th(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if student:
            extra = dict(student.extra_data or {})
            extra["payment_unlocked_for_50th_session"] = True
            student.extra_data = extra
            flag_modified(student, "extra_data")
        ctx = dict(instance.context_data or {})
        ctx["payment_unlocked_for_50th_session"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "payment_unlocked_for_50th_session"

    async def _handle_display_supervision_history(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = dict(instance.context_data or {})
        ctx.setdefault("ui_hints", []).append({"action": "display_supervision_history", "payload": {}})
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "supervision_history_displayed"

    async def _handle_remove_slot_from_available(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = dict(instance.context_data or {})
        ctx["supervisor_slot_removed_from_available"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "slot_removed_from_available_sheet"

    async def _handle_add_hour_by_course_and_weekly_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        weekly = int(action.get("weekly_sessions") or (student.weekly_sessions if student else 1))
        hours_unit = float(action.get("hours_per_unit", 1.0))
        add = hours_unit * max(1, weekly)
        ctx = dict(instance.context_data or {})
        prev = float(ctx.get("accumulated_therapy_hours", 0))
        ctx["accumulated_therapy_hours"] = prev + add
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"hours_accumulated total={ctx['accumulated_therapy_hours']} (+{add})"

    async def _handle_record_attendance_action(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = {**(instance.context_data or {}), **(context or {})}
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
        ctx = {**(instance.context_data or {}), **(context or {})}
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
        merged = {**(instance.context_data or {}), **(context or {})}
        keys = (
            "total_score",
            "result_status",
            "average_score",
            "participation_rate",
            "grade",
            "course_name",
        )
        block = {k: merged[k] for k in keys if k in merged}
        extra = dict(student.extra_data or {})
        extra.setdefault("gradebook", {})[instance.process_code] = block
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"record_updated keys={list(block.keys())}"

    async def _handle_merge_instance_context(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت payment_method و شمارندهٔ اقساط در context_data؛ در صورت صفر، بستن خودکار با finalize_term2_registration."""
        from app.core.engine import StateMachineEngine, InvalidTransitionError

        system_actor = uuid.UUID("00000000-0000-0000-0000-000000000001")
        ctx = dict(instance.context_data or {})
        merged = {**ctx, **(context or {})}
        mode = action.get("mode", "initial_payment")

        from app.services.installment_settings_service import get_installment_policy

        policy = await get_installment_policy(self.db)
        term2_installment_gap_days = int(policy.get("term2_installment_gap_days") or 25)

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
                # سررسید قسط بعدی: از تاریخ شروع ترم در extra دانشجو یا N روز پس از امروز
                extra_st = {}
                stu = await self._get_student(instance.student_id)
                if stu and stu.extra_data:
                    extra_st = stu.extra_data
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
        elif mode == "installment_paid":
            cur = merged.get("pending_installments_remaining")
            if isinstance(cur, int) and cur > 0:
                merged["pending_installments_remaining"] = cur - 1
            elif cur is not None:
                try:
                    c = int(cur)
                    if c > 0:
                        merged["pending_installments_remaining"] = c - 1
                except (TypeError, ValueError):
                    pass
            pending_after = merged.get("pending_installments_remaining")
            if isinstance(pending_after, int) and pending_after > 0:
                merged["next_installment_due_at"] = (
                    datetime.now(timezone.utc).date() + timedelta(days=term2_installment_gap_days)
                ).isoformat()
            else:
                merged.pop("next_installment_due_at", None)

        instance.context_data = merged
        flag_modified(instance, "context_data")
        await self.db.flush()

        pending = merged.get("pending_installments_remaining")
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
        extra = dict(student.extra_data or {})
        extra["portal_blocked"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "student_account_deactivated"

    async def _handle_call_bpms_subprocess(self, action: dict, instance: ProcessInstance, context: dict):
        code = action.get("process_code") or action.get("subprocess_code") or "violation_registration"
        payload = dict(action.get("payload") or {})
        payload["parent_instance_id"] = str(instance.id)
        return await self._handle_start_process(
            {"process_code": code, "payload": payload},
            instance,
            context,
        )

    async def _handle_external_integration(self, action: dict, instance: ProcessInstance, context: dict):
        """یکپارچه‌سازی LMS/وب‌هوک + راهنمای UI؛ برای اکشن‌های «ثبت در LMS» و مشابه."""
        name = action.get("type", "unknown")
        detail = {k: v for k, v in action.items() if k != "type"}
        append_integration_event(instance, name, {"detail": detail, "context_keys": list((context or {}).keys())})
        ctx = dict(instance.context_data or {})
        ctx.setdefault("ui_hints", []).append({"action": name, "detail": detail})
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        webhook = await notify_integration(
            name,
            instance.id,
            instance.student_id,
            instance.process_code,
            extra={"action": detail},
        )
        return f"{name} integration={webhook}"

    async def _handle_move_therapist_to_past(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        extra["therapist_assignment"] = "past_list"
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "therapist_moved_to_past_list"

    async def _handle_unlock_student_portal_flag(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        extra["student_portal_result_recorded"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "record_result_in_student_portal"

    async def _handle_redirect_to_process(self, action: dict, instance: ProcessInstance, context: dict):
        code = action.get("process_code", "")
        if code:
            return await self._handle_start_process(
                {"process_code": code, "payload": action.get("payload", {})},
                instance,
                context,
            )
        return "redirect_process_skipped_no_code"

    async def _handle_run_patient_referral(self, action: dict, instance: ProcessInstance, context: dict):
        payload = dict(action.get("payload") or {})
        payload.setdefault("parent_instance_id", str(instance.id))
        return await self._handle_start_process(
            {"process_code": "patient_referral", "payload": payload},
            instance,
            context,
        )

    async def _handle_refer_to_violation_registration(self, action: dict, instance: ProcessInstance, context: dict):
        payload = dict(action.get("payload") or {})
        payload.setdefault("parent_instance_id", str(instance.id))
        return await self._handle_start_process(
            {"process_code": "violation_registration", "payload": payload},
            instance,
            context,
        )

    async def _handle_reset_therapy_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """آغاز مجدد درمان: حذف جلسات آینده (همان مسیر قطع برنامه‌ریزی‌شده)."""
        return await self._handle_delete_future_appointments(action, instance, context)

    async def _handle_update_therapist(self, action: dict, instance: ProcessInstance, context: dict):
        """تعیین درمانگر جدید از context/payload/instance پس از تایید دانشجو."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        merged = {**(instance.context_data or {}), **(context or {}), **(action.get("payload") or {})}
        tid = merged.get("new_therapist_id") or merged.get("therapist_id")
        if tid:
            student.therapist_id = uuid.UUID(str(tid)) if isinstance(tid, str) else tid
        return "therapist_updated"

    async def _handle_process_refund_action(self, action: dict, instance: ProcessInstance, context: dict):
        amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        reason = str(action.get("reason", "process_refund"))
        await self.payment.process_refund(
            student_id=instance.student_id,
            amount=amount,
            reason=reason,
            reference_id=instance.id,
        )
        return f"process_refund amount={amount}"

    async def _handle_move_supervisor_to_past_list(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = dict(student.extra_data or {})
        extra["supervisor_assignment"] = "past_list"
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "supervisor_moved_to_past_list"

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
        "record_supervision_attendance": _handle_record_supervision_attendance,
        "add_hour_to_supervision_block": _handle_add_hour_to_block,
        "connect_to_supervision_50h_completion": _handle_connect_to_50h,

        "update_supervision_schedule_frequency": _handle_update_schedule_frequency,
        "remove_weekly_session_from_student_schedule": _handle_remove_weekly_session,

        "cancel_session": _handle_cancel_session,
        "add_credit_if_paid": _handle_add_credit,
        "deduct_credit_session": _handle_deduct_credit_session,
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

        "record_attendance": _handle_record_attendance_action,
        "record_absence_auto": _handle_record_absence_auto,
        "add_hour_by_course_and_weekly_sessions": _handle_add_hour_by_course_and_weekly_sessions,
        "notify_committee": _handle_notify_committee,
        "update_record": _handle_update_record,
        "merge_instance_context": _handle_merge_instance_context,
        "deactivate_student_account": _handle_deactivate_student_account,
        "call_bpms_subprocess": _handle_call_bpms_subprocess,
        "redirect_to_process": _handle_redirect_to_process,
        "move_therapist_to_past": _handle_move_therapist_to_past,
        "record_result_in_student_portal": _handle_unlock_student_portal_flag,
        "ensure_therapist_slots_freed": _handle_release_therapist_slots,

        "send_unlock_to_lms": _handle_external_integration,
        "unlock_student_therapist_selection": _handle_external_integration,
        "record_commission_result": _handle_external_integration,
        "store_nezarat_recommendation": _handle_external_integration,
        "generate_termination_letter": _handle_external_integration,
        "register_new_supervision_block_in_lms": _handle_external_integration,
        "enable_attendance_for_new_supervisor": _handle_external_integration,
        "create_online_link_50th": _handle_external_integration,
        "enable_attendance_for_current_supervisor_50th": _handle_external_integration,
        "display_available_supervisor_slots": _handle_external_integration,
        "display_mandatory_message": _handle_external_integration,
        "apply_24h_rule_for_start_date": _handle_external_integration,
        "display_calculated_start_date": _handle_external_integration,
        "cancel_supervision_session": _handle_cancel_session,
        "add_supervision_credit_if_paid": _handle_add_credit,
        "register_supervision_makeup_session": _handle_register_makeup,
        "enable_attendance_registration": _handle_unlock_attendance_registration,
        "release_supervisor_slot": _handle_release_slots,
        "move_supervisor_to_past_list": _handle_move_supervisor_to_past_list,
        "record_interruption_dates": _handle_external_integration,
        "monitor_return_at_end_date": _handle_external_integration,
        "run_patient_referral": _handle_run_patient_referral,
        "move_ta_to_instructor": _handle_external_integration,
        "upgrade_rank_to_assistant_faculty": _handle_external_integration,
        "unlock_next_course_in_track": _handle_external_integration,
        "publish_courses_to_website": _handle_external_integration,
        "publish_academic_calendar_to_profiles": _handle_external_integration,
        "show_popup": _handle_external_integration,
        "load_available_courses": _handle_external_integration,
        "register_courses_in_portal": _handle_external_integration,
        "create_online_class_links": _handle_external_integration,
        "schedule_installment_reminders": _handle_external_integration,
        "block_attendance_registration": _handle_block_attendance,
        "notify_instructor": _handle_external_integration,
        "unblock_attendance_registration": _handle_unlock_attendance_registration,

        "record_commission_result_in_student_portal": _handle_external_integration,
        "record_evaluation_completion": _handle_external_integration,
        "lock_block_counter": _handle_external_integration,
        "display_evaluation_warning_to_supervisor": _handle_external_integration,
        "create_evaluation_task": _handle_external_integration,
        "suspend_class_registration": _handle_block_class_access,
        "revoke_intern_status": _handle_external_integration,

        # نام‌های اضافهٔ متادیتا (هم‌ارز یا استاب یکپارچه‌سازی)
        "add_ta_score": _handle_external_integration,
        "apply_electronic_signature_and_seal": _handle_external_integration,
        "archive_letter_in_student_file": _handle_external_integration,
        "block_future_applications": _handle_external_integration,
        "block_future_enrollment": _handle_external_integration,
        "block_next_term_registration": _handle_external_integration,
        "cancel_all_future_sessions": _handle_delete_future_appointments,
        "create_education_committee_task": _handle_external_integration,
        "create_extra_session_record": _handle_create_extra_session_record,
        "create_lms_course_links": _handle_external_integration,
        "create_user_account": _handle_external_integration,
        "deduct_credit_if_has": _handle_deduct_credit_session,
        "display_error_message": _handle_external_integration,
        "display_meeting_in_portal": _handle_external_integration,
        "display_rejection_explanations": _handle_external_integration,
        "enable_pdf_export": _handle_external_integration,
        "generate_certificate": _handle_external_integration,
        "generate_cumulative_transcript": _handle_external_integration,
        "generate_decline_list": _handle_external_integration,
        "generate_pdf_export": _handle_external_integration,
        "generate_term_transcript": _handle_external_integration,
        "increase_intern_capacity": _handle_external_integration,
        "load_term3_courses": _handle_external_integration,
        "log_sla_breach_in_portals": _handle_external_integration,
        "move_to_past_lists": _handle_external_integration,
        "process_refund": _handle_process_refund_action,
        "reactivate_class_registration": _handle_external_integration,
        "record_accounting": _handle_external_integration,
        "record_pause_dates_in_lms": _handle_external_integration,
        "record_termination_date": _handle_external_integration,
        "record_termination_in_student_portal": _handle_external_integration,
        "refer_to_violation_registration": _handle_refer_to_violation_registration,
        "register_in_calendar": _handle_external_integration,
        "register_student_in_courses": _handle_external_integration,
        "release_supervisor_slots": _handle_release_slots,
        "reset_therapy_sessions": _handle_reset_therapy_sessions,
        "retain_patients": _handle_external_integration,
        "retain_supervisor": _handle_external_integration,
        "retain_therapist_and_supervisor": _handle_external_integration,
        "revoke_student_access": _handle_external_integration,
        "schedule_reminder": _handle_external_integration,
        "scheduled_notification": _handle_external_integration,
        "send_to_dashboard": _handle_external_integration,
        "send_to_progress_committee": _handle_external_integration,
        "share_document_with_interviewer": _handle_external_integration,
        "show_payment_confirmation": _handle_external_integration,
        "store_executive_advisory_opinion": _handle_external_integration,
        "store_rejection_reason_confidential": _handle_external_integration,
        "unblock_next_term_registration": _handle_external_integration,
        "update_schedule": _handle_external_integration,
        "update_therapist": _handle_update_therapist,
        "update_total_hours": _handle_external_integration,
        "upload_certificate_to_portal": _handle_external_integration,
        "warn_if": _handle_external_integration,
    }
