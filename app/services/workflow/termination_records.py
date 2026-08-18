"""Service I - Termination / Accounting Records Service.

Replaces the log-only stub for termination and accounting records. Persisted
under ``Student.extra_data``:

    termination        -> {"date", "recorded_in_portal", ...}
    accounting_entries -> ledger entries (amount, kind, ref)

For tuition (SOP 40+): also creates a ``FinancialRecord`` payment with
``ledger_category=tuition`` for the finance dashboard.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import FinancialRecord, ProcessInstance
from app.services.workflow import _common as C

TUITION_PROCESS_CODES = frozenset({
    "introductory_course_registration",
    "intro_second_semester_registration",
    "comprehensive_course_registration",
    "comprehensive_term_start",
})

TUITION_DESC_PREFIX = "شهریه ترم"


def _as_float(raw: Any, default: float = 0.0) -> float:
    try:
        if raw is None or raw == "":
            return default
        return float(raw)
    except (TypeError, ValueError):
        return default


def _tuition_amount_toman(ctx: dict) -> float:
    """Resolve payable tuition amount in toman from process context."""
    for key in (
        "payable_amount_toman",
        "invoice_amount",
        "amount",
        "total_tuition_toman",
        "payment_amount_toman",
    ):
        v = _as_float(ctx.get(key), 0.0)
        if v > 0:
            return v
    rial = _as_float(
        ctx.get("payable_amount_rial")
        or ctx.get("payment_amount_rial")
        or ctx.get("invoice_amount_rial"),
        0.0,
    )
    if rial > 0:
        return rial / 10.0
    return 0.0


def _payer_name(student: Any, ctx: dict) -> str:
    for key in ("payer_name_fa", "student_name_fa", "full_name_fa", "name_fa"):
        v = ctx.get(key)
        if v and str(v).strip():
            return str(v).strip()
    code = getattr(student, "student_code", None) or ""
    return str(code).strip() or "—"


def _tuition_purpose_fa(instance: ProcessInstance, ctx: dict) -> str:
    term = ctx.get("term_label_fa") or ctx.get("term_name_fa") or ctx.get("term") or ""
    if term:
        return f"{TUITION_DESC_PREFIX} {term}"
    labels = {
        "introductory_course_registration": f"{TUITION_DESC_PREFIX} دوره آشنایی",
        "intro_second_semester_registration": f"{TUITION_DESC_PREFIX} دوم آشنایی",
        "comprehensive_course_registration": f"{TUITION_DESC_PREFIX} ورود جامع",
        "comprehensive_term_start": f"{TUITION_DESC_PREFIX} دوره جامع",
    }
    return labels.get(instance.process_code, TUITION_DESC_PREFIX)


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    ctx = C.merged_context(instance, action, context)
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"

    extra = C.student_extra(student)
    result = action_type

    if action_type in ("record_termination_date", "record_termination_in_student_portal"):
        term = dict(extra.get("termination") or {})
        if action_type == "record_termination_date":
            term["date"] = (
                ctx.get("termination_date")
                or ctx.get("end_date")
                or datetime.now(timezone.utc).date().isoformat()
            )
            term["date_recorded_at"] = C.now_iso()
        else:
            term["recorded_in_portal"] = True
            term["portal_recorded_at"] = C.now_iso()
            term.setdefault("reason_fa", ctx.get("termination_reason_fa") or ctx.get("reason_fa"))
        term["process_code"] = instance.process_code
        extra["termination"] = term
        result = f"termination_recorded ({'date' if 'date' in action_type else 'portal'})"

    elif action_type == "record_accounting":
        is_tuition = (
            instance.process_code in TUITION_PROCESS_CODES
            or (ctx.get("accounting_kind") or action.get("kind") or "") == "tuition"
            or action.get("ledger_category") == "tuition"
        )
        if is_tuition:
            amount = _tuition_amount_toman(ctx)
            if amount <= 0:
                amount = _as_float(action.get("amount"), 0.0)
            purpose = _tuition_purpose_fa(instance, ctx)
            payer = _payer_name(student, ctx)
            desc = f"{purpose} — پرداخت‌کننده: {payer}"
            record = FinancialRecord(
                id=uuid.uuid4(),
                student_id=instance.student_id,
                record_type="payment",
                amount=amount,
                description_fa=desc,
                reference_id=instance.id,
                ledger_category="tuition",
                accounting_status="pending",
                created_at=datetime.now(timezone.utc),
            )
            db.add(record)
            entry = {
                "id": str(record.id),
                "kind": "tuition",
                "amount": amount,
                "purpose_fa": purpose,
                "payer_name_fa": payer,
                "reference": str(instance.id),
                "process_code": instance.process_code,
                "financial_record_id": str(record.id),
                "accounting_status": "pending",
                "recorded_at": C.now_iso(),
            }
            entries = list(extra.get("accounting_entries") or [])
            entries.append(entry)
            extra["accounting_entries"] = entries
            result = f"tuition_accounting_recorded amount={amount} record={record.id}"
        else:
            try:
                amount = float(ctx.get("amount") or action.get("amount") or 0)
            except (TypeError, ValueError):
                amount = 0.0
            entry = {
                "id": C.new_id(),
                "kind": ctx.get("accounting_kind") or action.get("kind") or "adjustment",
                "amount": amount,
                "reference": ctx.get("reference") or str(instance.id),
                "process_code": instance.process_code,
                "recorded_at": C.now_iso(),
            }
            entries = list(extra.get("accounting_entries") or [])
            entries.append(entry)
            extra["accounting_entries"] = entries
            result = f"accounting_recorded amount={amount}"

    else:
        C.record_event(instance, action_type, {"unhandled_in": "termination_records"})
        return f"termination_noop:{action_type}"

    C.commit_student_extra(student, extra)
    C.record_event(instance, action_type, {"result": result})
    return result
