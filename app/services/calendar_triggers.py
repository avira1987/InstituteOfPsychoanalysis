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
from app.models.operational_models import ProcessInstance, InterviewSlot, Student, User
from app.services.notification_service import notification_service
from app.services.student_service import StudentService
from app.services.fee_determination_runner import sweep_stuck_fee_determination_triggered
from app.services.attendance_tracking_sync import sync_all_open_attendance_instances_from_sessions
from app.services.sms_gateway import send_sms, normalize_ir_mobile
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _context_as_dict(instance: ProcessInstance) -> dict[str, Any]:
    """JSONB / ردیف قدیمی: ``context_data`` گاهی رشتهٔ JSON است (مشابه ``StateMachineEngine._as_mapping``)."""
    return StateMachineEngine._as_mapping(instance.context_data)


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


async def _run_session_payment_sla_reminders(db: AsyncSession, now: datetime) -> list[dict]:
    """یادآوری پیامکی قبل از پایان مهلت SLA برای session_payment / awaiting_payment."""
    settings = get_settings()
    try:
        hours_before = float(
            getattr(settings, "SESSION_PAYMENT_REMINDER_HOURS_BEFORE_DEADLINE", 24.0)
        )
    except (TypeError, ValueError):
        hours_before = 24.0
    out: list[dict] = []
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "session_payment",
        ProcessInstance.current_state_code == "awaiting_payment",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for instance in rows:
        ctx = _context_as_dict(instance)
        if ctx.get("payment_sla_reminder_sent"):
            continue
        sla = await _get_state_sla_hours(db, "session_payment", "awaiting_payment")
        try:
            hours_total = float(sla) if sla is not None else 72.0
        except (TypeError, ValueError):
            hours_total = 72.0
        lt = instance.last_transition_at
        if lt is None:
            continue
        if lt.tzinfo is None:
            lt = lt.replace(tzinfo=timezone.utc)
        deadline = lt + timedelta(hours=hours_total)
        remind_from = deadline - timedelta(hours=hours_before)
        if now < remind_from or now >= deadline:
            continue
        student = await db.get(Student, instance.student_id)
        if not student or not student.user_id:
            continue
        user = await db.get(User, student.user_id)
        if not user:
            continue
        phone = normalize_ir_mobile(user.phone or "")
        if not phone or len(phone) < 10:
            continue
        msg = notification_service.get_template("session_payment_sla_payment", "sms")
        if not msg:
            continue
        try:
            await send_sms(phone, msg)
        except Exception as e:
            logger.warning("session_payment SLA reminder SMS failed instance=%s: %s", instance.id, e)
            continue
        ctx["payment_sla_reminder_sent"] = now.isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        out.append({"instance_id": str(instance.id), "template": "session_payment_sla_payment"})
    return out


async def _run_payment_timeouts(db: AsyncSession, now: datetime) -> list[dict]:
    """مهلت پرداخت: session_payment و extra_session."""
    out = []
    engine = StateMachineEngine(db)
    specs = [
        ("session_payment", "awaiting_payment", 72.0),
        ("extra_session", "payment_required", 48.0),
    ]
    for pcode, st_code, default_h in specs:
        stmt = select(ProcessInstance).where(
            ProcessInstance.process_code == pcode,
            ProcessInstance.current_state_code == st_code,
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        result = await db.execute(stmt)
        for instance in result.scalars().all():
            sla = await _get_state_sla_hours(db, pcode, st_code)
            try:
                hours = float(sla) if sla is not None else default_h
            except (TypeError, ValueError):
                hours = default_h
            lt = instance.last_transition_at
            if lt is None:
                continue
            if lt.tzinfo is None:
                lt = lt.replace(tzinfo=timezone.utc)
            deadline = lt + timedelta(hours=hours)
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
                    out.append(
                        {"instance_id": str(instance.id), "trigger": "payment_timeout", "process": pcode}
                    )
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
        ctx = _context_as_dict(instance)
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
        ctx = _context_as_dict(instance)
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
        ctx = _context_as_dict(instance)
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
        ctx = _context_as_dict(instance)
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
        ctx = _context_as_dict(instance)
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
        ctx = _context_as_dict(instance)
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


async def _run_extra_session_sla_reminders(db: AsyncSession, now: datetime) -> list[dict]:
    """نیمهٔ مهلت SLA برای بررسی درمانگر و پرداخت جلسه اضافی (پیامک)."""
    out: list[dict] = []
    pairs = [
        ("therapist_review", "extra_session_sla_reminder_therapist_sent", "extra_session_sla_therapist", 48.0, "therapist"),
        ("payment_required", "extra_session_sla_reminder_payment_sent", "extra_session_sla_payment", 48.0, "student"),
    ]
    for state_code, ctx_flag, template_name, default_sla_h, recipient_kind in pairs:
        stmt = select(ProcessInstance).where(
            ProcessInstance.process_code == "extra_session",
            ProcessInstance.current_state_code == state_code,
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        rows = list((await db.execute(stmt)).scalars().all())
        for instance in rows:
            ctx = _context_as_dict(instance)
            if ctx.get(ctx_flag):
                continue
            sla = await _get_state_sla_hours(db, "extra_session", state_code)
            try:
                hours_total = float(sla) if sla is not None else default_sla_h
            except (TypeError, ValueError):
                hours_total = default_sla_h
            half = timedelta(hours=hours_total * 0.5)
            lt = instance.last_transition_at
            if lt is None:
                continue
            if lt.tzinfo is None:
                lt = lt.replace(tzinfo=timezone.utc)
            if now < lt + half:
                continue
            student = await db.get(Student, instance.student_id)
            if not student:
                continue
            phone = None
            if recipient_kind == "student":
                user = await db.get(User, student.user_id) if student.user_id else None
                if user:
                    phone = normalize_ir_mobile(user.phone or "")
            else:
                if student.therapist_id:
                    th_user = await db.get(User, student.therapist_id)
                    if th_user:
                        phone = normalize_ir_mobile(th_user.phone or "")
            if not phone or len(phone) < 10:
                continue
            msg = notification_service.get_template(template_name, "sms")
            if not msg:
                continue
            try:
                await send_sms(phone, msg)
            except Exception as e:
                logger.warning("extra_session SLA SMS failed instance=%s: %s", instance.id, e)
                continue
            ctx[ctx_flag] = now.isoformat()
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            out.append({"instance_id": str(instance.id), "template": template_name})
    return out


async def _run_therapy_session_increase_sla_reminders(db: AsyncSession, now: datetime) -> list[dict]:
    """نیمهٔ مهلت SLA برای بررسی درمانگر (therapy_session_increase / therapist_review)."""
    out: list[dict] = []
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "therapy_session_increase",
        ProcessInstance.current_state_code == "therapist_review",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for instance in rows:
        ctx = _context_as_dict(instance)
        if ctx.get("therapy_session_increase_sla_therapist_sent"):
            continue
        sla = await _get_state_sla_hours(db, "therapy_session_increase", "therapist_review")
        try:
            hours_total = float(sla) if sla is not None else 48.0
        except (TypeError, ValueError):
            hours_total = 48.0
        half = timedelta(hours=hours_total * 0.5)
        lt = instance.last_transition_at
        if lt is None:
            continue
        if lt.tzinfo is None:
            lt = lt.replace(tzinfo=timezone.utc)
        if now < lt + half:
            continue
        student = await db.get(Student, instance.student_id)
        if not student or not student.therapist_id:
            continue
        th_user = await db.get(User, student.therapist_id)
        if not th_user:
            continue
        phone = normalize_ir_mobile(th_user.phone or "")
        if not phone or len(phone) < 10:
            continue
        msg = notification_service.get_template("therapy_session_increase_sla_therapist", "sms")
        if not msg:
            continue
        try:
            await send_sms(phone, msg)
        except Exception as e:
            logger.warning("therapy_session_increase SLA therapist SMS failed instance=%s: %s", instance.id, e)
            continue
        ctx["therapy_session_increase_sla_therapist_sent"] = now.isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        out.append({"instance_id": str(instance.id), "template": "therapy_session_increase_sla_therapist"})
    return out


async def _run_therapy_session_increase_student_response_reminders(db: AsyncSession, now: datetime) -> list[dict]:
    """نیمهٔ مهلت SLA برای پاسخ دانشجو پس از پیشنهاد جایگزین (student_response)."""
    out: list[dict] = []
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "therapy_session_increase",
        ProcessInstance.current_state_code == "student_response",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for instance in rows:
        ctx = _context_as_dict(instance)
        if ctx.get("therapy_session_increase_reminder_student_sent"):
            continue
        sla = await _get_state_sla_hours(db, "therapy_session_increase", "student_response")
        try:
            hours_total = float(sla) if sla is not None else 72.0
        except (TypeError, ValueError):
            hours_total = 72.0
        half = timedelta(hours=hours_total * 0.5)
        lt = instance.last_transition_at
        if lt is None:
            continue
        if lt.tzinfo is None:
            lt = lt.replace(tzinfo=timezone.utc)
        if now < lt + half:
            continue
        student = await db.get(Student, instance.student_id)
        if not student or not student.user_id:
            continue
        user = await db.get(User, student.user_id)
        if not user:
            continue
        phone = normalize_ir_mobile(user.phone or "")
        if not phone or len(phone) < 10:
            continue
        msg = notification_service.get_template("therapy_session_increase_reminder_student_response", "sms")
        if not msg:
            continue
        try:
            await send_sms(phone, msg)
        except Exception as e:
            logger.warning(
                "therapy_session_increase student_response reminder SMS failed instance=%s: %s",
                instance.id,
                e,
            )
            continue
        ctx["therapy_session_increase_reminder_student_sent"] = now.isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        out.append({"instance_id": str(instance.id), "template": "therapy_session_increase_reminder_student_response"})
    return out


async def _run_start_therapy_sla_reminders(db: AsyncSession, now: datetime) -> list[dict]:
    """یادآوری پیامکی نیمهٔ مهلت SLA برای مراحل تایید درمانگر و پرداخت جلسه اول."""
    out: list[dict] = []
    pairs = [
        ("therapist_confirmation", "start_therapy_sla_reminder_therapist", "start_therapy_sla_therapist_pending", 72.0),
        ("payment_pending", "start_therapy_sla_reminder_payment", "start_therapy_sla_payment_pending", 48.0),
    ]
    for state_code, ctx_flag, template_name, default_sla_h in pairs:
        stmt = select(ProcessInstance).where(
            ProcessInstance.process_code == "start_therapy",
            ProcessInstance.current_state_code == state_code,
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        rows = list((await db.execute(stmt)).scalars().all())
        for instance in rows:
            ctx = _context_as_dict(instance)
            if ctx.get(ctx_flag):
                continue
            sla = await _get_state_sla_hours(db, "start_therapy", state_code)
            try:
                hours_total = float(sla) if sla is not None else default_sla_h
            except (TypeError, ValueError):
                hours_total = default_sla_h
            half = timedelta(hours=hours_total * 0.5)
            lt = instance.last_transition_at
            if lt is None:
                continue
            if lt.tzinfo is None:
                lt = lt.replace(tzinfo=timezone.utc)
            if now < lt + half:
                continue
            student = await db.get(Student, instance.student_id)
            if not student:
                continue
            user = await db.get(User, student.user_id) if student.user_id else None
            if not user:
                continue
            phone = normalize_ir_mobile(user.phone or "")
            if not phone or len(phone) < 10:
                continue
            msg = notification_service.get_template(template_name, "sms")
            if not msg:
                continue
            try:
                await send_sms(phone, msg)
            except Exception as e:
                logger.warning("start_therapy SLA SMS failed instance=%s: %s", instance.id, e)
                continue
            ctx[ctx_flag] = now.isoformat()
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            out.append({"instance_id": str(instance.id), "template": template_name})
    return out


async def _run_interview_slot_reminders(db: AsyncSession, now: datetime) -> list[dict]:
    """یادآوری پیامکی قبل از زمان مصاحبه برای اسلات‌های رزروشده."""
    settings = get_settings()
    hours = float(getattr(settings, "INTERVIEW_REMINDER_HOURS_BEFORE", 2.0))
    delta = timedelta(hours=hours)
    stmt = select(InterviewSlot).where(
        InterviewSlot.assigned_student_id.isnot(None),
        InterviewSlot.reminder_sent_at.is_(None),
    )
    rows = (await db.execute(stmt)).scalars().all()
    out: list[dict] = []
    for slot in rows:
        st = slot.starts_at
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        if st <= now:
            continue
        send_at = st - delta
        if now < send_at:
            continue
        student = await db.get(Student, slot.assigned_student_id)
        if not student:
            continue
        user = await db.get(User, student.user_id)
        if not user:
            continue
        phone = normalize_ir_mobile(user.phone or "")
        if not phone or len(phone) < 10:
            continue
        try:
            from zoneinfo import ZoneInfo

            local = st.astimezone(ZoneInfo("Asia/Tehran"))
            time_fa = local.strftime("%Y-%m-%d %H:%M")
            tz_note = "به وقت تهران"
        except Exception:
            time_fa = st.strftime("%Y-%m-%d %H:%M")
            tz_note = "UTC"
        msg = (
            "یادآوری مصاحبه پذیرش انستیتو روانکاوی تهران\n"
            f"زمان: {time_fa} ({tz_note})\n"
            "لطفاً به موقع در محل یا لینک اعلام‌شده حاضر شوید."
        )
        try:
            await send_sms(phone, msg)
        except Exception as e:
            logger.warning("interview reminder SMS failed slot=%s: %s", slot.id, e)
            continue
        slot.reminder_sent_at = now
        out.append({"slot_id": str(slot.id), "student_id": str(student.id)})
    return out


async def _run_session_payment_autostart_unpaid(db: AsyncSession) -> list[dict]:
    """باز کردن خودکار session_payment در صورت جلسات درمان بدون پرداخت و نبود نمونهٔ فعال."""
    svc = StudentService(db)
    return await svc.maybe_ensure_session_payment_for_unpaid_sessions()


async def run_calendar_trigger_pass(db: AsyncSession) -> dict[str, Any]:
    """یک دور کامل بررسی تریگرهای تقویمی."""
    now = datetime.now(timezone.utc)
    today = now.date()
    payment = await _run_payment_timeouts(db, now)
    session_pay_rem = await _run_session_payment_sla_reminders(db, now)
    session_pay_auto = await _run_session_payment_autostart_unpaid(db)
    leave_r = await _run_leave_reminders(db, now)
    leave_d = await _run_leave_return_deadline(db, now)
    await sync_all_open_attendance_instances_from_sessions(db)
    att = await _run_attendance_session_time(db, today)
    sup50 = await _run_supervision_50h_session_time(db, today)
    inst2 = await _run_intro_second_semester_installment_due(db, today)
    th_att = await _run_attendance_therapist_not_recorded_deadline(db, now)
    interview_rem = await _run_interview_slot_reminders(db, now)
    start_therapy_sla = await _run_start_therapy_sla_reminders(db, now)
    extra_session_sla = await _run_extra_session_sla_reminders(db, now)
    tsi_sla = await _run_therapy_session_increase_sla_reminders(db, now)
    tsi_student = await _run_therapy_session_increase_student_response_reminders(db, now)
    fee_det_sweep = await sweep_stuck_fee_determination_triggered(db)
    parts = [
        payment,
        session_pay_rem,
        session_pay_auto,
        leave_r,
        leave_d,
        att,
        sup50,
        inst2,
        th_att,
        interview_rem,
        start_therapy_sla,
        extra_session_sla,
        tsi_sla,
        tsi_student,
        fee_det_sweep,
    ]
    return {
        "at": now.isoformat(),
        "payment_timeout": payment,
        "session_payment_sla_reminders": session_pay_rem,
        "session_payment_autostart_unpaid": session_pay_auto,
        "send_return_reminder": leave_r,
        "return_deadline_passed": leave_d,
        "session_time_reached_attendance": att,
        "session_time_reached_supervision_50h": sup50,
        "installment_due_intro_second_semester": inst2,
        "therapist_did_not_record_attendance": th_att,
        "interview_slot_reminders": interview_rem,
        "start_therapy_sla_reminders": start_therapy_sla,
        "extra_session_sla_reminders": extra_session_sla,
        "therapy_session_increase_sla_reminders": tsi_sla,
        "therapy_session_increase_student_response_reminders": tsi_student,
        "fee_determination_stuck_sweep": fee_det_sweep,
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
