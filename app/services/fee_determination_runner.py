"""اجرای خودکار ترنزیشن‌های fee_determination پس از start_process و جمع‌زدن نمونه‌های گیرکرده."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine, InvalidTransitionError
from app.models.operational_models import ProcessInstance, TherapySession

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_FEE_DETERMINATION_SUMMARY_FA: dict[str, str] = {
    "scenario_1_credit_returned": "تعیین تکلیف مالی: یک جلسه به بستانکاری شما اضافه شد.",
    "scenario_2_no_action": "تعیین تکلیف مالی: در محدوده سهمیه سالانه بدون اقدام مالی ثبت شد.",
    "scenario_3_forfeited": "تعیین تکلیف مالی: با توجه به پرداخت قبلی و اتمام سهمیه، هزینه جلسه مصادره ثبت شد.",
    "scenario_4_debt_created": "تعیین تکلیف مالی: به دلیل اتمام سهمیه و عدم پرداخت، بدهی یا تسویه از بستانکاری ثبت شد. در صورت بدهی، از فرایند «پرداخت جلسات» پیگیری کنید.",
    "excluded": "تعیین تکلیف مالی: این مورد خارج از شمول مالی بود (وقفه یا لغو توسط درمانگر/سوپروایزر).",
}


def summary_fa_for_fee_determination_state(state_code: str) -> str:
    return _FEE_DETERMINATION_SUMMARY_FA.get(
        state_code,
        "تعیین تکلیف مالی جلسه ثبت شد.",
    )


async def attach_fee_determination_completion_ui_hint(
    db: AsyncSession, instance: ProcessInstance
) -> None:
    if instance.process_code != "fee_determination" or not instance.is_completed:
        return
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    ctx["ui_completion_summary_fa"] = summary_fa_for_fee_determination_state(instance.current_state_code)
    instance.context_data = ctx
    flag_modified(instance, "context_data")


async def complete_fee_determination_instance(
    db: AsyncSession,
    instance_id: uuid.UUID,
) -> dict[str, Any]:
    """
    پس از start_process: ابتدا precheck (وقفه/کنسلی ارائه‌دهنده)، در صورت عدم تطابق evaluate (۴ سناریو).
    """
    engine = StateMachineEngine(db)
    inst = await engine.get_process_instance(instance_id)
    if inst.process_code != "fee_determination":
        return {"skipped": True, "reason": "not_fee_determination"}
    if inst.is_completed or inst.is_cancelled:
        return {"skipped": True, "reason": "already_done"}
    if inst.current_state_code != "triggered":
        return {"skipped": True, "reason": f"unexpected_state:{inst.current_state_code}"}

    out: dict[str, Any] = {"instance_id": str(instance_id), "steps": []}

    r1 = await engine.execute_transition(
        instance_id=instance_id,
        trigger_event="precheck",
        actor_id=SYSTEM_ACTOR_ID,
        actor_role="system",
        payload={},
    )
    out["steps"].append({"trigger": "precheck", "success": r1.success, "error": getattr(r1, "error", None)})
    await db.refresh(inst)
    if inst.is_completed:
        out["completed"] = True
        out["terminal_state"] = inst.current_state_code
        return out

    r2 = await engine.execute_transition(
        instance_id=instance_id,
        trigger_event="evaluate",
        actor_id=SYSTEM_ACTOR_ID,
        actor_role="system",
        payload={},
    )
    out["steps"].append({"trigger": "evaluate", "success": r2.success, "error": getattr(r2, "error", None)})
    await db.refresh(inst)
    if inst.is_completed:
        out["completed"] = True
        out["terminal_state"] = inst.current_state_code
    else:
        out["completed"] = False
        out["error"] = getattr(r2, "error", None) or "evaluate did not complete instance"
    return out


async def sweep_stuck_fee_determination_triggered(db: AsyncSession) -> list[dict[str, Any]]:
    """نمونه‌های fee_determination که هنوز در triggered مانده‌اند (ایمنی در برابر خطای قبلی)."""
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "fee_determination",
        ProcessInstance.current_state_code == "triggered",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    out: list[dict[str, Any]] = []
    for inst in rows:
        try:
            detail = await complete_fee_determination_instance(db, inst.id)
            out.append({"instance_id": str(inst.id), **detail})
        except (InvalidTransitionError, Exception) as e:
            logger.warning("sweep fee_determination failed instance=%s: %s", inst.id, e)
            out.append({"instance_id": str(inst.id), "error": str(e)})
    return out


async def enrich_fee_determination_payload_from_therapy_session(
    db: AsyncSession,
    student_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """اگر therapy_session_id در payload است، session_paid و session_date را از DB پر کن."""
    merged = dict(payload or {})
    sid_raw = merged.get("therapy_session_id") or merged.get("session_id")
    if not sid_raw:
        return merged
    try:
        sid = uuid.UUID(str(sid_raw))
    except (ValueError, TypeError):
        return merged
    stmt = select(TherapySession).where(
        TherapySession.id == sid,
        TherapySession.student_id == student_id,
    )
    res = await db.execute(stmt)
    ts = res.scalars().first()
    if not ts:
        return merged
    merged["therapy_session_id"] = str(ts.id)
    merged["session_paid"] = ts.payment_status == "paid"
    merged["session_date"] = ts.session_date.isoformat() if ts.session_date else None
    if merged.get("session_cancelled_by_provider") is None:
        merged["session_cancelled_by_provider"] = ts.status == "cancelled"
    return merged
