"""Service I - Termination / Accounting Records Service.

Replaces the log-only stub for termination and accounting records. Persisted
under ``Student.extra_data``:

    termination        -> {"date", "recorded_in_portal", ...}
    accounting_entries -> ledger entries (amount, kind, ref)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.workflow import _common as C


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
