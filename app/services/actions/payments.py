"""Invoices, credit, debt and installment portal locks.

Part of the ActionHandler split. Every method below runs as a mixin method
on ActionHandler, so `self` exposes the whole handler surface.
"""

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from app.services.attendance_tracking_sync import (
    cancel_attendance_instances_for_therapy_session_ids,
    ensure_attendance_instance_for_session,
)
from app.services.financial_program_defaults_service import get_effective_financial_program_defaults
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, Any, List

from app.services.actions._shared import (
    _as_mapping,
    logger,
)


class PaymentActionsMixin:
    """Invoices, credit, debt and installment portal locks."""

    @staticmethod
    def _fee_ledger_category(instance: ProcessInstance, context: Optional[dict] = None) -> str:
        """therapy vs supervision wallet for fee_determination / session credits."""
        from app.services.payment_service import LEDGER_SUPERVISION, LEDGER_THERAPY

        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        if (
            ctx.get("context") == "supervision"
            or ctx.get("supervision_session_paid") is not None
            or str(ctx.get("session_kind") or "").lower().startswith("supervision")
            or "supervision" in str(instance.process_code or "")
        ):
            return LEDGER_SUPERVISION
        return LEDGER_THERAPY

    async def _handle_add_to_credit_balance(self, action: dict, instance: ProcessInstance, context: dict):
        """fee_determination: record financial credit; session_payment: virtual balance (payment row from gateway callback)."""
        from app.services.payment_service import LEDGER_THERAPY

        category = action.get("ledger_category") or self._fee_ledger_category(instance, context)
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
                category=category,
            )
            ctx = _as_mapping(instance.context_data)
            ctx["fee_ledger_amount"] = total
            ctx["fee_ledger_record_type"] = "credit"
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return f"credit_refund_recorded: {total} category={category}"
        if instance.process_code == "session_payment":
            amount = float(
                context.get("amount")
                or _as_mapping(instance.context_data).get("amount")
                or self.payment.DEFAULT_SESSION_FEE
            )
            ctx = _as_mapping(instance.context_data)
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
            category=category or LEDGER_THERAPY,
        )
        return f"credit_added: {amount} category={category}"

    async def _handle_forfeit_payment(self, action: dict, instance: ProcessInstance, context: dict):
        category = action.get("ledger_category") or self._fee_ledger_category(instance, context)
        amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        await self.payment.charge_absence_fee(
            student_id=instance.student_id,
            session_id=instance.id,
            amount=amount,
            created_by=None,
            category=category,
        )
        ctx = _as_mapping(instance.context_data)
        ctx["session_payment_forfeited"] = True
        ctx["forfeit_amount"] = amount
        ctx["fee_ledger_amount"] = amount
        ctx["fee_ledger_record_type"] = "absence_fee"
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"session_payment_forfeited amount={amount} category={category}"

    async def _handle_create_debt_or_deduct_credit(self, action: dict, instance: ProcessInstance, context: dict):
        """سناریوی ۴: اگر بستانکاری همان کیف‌پول کافی باشد، بدون ایجاد بدهی جدید تسویه ثبت می‌شود."""
        category = action.get("ledger_category") or self._fee_ledger_category(instance, context)
        try:
            amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        except (TypeError, ValueError):
            amount = float(self.payment.DEFAULT_SESSION_FEE)
        bal_info = await self.payment.get_student_balance(instance.student_id, category=category)
        net = float(bal_info.get("balance", 0) or 0)
        ctx = _as_mapping(instance.context_data)
        if net >= amount:
            await self.payment.consume_credit(
                student_id=instance.student_id,
                amount=amount,
                reason="کسر از بستانکاری جلسه (تعیین تکلیف هزینه)",
                reference_id=instance.id,
                category=category,
            )
            ctx["fee_settlement_mode"] = "from_existing_credit_balance"
            ctx["fee_settlement_amount"] = amount
            ctx["fee_settlement_ledger_category"] = category
            ctx["fee_ledger_amount"] = amount
            ctx["fee_ledger_record_type"] = "debt"
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return f"fee_settled_from_credit balance_was={net} amount={amount} category={category}"
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=amount,
            description="بدهی غیبت جلسه",
            reference_id=instance.id,
            category=category,
        )
        ctx["fee_settlement_mode"] = "new_debt"
        ctx["fee_settlement_amount"] = amount
        ctx["fee_settlement_ledger_category"] = category
        ctx["fee_ledger_amount"] = amount
        ctx["fee_ledger_record_type"] = "debt"
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"debt_created: {amount} category={category}"

    async def _handle_increment_absence(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        key = action.get("counter_key", "absence_counter_unexcused")
        extra[key] = int(extra.get(key, 0)) + 1
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"absence_counter_incremented {key}={extra[key]}"

    async def _handle_generate_payment_invoice(self, action: dict, instance: ProcessInstance, context: dict):
        ctx_map = _as_mapping(instance.context_data)
        raw_sessions = ctx_map.get("sessions_to_pay")
        try:
            n_sessions = max(1, int(raw_sessions)) if raw_sessions is not None else 1
        except (TypeError, ValueError):
            n_sessions = 1
        fd_inv = await get_effective_financial_program_defaults(self.db)
        per = float(fd_inv.get("default_therapy_session_fee_toman") or self.payment.DEFAULT_SESSION_FEE)
        # بدهی واقعی (گذشته/برگزارشده) — نه جلسات آیندهٔ تقویم؛ با تسویه اجباری به فاکتور
        from app.services.therapy_session_schedule import count_therapy_debt_sessions

        debt_n = await count_therapy_debt_sessions(self.db, instance.student_id)
        dsi = ctx_map.get("debt_settlement_included")
        if isinstance(dsi, str):
            include_debt = dsi.strip().lower() in ("1", "true", "yes", "on")
        else:
            include_debt = bool(dsi)
        if debt_n > 0:
            include_debt = True
        billable = n_sessions + (debt_n if include_debt else 0)
        computed = per * float(billable)
        if context.get("amount") is not None:
            try:
                amount = float(context["amount"])
            except (TypeError, ValueError):
                amount = computed
        elif include_debt and debt_n > 0:
            # مبلغ پرونده ممکن است بدون بدهی قدیمی باشد — با بدهی از محاسبهٔ تازه استفاده کن
            amount = computed
        elif ctx_map.get("amount") not in (None, "", 0) and float(ctx_map.get("amount") or 0) > 0:
            amount = float(ctx_map["amount"])
        elif ctx_map.get("total_amount") not in (None, "", 0) and float(ctx_map.get("total_amount") or 0) > 0:
            amount = float(ctx_map["total_amount"])
        else:
            amount = computed
        desc = "پیش‌فاکتور پرداخت جلسات درمان"
        if include_debt and debt_n > 0:
            desc = f"پیش‌فاکتور {n_sessions} جلسه آتی + تسویه {debt_n} جلسه بدهکار"
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=amount,
            description=desc,
            reference_id=instance.id,
            category="therapy",
        )
        ctx = _as_mapping(instance.context_data)
        ctx["invoice_amount"] = amount
        ctx["payment_amount_rial"] = int(round(float(amount) * 10))
        ctx["sessions_to_pay"] = n_sessions
        ctx["debt_sessions_count"] = debt_n
        ctx["debt_settlement_included"] = include_debt
        if include_debt and debt_n > 0:
            ctx["debt_amount_toman"] = per * float(debt_n)
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"payment_invoice_generated amount={amount} sessions={n_sessions} debt={debt_n if include_debt else 0}"

    async def _handle_zero_debt_if_paid(self, action: dict, instance: ProcessInstance, context: dict):
        stmt = delete(FinancialRecord).where(
            FinancialRecord.student_id == instance.student_id,
            FinancialRecord.record_type == "debt",
            FinancialRecord.reference_id == instance.id,
        )
        result = await self.db.execute(stmt)
        return f"zero_debt_cleared rows={getattr(result, 'rowcount', None)}"

    async def _handle_allocate_credit_to_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """تخصیص فقط از کیف‌پول درمان (نه سوپرویژن) به جلسات درمان."""
        from app.services.payment_service import LEDGER_THERAPY

        fd_c = await get_effective_financial_program_defaults(self.db)
        fee = float(fd_c.get("default_therapy_session_fee_toman") or self.payment.DEFAULT_SESSION_FEE)
        ctx = _as_mapping(instance.context_data)
        balance = float(ctx.get("session_credit_balance", 0))
        if balance <= 0:
            balance = float(context.get("amount") or 0)
        if balance <= 0:
            # مانده واقعی کیف درمان (بستانکاری fee_determination)
            therapy_bal = await self.payment.get_student_balance(
                instance.student_id, category=LEDGER_THERAPY
            )
            balance = max(0.0, float(therapy_bal.get("balance") or 0))
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
        paid_sessions: List[TherapySession] = []
        for s in rows[:sessions_to_cover]:
            s.payment_status = "paid"
            spent += fee
            n += 1
            paid_sessions.append(s)
        ctx["session_credit_balance"] = max(0.0, balance - spent)
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await self.db.flush()
        for s in paid_sessions:
            try:
                await ensure_attendance_instance_for_session(self.db, s)
            except Exception:
                logger.exception("ensure_attendance_instance_for_session failed after allocate session=%s", s.id)
        return f"allocated_to_sessions n={n} remaining={ctx['session_credit_balance']} wallet={LEDGER_THERAPY}"

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
            extra = _as_mapping(student.extra_data)
            extra["session_links_unlocked"] = True
            student.extra_data = extra
            flag_modified(student, "extra_data")
        return f"session_links_unlocked count={unlocked}"

    async def _handle_unlock_attendance_registration(self, action: dict, instance: ProcessInstance, context: dict):
        from app.services.class_attendance_service import TUITION_PRESENT_BLOCK_PROCESS_CODES

        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["attendance_registration_unlocked"] = True
        # رفع قفل «حاضر» کلاس پس از تسویه قسط معوق
        if instance.process_code in TUITION_PRESENT_BLOCK_PROCESS_CODES or extra.get("class_present_blocked"):
            extra.pop("class_present_blocked", None)
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "attendance_registration_unlocked"

    async def _handle_set_installment_portal_lock(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["installment_portal_lock"] = {
            "active": True,
            "instance_id": str(instance.id),
            "process_code": instance.process_code,
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "installment_portal_lock_set"

    async def _handle_clear_installment_portal_lock(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra.pop("installment_portal_lock", None)
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "installment_portal_lock_cleared"

    async def _handle_suspend_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["sessions_suspended"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "sessions_suspended_flag_set"


# action type -> handler; merged into ActionHandler._registry
REGISTRY = {
    'add_to_credit_balance': PaymentActionsMixin._handle_add_to_credit_balance,
    'forfeit_session_payment': PaymentActionsMixin._handle_forfeit_payment,
    'create_debt_or_deduct_credit': PaymentActionsMixin._handle_create_debt_or_deduct_credit,
    'increment_absence_counter': PaymentActionsMixin._handle_increment_absence,
    'generate_payment_invoice': PaymentActionsMixin._handle_generate_payment_invoice,
    'zero_debt_if_paid': PaymentActionsMixin._handle_zero_debt_if_paid,
    'allocate_credit_to_sessions': PaymentActionsMixin._handle_allocate_credit_to_sessions,
    'unlock_session_links': PaymentActionsMixin._handle_unlock_session_links,
    'unlock_attendance_registration': PaymentActionsMixin._handle_unlock_attendance_registration,
    'suspend_sessions': PaymentActionsMixin._handle_suspend_sessions,
    'enable_attendance_registration': PaymentActionsMixin._handle_unlock_attendance_registration,
    'set_installment_portal_lock': PaymentActionsMixin._handle_set_installment_portal_lock,
    'unblock_attendance_registration': PaymentActionsMixin._handle_unlock_attendance_registration,
    'clear_installment_portal_lock': PaymentActionsMixin._handle_clear_installment_portal_lock,
}
