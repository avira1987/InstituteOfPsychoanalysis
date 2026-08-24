"""Tuition installment plan, payable amount, and student finance aggregation."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student

TUITION_INSTALLMENT_PROCESS_CODES = (
    "introductory_course_registration",
    "intro_second_semester_registration",
    "comprehensive_course_registration",
    "comprehensive_term_start",
)

TUITION_PAYMENT_STATES = frozenset(
    {
        "payment",
        "payment_method",
        "payment_processing",
        "payment_choice",
        "installment_overdue",
        "registration_complete",
        "course_selection",
        "course_display",
    }
)

DEFAULT_INSTALLMENT_GAP_DAYS = 25
REMINDER_DAYS_BEFORE = 1


def _valid_rial(value: Any) -> bool:
    try:
        return int(value) >= 1000
    except (TypeError, ValueError):
        return False


def _parse_date(value: Any) -> Optional[date]:
    from app.utils.shamsi_calendar_utils import tehran_calendar_date

    return tehran_calendar_date(value)


def split_installment_amounts(total_rial: int, count: int) -> list[int]:
    """Equal split; remainder on last installment."""
    if count <= 0:
        return [total_rial]
    base = total_rial // count
    amounts = [base] * count
    amounts[-1] += total_rial % count
    return amounts


def compute_installment_plan(
    total_tuition_rial: int,
    payment_method: str,
    installment_count: int | None,
    base_due_date: date | None = None,
    gap_days: int = DEFAULT_INSTALLMENT_GAP_DAYS,
    existing_plan: list[dict] | None = None,
) -> list[dict]:
    """Build or refresh installment schedule."""
    from app.utils.shamsi_calendar_utils import tehran_today

    base = base_due_date or tehran_today()
    if payment_method != "installment" or not installment_count or int(installment_count) <= 1:
        item: dict[str, Any] = {
            "index": 1,
            "amount_rial": total_tuition_rial,
            "due_at": base.isoformat(),
            "status": "pending",
        }
        if existing_plan:
            ex = existing_plan[0] if existing_plan else {}
            if ex.get("status") == "paid":
                item["status"] = "paid"
                item["paid_at"] = ex.get("paid_at")
                item["payment_ref"] = ex.get("payment_ref")
        return [item]

    count = int(installment_count)
    amounts = split_installment_amounts(total_tuition_rial, count)
    paid_by_index = {}
    if existing_plan:
        for ex in existing_plan:
            if ex.get("status") == "paid":
                paid_by_index[int(ex.get("index") or 0)] = ex

    plan: list[dict] = []
    for i in range(count):
        due = base if i == 0 else base + timedelta(days=gap_days * i)
        idx = i + 1
        entry: dict[str, Any] = {
            "index": idx,
            "amount_rial": amounts[i],
            "due_at": due.isoformat(),
            "status": "pending",
        }
        if idx in paid_by_index:
            ex = paid_by_index[idx]
            entry["status"] = "paid"
            entry["paid_at"] = ex.get("paid_at")
            entry["payment_ref"] = ex.get("payment_ref")
        plan.append(entry)
    return plan


def detach_stale_interview_payment_amount(ctx: dict, tuition_total_rial: int) -> dict:
    """Move leftover interview fee out of payment_amount_rial before tuition payment."""
    out = dict(ctx)
    stale = out.get("payment_amount_rial")
    if not _valid_rial(stale):
        return out
    stale_int = int(stale)
    if stale_int == tuition_total_rial:
        return out
    if stale_int < tuition_total_rial:
        if not _valid_rial(out.get("interview_payment_amount_rial")):
            out["interview_payment_amount_rial"] = stale_int
        out.pop("payment_amount_rial", None)
    return out


def get_current_payable_from_plan(plan: list[dict]) -> tuple[int, int | None]:
    from app.utils.shamsi_calendar_utils import tehran_today

    today = tehran_today().isoformat()
    for item in plan:
        status = item.get("status")
        if status == "paid":
            continue
        if status == "overdue" or status == "pending":
            return int(item["amount_rial"]), int(item["index"])
    return 0, None


def apply_tuition_payment_context(
    ctx: dict,
    *,
    gap_days: int = DEFAULT_INSTALLMENT_GAP_DAYS,
) -> dict:
    """Augment context with tuition totals, installment plan, and payable amount."""
    out = dict(ctx)
    total = out.get("tuition_total_rial")
    if not _valid_rial(total):
        if _valid_rial(out.get("payment_amount_rial")) and not out.get("installment_plan"):
            total = int(out["payment_amount_rial"])
        elif out.get("invoice_amount") is not None:
            try:
                total = int(round(float(out["invoice_amount"]) * 10))
            except (TypeError, ValueError):
                total = None
    if not _valid_rial(total):
        return out

    total = int(total)
    out = detach_stale_interview_payment_amount(out, total)
    out["tuition_total_rial"] = total
    out["tuition_amount_rial"] = total
    out["tuition_amount"] = float(total) / 10.0

    pm = out.get("payment_method")
    if not pm:
        out["payable_amount_rial"] = total
        out["payment_amount_rial"] = total
        out["payment_method_selected"] = False
        return out
    out["payment_method_selected"] = True

    try:
        ic = int(out["installment_count"]) if out.get("installment_count") is not None else None
    except (TypeError, ValueError):
        ic = None

    base_due = _parse_date(out.get("term_start_date"))
    if base_due is None:
        from app.utils.shamsi_calendar_utils import tehran_today

        base_due = tehran_today()
    existing = out.get("installment_plan")
    existing_plan = list(existing) if isinstance(existing, list) and existing else None
    # اگر تعداد اقساط با برنامه قبلی هم‌خوان نیست، از نو بساز
    if existing_plan and pm == "installment" and ic is not None:
        try:
            if len(existing_plan) != int(ic):
                existing_plan = None
        except (TypeError, ValueError):
            existing_plan = None
    if existing_plan and pm == "cash":
        first = existing_plan[0] if existing_plan else {}
        if first.get("status") != "paid":
            existing_plan = None
    plan = compute_installment_plan(total, str(pm), ic, base_due, gap_days, existing_plan)
    out["installment_plan"] = plan

    if pm == "cash":
        out["payable_amount_rial"] = total
        out["payment_amount_rial"] = total
        out["current_installment_index"] = 1
        cash_paid = bool(plan) and plan[0].get("status") == "paid"
        out["pending_installments_remaining"] = 0
        out.pop("next_installment_due_at", None)
        if cash_paid:
            out["payable_amount_rial"] = 0
            out["payment_amount_rial"] = 0
        return out

    payable, idx = get_current_payable_from_plan(plan)
    out["payable_amount_rial"] = payable
    out["payment_amount_rial"] = payable
    if idx:
        out["current_installment_index"] = idx
    pending = sum(1 for p in plan if p.get("status") in ("pending", "overdue"))
    out["pending_installments_remaining"] = pending
    next_item = next((p for p in plan if p.get("status") in ("pending", "overdue")), None)
    if next_item:
        out["next_installment_due_at"] = next_item.get("due_at")
    return out


def mark_installment_paid(
    ctx: dict,
    payment_ref: str,
    amount_rial: int,
    *,
    gap_days: int = DEFAULT_INSTALLMENT_GAP_DAYS,
) -> dict:
    """Mark current installment paid and advance counters."""
    out = dict(ctx)
    plan = [dict(p) for p in (out.get("installment_plan") or [])]
    idx = out.get("current_installment_index")
    marked = False
    for i, item in enumerate(plan):
        if item.get("status") == "paid":
            continue
        if idx is None or int(item.get("index") or 0) == int(idx):
            item["status"] = "paid"
            item["paid_at"] = datetime.now(timezone.utc).isoformat()
            item["payment_ref"] = payment_ref
            if amount_rial > 0:
                item["amount_rial"] = int(amount_rial)
            plan[i] = item
            marked = True
            break
    if not marked and plan:
        for i, item in enumerate(plan):
            if item.get("status") != "paid":
                item["status"] = "paid"
                item["paid_at"] = datetime.now(timezone.utc).isoformat()
                item["payment_ref"] = payment_ref
                plan[i] = item
                break

    out["installment_plan"] = plan
    pending_items = [p for p in plan if p.get("status") in ("pending", "overdue")]
    out["pending_installments_remaining"] = len(pending_items)
    next_item = pending_items[0] if pending_items else None
    if next_item:
        out["next_installment_due_at"] = next_item.get("due_at")
        out["current_installment_index"] = next_item.get("index")
        payable = int(next_item.get("amount_rial") or 0)
        out["payable_amount_rial"] = payable
        out["payment_amount_rial"] = payable
    else:
        out.pop("next_installment_due_at", None)
        out.pop("current_installment_index", None)
        out["payable_amount_rial"] = 0
    return apply_tuition_payment_context(out, gap_days=gap_days)


def installment_sms_still_owed(ctx: dict | None) -> bool:
    """True only when an installment plan still has unpaid remaining dues."""
    data = ctx if isinstance(ctx, dict) else {}
    if str(data.get("payment_method") or "") != "installment":
        return False
    plan = data.get("installment_plan") or []
    if isinstance(plan, list) and plan:
        return any(
            isinstance(p, dict) and p.get("status") in ("pending", "overdue")
            for p in plan
        )
    try:
        pending = int(data.get("pending_installments_remaining") or 0)
    except (TypeError, ValueError):
        pending = 0
    return pending > 0


def cancel_unsent_installment_reminders(
    student: Student,
    *,
    instance_id: str | uuid.UUID | None = None,
    reason: str = "settled",
) -> int:
    """Mark unsent installment SMS reminders as skipped so the scheduler will not send them."""
    extra = dict(student.extra_data or {}) if isinstance(student.extra_data, dict) else {}
    items = list(extra.get("scheduled_reminders") or [])
    if not items:
        return 0
    iid = str(instance_id) if instance_id is not None else None
    now = datetime.now(timezone.utc).isoformat()
    changed = 0
    for rec in items:
        if not isinstance(rec, dict):
            continue
        if rec.get("sent"):
            continue
        if rec.get("type") != "installment":
            continue
        if iid is not None and str(rec.get("instance_id") or "") != iid:
            continue
        rec["sent"] = True
        rec["skipped"] = True
        rec["skipped_reason"] = reason
        rec["sent_at"] = now
        changed += 1
    if changed:
        extra["scheduled_reminders"] = items
        student.extra_data = extra
        flag_modified(student, "extra_data")
    return changed


def sync_installment_reminder_queue(
    student: Student,
    instance: ProcessInstance,
    ctx: dict | None = None,
) -> int:
    """Drop queued installment SMS when the student is cash-paid or fully settled."""
    data = ctx if isinstance(ctx, dict) else dict(instance.context_data or {})
    if installment_sms_still_owed(data):
        return 0
    reason = "not_installment" if str(data.get("payment_method") or "") != "installment" else "settled"
    return cancel_unsent_installment_reminders(
        student,
        instance_id=str(instance.id),
        reason=reason,
    )


async def refresh_instance_tuition_context(
    db: AsyncSession,
    process_code: str,
    state_code: str,
    ctx: dict,
) -> dict:
    """Resolve tuition total and payable from student selections."""
    if process_code not in TUITION_INSTALLMENT_PROCESS_CODES:
        return ctx
    if state_code not in TUITION_PAYMENT_STATES:
        return ctx

    from app.services.installment_settings_service import get_installment_policy
    from app.services.term_course_offering_service import resolve_registration_fees

    out = dict(ctx)
    fees = await resolve_registration_fees(db, process_code, out, state_code)
    if fees.get("fee_source"):
        out["fee_source"] = fees["fee_source"]
    if fees.get("tuition_reason_fa"):
        out["tuition_reason_fa"] = fees["tuition_reason_fa"]
    if fees.get("tuition_lines") is not None:
        out["tuition_lines"] = fees["tuition_lines"]

    # همیشه از انتخاب فعلی دوباره حساب شود
    total = fees.get("tuition_total_rial")
    if not _valid_rial(total):
        try:
            tom = float(fees.get("registration_tuition_invoice_toman") or 0)
            if tom > 0:
                total = int(round(tom * 10))
        except (TypeError, ValueError):
            total = None
    if _valid_rial(total):
        out["tuition_total_rial"] = int(total)
        out["tuition_amount_rial"] = int(total)
        out["tuition_amount"] = float(total) / 10.0
        out["invoice_amount"] = float(total) / 10.0

    policy = await get_installment_policy(db)
    gap_days = int(policy.get("term2_installment_gap_days") or DEFAULT_INSTALLMENT_GAP_DAYS)
    return apply_tuition_payment_context(out, gap_days=gap_days)


async def resolve_expected_payable_rial(
    db: AsyncSession,
    instance: ProcessInstance,
) -> Optional[int]:
    """Server-side payable amount for gateway validation."""
    if instance.process_code not in TUITION_INSTALLMENT_PROCESS_CODES:
        return None
    ctx = await refresh_instance_tuition_context(
        db,
        instance.process_code,
        instance.current_state_code or "",
        dict(instance.context_data or {}),
    )
    payable = ctx.get("payable_amount_rial")
    if _valid_rial(payable):
        return int(payable)
    if _valid_rial(ctx.get("payment_amount_rial")):
        return int(ctx["payment_amount_rial"])
    return None


def is_tuition_gateway_state(process_code: str, state_code: str) -> bool:
    if process_code not in TUITION_INSTALLMENT_PROCESS_CODES:
        return False
    return state_code in {
        "payment",
        "payment_processing",
        "installment_overdue",
        "registration_complete",
    }


async def apply_post_payment_context_update(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    payment_ref: str,
    amount_rial: int,
) -> dict:
    """Update installment plan after successful gateway payment."""
    from app.services.installment_settings_service import get_installment_policy

    policy = await get_installment_policy(db)
    gap_days = int(policy.get("term2_installment_gap_days") or DEFAULT_INSTALLMENT_GAP_DAYS)
    ctx = dict(instance.context_data or {})
    ctx = await refresh_instance_tuition_context(
        db,
        instance.process_code,
        instance.current_state_code or "",
        ctx,
    )
    if ctx.get("payment_method") in ("installment", "cash"):
        ctx = mark_installment_paid(ctx, payment_ref, amount_rial, gap_days=gap_days)
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()
    student = await db.get(Student, instance.student_id) if instance.student_id else None
    if student is not None:
        sync_installment_reminder_queue(student, instance, ctx)
    return ctx


async def build_student_finance_summary(db: AsyncSession, student_id: uuid.UUID) -> dict:
    """Aggregate balance, ledger, and installment plans for student profile."""
    from app.services.payment_service import PaymentService

    payment_svc = PaymentService(db)
    balance = await payment_svc.get_student_balance(student_id)
    by_cat = await payment_svc.get_student_balances_by_category(student_id)
    history = await payment_svc.get_student_financial_history(student_id, limit=200)

    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.student_id == student_id,
            ProcessInstance.process_code.in_(TUITION_INSTALLMENT_PROCESS_CODES),
            ProcessInstance.is_cancelled.is_(False),
        )
        .order_by(ProcessInstance.last_transition_at.desc())
    )
    instances = list((await db.execute(stmt)).scalars().all())

    installments: list[dict] = []
    open_payments: list[dict] = []
    for inst in instances:
        ctx = dict(inst.context_data or {})
        ctx = await refresh_instance_tuition_context(
            db,
            inst.process_code,
            inst.current_state_code or "",
            ctx,
        )
        plan = ctx.get("installment_plan") or []
        for item in plan:
            installments.append(
                {
                    **item,
                    "process_code": inst.process_code,
                    "instance_id": str(inst.id),
                    "process_state": inst.current_state_code,
                }
            )
        payable = ctx.get("payable_amount_rial")
        if (
            ctx.get("payment_method") == "installment"
            and _valid_rial(payable)
            and int(ctx.get("pending_installments_remaining") or 0) > 0
        ):
            open_payments.append(
                {
                    "instance_id": str(inst.id),
                    "process_code": inst.process_code,
                    "process_state": inst.current_state_code,
                    "payable_amount_rial": int(payable),
                    "current_installment_index": ctx.get("current_installment_index"),
                    "next_installment_due_at": ctx.get("next_installment_due_at"),
                    "tuition_total_rial": ctx.get("tuition_total_rial"),
                }
            )

    def _wallet(key: str) -> dict:
        w = by_cat.get(key) or {}
        return {
            "total_paid": w.get("total_payments", 0),
            "total_credit": w.get("total_credits", 0),
            "total_debt": w.get("total_debts", 0),
            "net_balance": w.get("balance", 0),
            "has_outstanding_debt": w.get("has_outstanding_debt", False),
        }

    return {
        "balance": {
            "total_paid": balance.get("total_payments", 0),
            "total_credit": balance.get("total_credits", 0),
            "total_debt": balance.get("total_debts", 0),
            "net_balance": balance.get("balance", 0),
            "has_outstanding_debt": balance.get("has_outstanding_debt", False),
        },
        "wallets": {
            "therapy": _wallet("therapy"),
            "supervision": _wallet("supervision"),
            "tuition": _wallet("tuition"),
        },
        "ledger": [
            {
                "id": r.get("id"),
                "record_type": r.get("type"),
                "amount": r.get("amount"),
                "description_fa": r.get("description"),
                "ledger_category": r.get("ledger_category") or "other",
                "created_at": r.get("created_at"),
            }
            for r in history
        ],
        "installments": installments,
        "open_payments": open_payments,
    }
