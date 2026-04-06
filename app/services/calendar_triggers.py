"""تریگرهای زمان‌محور (تقویمی) — مکمل SLA.

موارد مثل ``payment_timeout``، ``send_return_reminder``، ``return_deadline_passed``،
``session_time_reached``، ``installment_due_date_passed`` (ترم دوم آشنایی)، و
پس از مهلت ۲۴ ساعت ``therapist_did_not_record`` (حضور درمان) را در فواصل منظم بررسی
و با نقش ``system`` اجرا می‌کند.

نیاز به داده در ``context_data`` (مثلاً ``return_reminder_at``) در مستند
``docs/CALENDAR_TRIGGERS_FA.md`` توضیح داده شده است.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta, date, time
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.engine import StateMachineEngine, InvalidTransitionError
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import ProcessInstance

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            s = value.replace("Z", "+00:00")
            d = datetime.fromisoformat(s)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception:
            return None
    return None


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except Exception:
            return None
    return None


async def _get_state_sla_hours(db: AsyncSession, process_code: str, state_code: str) -> Optional[int]:
    stmt = (
        select(StateDefinition.sla_hours)
        .join(ProcessDefinition, StateDefinition.process_id == ProcessDefinition.id)
        .where(
            ProcessDefinition.code == process_code,
            ProcessDefinition.is_active == True,
            StateDefinition.code == state_code,
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def _run_payment_timeouts(db: AsyncSession, now: datetime) -> list[dict]:
    out = []
    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "session_payment",
        ProcessInstance.current_state_code == "awaiting_payment",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    result = await db.execute(stmt)
    for instance in result.scalars().all():
        sla = await _get_state_sla_hours(db, "session_payment", "awaiting_payment")
        hours = float(sla) if sla is not None else 72.0
        deadline = instance.last_transition_at + timedelta(hours=hours)
        if now <= deadline:
            continue
        try:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="payment_timeout",
                actor_id=SYSTEM_ACTOR_ID,
                actor_role="system",
            )
            if r.success:
                out.append({"instance_id": str(instance.id), "trigger": "payment_timeout"})
            else:
                logger.debug("payment_timeout skipped: %s", r.error)
        except (InvalidTransitionError, Exception) as e:
            logger.warning("payment_timeout failed: %s", e)
    return out


async def _run_leave_reminders(db: AsyncSession, now: datetime) -> list[dict]:
    out = []
    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "educational_leave",
        ProcessInstance.current_state_code == "on_leave",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    result = await db.execute(stmt)
    for instance in result.scalars().all():
        ctx = dict(instance.context_data or {})
        rra = _parse_iso_datetime(ctx.get("return_reminder_at"))
        if not rra or now < rra:
            continue
        try:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="send_return_reminder",
                actor_id=SYSTEM_ACTOR_ID,
                actor_role="system",
            )
            if r.success:
                out.append({"instance_id": str(instance.id), "trigger": "send_return_reminder"})
        except Exception as e:
            logger.warning("send_return_reminder failed: %s", e)
    return out


async def _run_leave_return_deadline(db: AsyncSession, now: datetime) -> list[dict]:
    out = []
    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "educational_leave",
        ProcessInstance.current_state_code == "return_reminder_sent",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    result = await db.execute(stmt)
    for instance in result.scalars().all():
        ctx = dict(instance.context_data or {})
        rda = _parse_iso_datetime(ctx.get("return_deadline_at"))
        if not rda or now < rda:
            continue
        try:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="return_deadline_passed",
                actor_id=SYSTEM_ACTOR_ID,
                actor_role="system",
            )
            if r.success:
                out.append({"instance_id": str(instance.id), "trigger": "return_deadline_passed"})
        except Exception as e:
            logger.warning("return_deadline_passed failed: %s", e)
    return out


async def _run_supervision_50h_session_time(db: AsyncSession, today: date) -> list[dict]:
    """همان منطق حضور درمان، برای فرایند تکمیل ۵۰ ساعت سوپرویژن."""
    out = []
    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "supervision_50h_completion",
        ProcessInstance.current_state_code == "session_scheduled",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    result = await db.execute(stmt)
    for instance in result.scalars().all():
        ctx = instance.context_data or {}
        sd = _parse_date(ctx.get("session_date") or ctx.get("supervision_session_date"))
        if not sd or sd > today:
            continue
        try:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="session_time_reached",
                actor_id=SYSTEM_ACTOR_ID,
                actor_role="system",
            )
            if r.success:
                out.append({"instance_id": str(instance.id), "trigger": "session_time_reached_supervision_50h"})
            else:
                logger.debug("supervision_50h session_time_reached: %s", r.error)
        except Exception as e:
            logger.warning("supervision_50h session_time_reached failed: %s", e)
    return out


async def _run_attendance_session_time(db: AsyncSession, today: date) -> list[dict]:
    """زمان جلسه رسیده: اگر ``session_date`` در context به امروز یا قبل باشد."""
    out = []
    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "attendance_tracking",
        ProcessInstance.current_state_code == "session_scheduled",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    result = await db.execute(stmt)
    for instance in result.scalars().all():
        ctx = instance.context_data or {}
        sd = _parse_date(ctx.get("session_date"))
        if not sd or sd > today:
            continue
        try:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="session_time_reached",
                actor_id=SYSTEM_ACTOR_ID,
                actor_role="system",
            )
            if r.success:
                out.append({"instance_id": str(instance.id), "trigger": "session_time_reached"})
            else:
                logger.debug(
                    "session_time_reached no branch: %s",
                    r.error,
                )
        except Exception as e:
            logger.warning("session_time_reached failed: %s", e)
    return out


async def _run_intro_second_semester_installment_due(db: AsyncSession, today: date) -> list[dict]:
    """قسط ترم دوم: ``registration_complete`` + اقساط باز + سررسید ≤ امروز → ``installment_overdue``."""
    out = []
    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "intro_second_semester_registration",
        ProcessInstance.current_state_code == "registration_complete",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    result = await db.execute(stmt)
    for instance in result.scalars().all():
        ctx = instance.context_data or {}
        try:
            pend = int(ctx.get("pending_installments_remaining") or 0)
        except (TypeError, ValueError):
            pend = 0
        if pend <= 0:
            continue
        due_raw = ctx.get("next_installment_due_at")
        due_d = _parse_date(due_raw)
        if not due_d or due_d > today:
            continue
        try:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="installment_due_date_passed",
                actor_id=SYSTEM_ACTOR_ID,
                actor_role="system",
            )
            if r.success:
                out.append(
                    {
                        "instance_id": str(instance.id),
                        "trigger": "installment_due_date_passed",
                    }
                )
            else:
                logger.debug("installment_due_date_passed skipped: %s", r.error)
        except Exception as e:
            logger.warning("installment_due_date_passed failed: %s", e)
    return out


async def _run_attendance_therapist_not_recorded_deadline(db: AsyncSession, now: datetime) -> list[dict]:
    """پس از ۲۴ ساعت از نیمه‌شب روز جلسه، اگر درمانگر هنوز ثبت نکرده → ``therapist_did_not_record``."""
    out = []
    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "attendance_tracking",
        ProcessInstance.current_state_code == "therapist_recording",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    result = await db.execute(stmt)
    for instance in result.scalars().all():
        ctx = instance.context_data or {}
        sd = _parse_date(ctx.get("session_date"))
        if not sd:
            continue
        deadline = datetime.combine(sd, time.min, tzinfo=timezone.utc) + timedelta(hours=24)
        if now < deadline:
            continue
        try:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="therapist_did_not_record",
                actor_id=SYSTEM_ACTOR_ID,
                actor_role="system",
            )
            if r.success:
                out.append(
                    {
                        "instance_id": str(instance.id),
                        "trigger": "therapist_did_not_record",
                    }
                )
            else:
                logger.debug("therapist_did_not_record skipped: %s", r.error)
        except Exception as e:
            logger.warning("therapist_did_not_record failed: %s", e)
    return out


async def run_calendar_trigger_pass(db: AsyncSession) -> dict[str, Any]:
    """یک دور کامل بررسی تریگرهای تقویمی."""
    now = datetime.now(timezone.utc)
    today = now.date()
    payment = await _run_payment_timeouts(db, now)
    leave_r = await _run_leave_reminders(db, now)
    leave_d = await _run_leave_return_deadline(db, now)
    att = await _run_attendance_session_time(db, today)
    sup50 = await _run_supervision_50h_session_time(db, today)
    inst2 = await _run_intro_second_semester_installment_due(db, today)
    th_att = await _run_attendance_therapist_not_recorded_deadline(db, now)
    parts = [payment, leave_r, leave_d, att, sup50, inst2, th_att]
    return {
        "at": now.isoformat(),
        "payment_timeout": payment,
        "send_return_reminder": leave_r,
        "return_deadline_passed": leave_d,
        "session_time_reached_attendance": att,
        "session_time_reached_supervision_50h": sup50,
        "installment_due_intro_second_semester": inst2,
        "therapist_did_not_record_attendance": th_att,
        "fired_total": sum(len(p) for p in parts),
    }


class CalendarTriggerMonitor:
    def __init__(self):
        self._running = False

    async def start_loop(self, db_factory, interval_seconds: int = 300):
        self._running = True
        logger.info("Calendar trigger monitor started (interval: %ss)", interval_seconds)
        try:
            while self._running:
                try:
                    settings = get_settings()
                    if not getattr(settings, "CALENDAR_TRIGGERS_ENABLED", True):
                        await asyncio.sleep(interval_seconds)
                        continue
                    async with db_factory() as db:
                        summary = await run_calendar_trigger_pass(db)
                        if summary.get("fired_total"):
                            logger.info("Calendar triggers fired: %s", summary)
                        await db.commit()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error("Calendar trigger pass error: %s", e, exc_info=True)
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            self._running = False
            logger.info("Calendar trigger monitor cancelled")
            raise

    def stop(self):
        self._running = False
        logger.info("Calendar trigger monitor stopped")


calendar_trigger_monitor = CalendarTriggerMonitor()
