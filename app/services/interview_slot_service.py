"""رزرو اسلات مصاحبه و اتصال به ترنزیشن فرایند ثبت‌نام."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_settings
from app.core.engine import InvalidTransitionError, StateMachineEngine
from app.models.operational_models import InterviewSlot, ProcessInstance, Student, User
from app.services.alocom_client import AlocomAPIError
from app.services.alocom_interview_provision import (
    build_interview_alocom_title,
    ensure_interview_slot_host_meeting_link,
    provision_interview_slot_alocom,
    refresh_interview_slot_alocom_links,
)
from app.services.alocom_provision import _link_has_join_token, is_alocom_configured
from app.services.notification_service import notification_service
from app.services.interview_slot_notification_service import notify_interviewer_slot_booked
from app.services.sms_gateway import normalize_ir_mobile
from app.utils.shamsi_calendar_utils import tehran_datetime_parts

logger = logging.getLogger(__name__)

# فرایندهای ثبت‌نامی که مصاحبهٔ پذیرش دارند
INTERVIEW_REGISTRATION_PROCESS_CODES = frozenset(
    {"introductory_course_registration", "comprehensive_course_registration"}
)

# تا وقتی نمونهٔ فرایند در یکی از این وضعیت‌هاست، مصاحبه هنوز تمام نشده و لینک ورود معتبر است.
# با ثبت نتیجه، وضعیت به result_* / rejected / ... می‌رود و لینک باید غیرفعال شود.
INTERVIEW_LINK_ACTIVE_STATES = frozenset(
    {
        "application_submitted",
        "interview_scheduled",
        "interview_payment",
        "interview_payment_confirmed",
        "interview_completed",
    }
)

# awaiting_payment | alocom_not_configured | provisioning_failed | provisioning_pending | None (ok)
MeetingLinkProvisionStatus = Optional[str]


def interview_result_recorded_for_instance(instance: Optional[ProcessInstance]) -> bool:
    """نتیجهٔ مصاحبه ثبت شده است؟ (وضعیت فرایند از مرحلهٔ مصاحبه گذشته)"""
    if instance is None:
        return False
    if (instance.process_code or "") not in INTERVIEW_REGISTRATION_PROCESS_CODES:
        return False
    state = (instance.current_state_code or "").strip()
    if not state:
        return False
    return state not in INTERVIEW_LINK_ACTIVE_STATES


async def interview_slot_result_recorded(
    db: AsyncSession,
    slot: InterviewSlot,
    *,
    instance: Optional[ProcessInstance] = None,
) -> bool:
    """برای اسلات رزروشده: آیا نتیجهٔ مصاحبه ثبت شده و لینک ورود باید بسته شود؟"""
    if instance is None:
        instance_id = getattr(slot, "assigned_instance_id", None)
        if not instance_id:
            return False
        instance = await db.get(ProcessInstance, instance_id)
    return interview_result_recorded_for_instance(instance)


def interview_meeting_link_provision_status(slot: InterviewSlot) -> MeetingLinkProvisionStatus:
    """دلیل نبود لینک آنلاین برای رزرو پرداخت‌شده — برای نمایش خطا در پنل اپراتور."""
    if slot.mode != "online" or not slot.assigned_student_id:
        return None
    if getattr(slot, "booking_payment_deadline_at", None) is not None:
        return "awaiting_payment"
    student_link = (slot.meeting_link or "").strip()
    if student_link and _link_has_join_token(student_link):
        return None
    if student_link or (getattr(slot, "alocom_event_id", None) or "").strip():
        return "provisioning_failed"
    alocom_ready, _agent_id = is_alocom_configured()
    if not alocom_ready:
        return "alocom_not_configured"
    return "provisioning_pending"


_COURSE_LABEL_FA = {
    "introductory": "دوره آشنایی",
    "comprehensive": "دوره جامع",
}


def interview_mode_fa_to_slot_mode(mode_fa: str | None) -> str:
    """interview_mode فارسی فرم آماده‌سازی ترم → mode اسلات."""
    if (mode_fa or "").strip() == "آنلاین":
        return "online"
    return "in_person"


def resolve_semester_prep_interview_location(ctx: dict[str, Any]) -> str | None:
    loc = (ctx.get("interview_location_fa") or ctx.get("interview_location_or_link") or "").strip()
    return loc or None


async def apply_semester_prep_interview_defaults_to_open_slots(
    db: AsyncSession,
    *,
    mode: str,
    location_fa: str | None = None,
) -> int:
    """اسلات‌های آزاد را با تنظیمات مرحلهٔ مصاحبهٔ آماده‌سازی ترم همگام می‌کند."""
    stmt = select(InterviewSlot).where(InterviewSlot.assigned_student_id.is_(None))
    rows = (await db.execute(stmt)).scalars().all()
    updated = 0
    for slot in rows:
        slot.mode = mode
        if mode == "in_person":
            if location_fa:
                slot.location_fa = location_fa
        else:
            slot.location_fa = None
        updated += 1
    if updated:
        await db.flush()
    return updated


def interviewer_capacity_slot_filter(user_id: uuid.UUID):
    """
    اسلات‌هایی که برای ظرفیت رزرو این مصاحبه‌گر شمرده می‌شوند:
    اختصاصی به خودش، یا استخر اداری بدون مصاحبه‌گر مشخص (همان منطق دید دانشجو).
    """
    return or_(
        InterviewSlot.interviewer_user_id == user_id,
        InterviewSlot.interviewer_user_id.is_(None),
    )


def _instance_context_dict(val: Any) -> dict[str, Any]:
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    return {}


async def enrich_interview_notification_context(
    db: AsyncSession,
    instance: ProcessInstance,
) -> dict[str, Any]:
    """فیلدهای interview_* از اسلات تخصیص‌یافته برای SMS و اعلان‌ها (ثبت‌نام آشنایی/جامع)."""
    if instance.process_code not in (
        "introductory_course_registration",
        "comprehensive_course_registration",
    ):
        return {}
    stmt = select(InterviewSlot).where(InterviewSlot.assigned_instance_id == instance.id)
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return {}
    ctx = _instance_context_dict(instance.context_data)
    sel = (ctx.get("selected_timeslot") or "").strip()
    slot = rows[0]
    if sel:
        for s in rows:
            if str(s.id) == sel:
                slot = s
                break
    interview_date, interview_time = tehran_datetime_parts(slot.starts_at)
    interview_type = "online" if slot.mode == "online" else "in_person"
    loc = (slot.location_fa or "").strip() or ("انستیتو روانکاوی تهران" if interview_type == "in_person" else "")
    link = (slot.meeting_link or "").strip() if interview_type == "online" else ""
    detail_tail = (
        f"لینک: {link}" if (interview_type == "online" and link) else (f"محل: {loc}" if loc else "")
    )
    out: dict[str, Any] = {
        "interview_date": interview_date,
        "interview_time": interview_time,
        "date": interview_date,
        "time": interview_time,
        "interview_type": interview_type,
        "interview_link": link,
        "interview_location": loc,
        "interview_location_or_link": link or loc or "—",
        "interview_detail_tail": detail_tail,
        "selected_timeslot": str(slot.id),
    }
    if getattr(slot, "interviewer_user_id", None):
        out["interviewer_user_id"] = str(slot.interviewer_user_id)
    if getattr(slot, "created_by", None):
        out["slot_created_by"] = str(slot.created_by)
    stu = await db.get(Student, instance.student_id)
    if stu:
        su = await db.get(User, stu.user_id)
        if su and (su.full_name_fa or "").strip():
            out.setdefault("student_name", (su.full_name_fa or "").strip())
    return out


async def sync_registration_interview_context_from_slot(
    db: AsyncSession,
    *,
    instance: ProcessInstance,
    slot: InterviewSlot,
) -> None:
    """جزئیات مصاحبه (از جمله لینک الوکام) را در context_data نمونهٔ فرایند ذخیره می‌کند."""
    ctx = _instance_context_dict(instance.context_data)
    ctx.update(_slot_payload(slot))
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()


async def maybe_provision_interview_slot_alocom_link(
    db: AsyncSession,
    slot: InterviewSlot,
    *,
    instance: Optional[ProcessInstance] = None,
    payment_confirmed: bool = False,
) -> bool:
    """برای اسلات آنلاین پرداخت‌شده بدون لینک، رویداد الوکام بسازد. True اگر لینک موجود باشد."""

    def _links_ready() -> bool:
        if not _link_has_join_token(slot.meeting_link):
            return False
        if slot.interviewer_user_id and not _link_has_join_token(
            getattr(slot, "interviewer_meeting_link", None)
        ):
            return False
        return True

    if slot.mode != "online":
        return bool((slot.meeting_link or "").strip())
    if _links_ready():
        return True
    if (getattr(slot, "alocom_event_id", None) or "").strip():
        refreshed = await refresh_interview_slot_alocom_links(db, slot)
        if refreshed and _links_ready():
            sync_instance = instance
            if sync_instance is None and slot.assigned_instance_id:
                sync_instance = await db.get(ProcessInstance, slot.assigned_instance_id)
            if sync_instance:
                await sync_registration_interview_context_from_slot(db, instance=sync_instance, slot=slot)
            return True
        logger.warning(
            "Stale Alocom event_id on slot=%s — clearing for reprovision (refreshed=%s)",
            slot.id,
            refreshed,
        )
        slot.alocom_event_id = None
        if not _link_has_join_token(slot.meeting_link):
            slot.meeting_link = None
        await db.flush()
    if not payment_confirmed and getattr(slot, "booking_payment_deadline_at", None) is not None:
        return False
    alocom_ready, agent_service_id = is_alocom_configured()
    if not alocom_ready or not slot.assigned_student_id:
        if payment_confirmed or getattr(slot, "booking_payment_deadline_at", None) is None:
            if slot.assigned_student_id and not alocom_ready:
                logger.error(
                    "Interview Alocom link not provisioned: ALOCOM_ENABLED/credentials not configured slot=%s",
                    slot.id,
                )
        return False
    st = await db.get(Student, slot.assigned_student_id)
    title = (
        build_interview_alocom_title(st.student_code, slot.id)
        if st
        else build_interview_alocom_title("", slot.id)
    )
    try:
        await provision_interview_slot_alocom(
            db,
            slot=slot,
            agent_service_id=agent_service_id,
            title=title,
            fetch_student_event_link=True,
        )
    except AlocomAPIError as e:
        logger.warning(
            "maybe_provision_interview_slot_alocom_link failed slot=%s: %s body=%s",
            slot.id,
            e,
            getattr(e, "body", None),
        )
        return False
    except Exception:
        logger.exception(
            "maybe_provision_interview_slot_alocom_link unexpected error slot=%s",
            slot.id,
        )
        return False
    sync_instance = instance
    if sync_instance is None and slot.assigned_instance_id:
        sync_instance = await db.get(ProcessInstance, slot.assigned_instance_id)
    if sync_instance:
        await sync_registration_interview_context_from_slot(db, instance=sync_instance, slot=slot)
    try:
        await ensure_interview_slot_host_meeting_link(db, slot)
    except Exception:
        logger.exception(
            "ensure_interview_slot_host_meeting_link failed slot=%s (student link kept if set)",
            slot.id,
        )
    return _links_ready()


async def ensure_registration_interview_slot_has_alocom_link(
    db: AsyncSession,
    *,
    instance_id: uuid.UUID,
) -> None:
    """پس از پرداخت موفق: برای مصاحبهٔ آنلاین لینک الوکام ساخته و context فرایند به‌روز می‌شود."""
    instance = await db.get(ProcessInstance, instance_id)
    if not instance:
        return

    stmt = select(InterviewSlot).where(InterviewSlot.assigned_instance_id == instance_id)
    slots = (await db.execute(stmt)).scalars().all()
    for slot in slots:
        await maybe_provision_interview_slot_alocom_link(
            db, slot, instance=instance, payment_confirmed=True
        )
        await sync_registration_interview_context_from_slot(db, instance=instance, slot=slot)


async def delete_prior_unbooked_slots_for_interviewer(
    db: AsyncSession,
    *,
    interviewer_user_id: uuid.UUID,
) -> int:
    """قبل از ثبت وقت آزاد جدید: تمام اسلات‌های آزاد قبلی متعلق به همان مصاحبه‌گر حذف می‌شوند."""
    stmt = select(InterviewSlot).where(
        InterviewSlot.assigned_student_id.is_(None),
        InterviewSlot.generated_from_rule_id.is_(None),
        or_(
            InterviewSlot.interviewer_user_id == interviewer_user_id,
            and_(
                InterviewSlot.interviewer_user_id.is_(None),
                InterviewSlot.created_by == interviewer_user_id,
            ),
        ),
    )
    rows = (await db.execute(stmt)).scalars().all()
    n = 0
    for s in rows:
        await db.delete(s)
        n += 1
    if n:
        await db.flush()
    return n


def _slot_payload(slot: InterviewSlot) -> dict[str, Any]:
    interview_date, interview_time = tehran_datetime_parts(slot.starts_at)
    interview_type = "online" if slot.mode == "online" else "in_person"
    loc = (slot.location_fa or "").strip() or ("انستیتو روانکاوی تهران" if interview_type == "in_person" else "")
    link = (slot.meeting_link or "").strip() if interview_type == "online" else ""
    out: dict[str, Any] = {
        "selected_timeslot": str(slot.id),
        "interview_date": interview_date,
        "interview_time": interview_time,
        "date": interview_date,
        "time": interview_time,
        "interview_type": interview_type,
        "interview_link": link,
        "interview_location": loc,
        "interview_location_or_link": link or loc or "—",
        "notes": "رزرو از طریق اسلات سامانه",
    }
    if getattr(slot, "interviewer_user_id", None):
        out["interviewer_user_id"] = str(slot.interviewer_user_id)
    if getattr(slot, "created_by", None):
        out["slot_created_by"] = str(slot.created_by)
    return out


def _resolve_trigger(process_code: str, current_state: str) -> Optional[str]:
    if process_code == "introductory_course_registration" and current_state == "application_submitted":
        return "timeslot_selected"
    if process_code == "comprehensive_course_registration" and current_state == "interview_scheduled":
        return "interview_time_selected"
    return None


def _booking_payment_deadline_at() -> datetime:
    minutes = max(1, int(get_settings().INTERVIEW_BOOKING_PAYMENT_DEADLINE_MINUTES))
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


async def _resolve_system_actor_for_deadline_job(db: AsyncSession) -> uuid.UUID:
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row is not None:
        return row
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row if row is not None else uuid.uuid4()


def _interview_registration_unpaid_states(process_code: str, state: str) -> bool:
    if process_code == "introductory_course_registration":
        return state in ("interview_scheduled", "interview_payment")
    if process_code == "comprehensive_course_registration":
        return state in ("interview_scheduled", "interview_payment")
    return False


def _booking_deadline_release_target_reached(process_code: str, state: str) -> bool:
    if process_code == "introductory_course_registration":
        return state == "application_submitted"
    if process_code == "comprehensive_course_registration":
        return state == "interview_scheduled"
    return True


async def expire_interview_booking_payment_deadlines(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """اسلات‌هایی که مهلت پرداخت تمام شده و هنوز تأیید نشده‌اند را آزاد می‌کند؛ فرایند ثبت‌نام تا قبل از رزرو برمی‌گردد."""
    now = now or datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []

    while True:
        stmt = (
            select(InterviewSlot)
            .where(
                InterviewSlot.assigned_student_id.isnot(None),
                InterviewSlot.booking_payment_deadline_at.isnot(None),
                InterviewSlot.booking_payment_deadline_at < now,
            )
            .limit(1)
            .with_for_update()
        )
        slot = (await db.execute(stmt)).scalars().first()
        if slot is None:
            break

        payload: dict[str, Any] = {"slot_id": str(slot.id)}
        inst: ProcessInstance | None = None
        if slot.assigned_instance_id:
            inst = await db.get(ProcessInstance, slot.assigned_instance_id)

        if (
            not inst
            or inst.is_completed
            or inst.is_cancelled
            or inst.process_code
            not in ("introductory_course_registration", "comprehensive_course_registration")
        ):
            slot.assigned_student_id = None
            slot.assigned_instance_id = None
            slot.booking_payment_deadline_at = None
            payload["cleared"] = True
            payload["reason"] = "no_instance_or_invalid_process"
            out.append(payload)
            await db.flush()
            continue

        if not _interview_registration_unpaid_states(inst.process_code, inst.current_state_code):
            slot.booking_payment_deadline_at = None
            payload["deadline_cleared_only"] = True
            out.append(payload)
            await db.flush()
            continue

        actor_id = await _resolve_system_actor_for_deadline_job(db)
        engine = StateMachineEngine(db)
        rolled_ok = False
        for _ in range(24):
            if _booking_deadline_release_target_reached(inst.process_code, inst.current_state_code):
                rolled_ok = True
                break
            try:
                await engine.rollback_to_previous_state(
                    instance_id=inst.id,
                    actor_id=actor_id,
                    actor_role="system",
                    reason="انقضای مهلت پرداخت هزینهٔ مصاحبه — آزادسازی اسلات",
                )
            except InvalidTransitionError:
                payload["rollback_error"] = True
                break
            await db.refresh(inst)

        if not rolled_ok and not payload.get("rollback_error"):
            payload["rollback_incomplete"] = inst.current_state_code

        slot.assigned_student_id = None
        slot.assigned_instance_id = None
        slot.booking_payment_deadline_at = None
        payload["released_slot"] = True
        out.append(payload)
        await db.flush()

    return out


async def clear_booking_deadline_for_instance(db: AsyncSession, instance_id: uuid.UUID) -> None:
    stmt = select(InterviewSlot).where(InterviewSlot.assigned_instance_id == instance_id)
    slots = (await db.execute(stmt)).scalars().all()
    for slot in slots:
        slot.booking_payment_deadline_at = None
    await db.flush()


async def advance_due_interview_interviews(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """پس از گذشت زمان مصاحبه، نمونهٔ ثبت‌نام آشنایی را از interview_payment_confirmed به interview_completed می‌برد."""
    now = now or datetime.now(timezone.utc)
    out: list[dict[str, Any]] = []
    actor_id = await _resolve_system_actor_for_deadline_job(db)
    engine = StateMachineEngine(db)

    stmt = select(InterviewSlot).where(
        InterviewSlot.assigned_instance_id.isnot(None),
        InterviewSlot.starts_at < now,
    )
    slots = (await db.execute(stmt)).scalars().all()
    seen: set[uuid.UUID] = set()

    for slot in slots:
        iid = slot.assigned_instance_id
        if not iid or iid in seen:
            continue
        seen.add(iid)

        inst = await db.get(ProcessInstance, iid)
        if not inst or inst.is_completed or inst.is_cancelled:
            continue
        if inst.process_code != "introductory_course_registration":
            continue
        if inst.current_state_code != "interview_payment_confirmed":
            continue

        try:
            result = await engine.execute_transition(
                instance_id=inst.id,
                trigger_event="interview_time_reached",
                actor_id=actor_id,
                actor_role="system",
                payload={},
            )
            out.append(
                {
                    "instance_id": str(inst.id),
                    "slot_id": str(slot.id),
                    "success": result.success,
                    "to_state": result.to_state,
                    "error": result.error,
                }
            )
        except Exception as e:
            logger.exception("advance_due_interview_interviews failed instance=%s", inst.id)
            out.append(
                {
                    "instance_id": str(inst.id),
                    "slot_id": str(slot.id),
                    "success": False,
                    "error": str(e),
                }
            )
    return out


def _normalize_utc_dt(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _sms_context_for_rescheduled_slot(
    db: AsyncSession,
    slot: InterviewSlot,
) -> dict[str, Any]:
    ctx = dict(_slot_payload(slot))
    ct = (slot.course_type or "").lower()
    ctx.setdefault("course_label", _COURSE_LABEL_FA.get(ct, "دوره"))
    if slot.assigned_student_id:
        stu = await db.get(Student, slot.assigned_student_id)
        if stu:
            su = await db.get(User, stu.user_id)
            if su and (su.full_name_fa or "").strip():
                ctx.setdefault("student_name", (su.full_name_fa or "").strip())
    return ctx


async def reschedule_booked_interview_slot(
    db: AsyncSession,
    *,
    slot: InterviewSlot,
    new_starts_at: datetime,
    new_ends_at: datetime,
) -> dict[str, Any]:
    """تغییر زمان اسلات رزروشدهٔ پرداخت‌شده؛ قفل مجدد ورود دانشجو + پیامک برای آنلاین."""
    if slot.assigned_student_id is None:
        return {"success": False, "error": "این اسلات رزرو نشده است."}
    if getattr(slot, "booking_payment_deadline_at", None) is not None:
        return {"success": False, "error": "تا قبل از قطعی شدن پرداخت امکان تغییر زمان نیست."}

    new_starts = _normalize_utc_dt(new_starts_at)
    new_ends = _normalize_utc_dt(new_ends_at)
    now = datetime.now(timezone.utc)

    if new_ends <= new_starts:
        return {"success": False, "error": "زمان پایان باید بعد از شروع باشد."}
    if new_ends <= now:
        return {"success": False, "error": "بازه باید در آینده باشد."}

    slot.starts_at = new_starts
    slot.ends_at = new_ends
    slot.student_join_open = False
    slot.reminder_sent_at = None
    await db.flush()

    if slot.assigned_instance_id:
        instance = await db.get(ProcessInstance, slot.assigned_instance_id)
        if instance:
            await sync_registration_interview_context_from_slot(db, instance=instance, slot=slot)

    sms_sent = False
    if slot.mode == "online":
        stu = await db.get(Student, slot.assigned_student_id)
        if stu:
            su = await db.get(User, stu.user_id)
            if su:
                phone = normalize_ir_mobile(su.phone or "")
                if phone and len(phone) >= 10:
                    ctx = await _sms_context_for_rescheduled_slot(db, slot)
                    try:
                        res = await notification_service.send_notification(
                            "sms",
                            "interview_scheduled_student_online",
                            phone,
                            ctx,
                        )
                        sms_sent = bool(res.success)
                        if not res.success:
                            logger.warning(
                                "reschedule interview SMS failed slot=%s err=%s",
                                slot.id,
                                res.error,
                            )
                    except Exception:
                        logger.exception(
                            "reschedule interview SMS exception slot=%s",
                            slot.id,
                        )

    return {
        "success": True,
        "slot_id": str(slot.id),
        "starts_at": slot.starts_at.isoformat(),
        "ends_at": slot.ends_at.isoformat(),
        "sms_sent": sms_sent,
    }


async def book_slot_for_registration(
    db: AsyncSession,
    *,
    user: User,
    instance_id: uuid.UUID,
    slot_id: uuid.UUID,
) -> dict[str, Any]:
    """یک اسلات را به نمونهٔ فرایند ثبت‌نام دانشجو وصل می‌کند و ترنزیشن را اجرا می‌کند."""
    now = datetime.now(timezone.utc)
    await expire_interview_booking_payment_deadlines(db, now=now)

    stmt_st = select(Student).where(Student.user_id == user.id)
    student = (await db.execute(stmt_st)).scalars().first()
    if not student:
        return {"success": False, "error": "پروفایل دانشجویی یافت نشد."}

    stmt_i = (
        select(ProcessInstance)
        .where(ProcessInstance.id == instance_id)
        .options(selectinload(ProcessInstance.student))
    )
    instance = (await db.execute(stmt_i)).scalars().first()
    if not instance:
        return {"success": False, "error": "فرایند یافت نشد."}
    if instance.student_id != student.id:
        return {"success": False, "error": "این فرایند متعلق به شما نیست."}
    if instance.is_completed or instance.is_cancelled:
        return {"success": False, "error": "این فرایند دیگر فعال نیست."}

    trigger = _resolve_trigger(instance.process_code, instance.current_state_code)
    if not trigger:
        return {
            "success": False,
            "error": "در این مرحله امکان رزرو اسلات از سامانه پیش‌بینی نشده است.",
        }

    stmt_slot = select(InterviewSlot).where(InterviewSlot.id == slot_id).with_for_update()
    slot = (await db.execute(stmt_slot)).scalars().first()
    if not slot:
        return {"success": False, "error": "اسلات یافت نشد."}

    if slot.ends_at <= now:
        return {"success": False, "error": "این زمان مصاحبه دیگر معتبر نیست."}
    if slot.assigned_student_id is not None:
        return {"success": False, "error": "این زمان قبلاً رزرو شده است."}

    ct = slot.course_type
    if ct:
        st_ct = (student.course_type or "").lower()
        if st_ct and ct != st_ct:
            return {"success": False, "error": "این اسلات برای نوع دورهٔ دیگری تعریف شده است."}

    payload = _slot_payload(slot)
    slot.assigned_student_id = student.id
    slot.assigned_instance_id = instance.id
    slot.student_join_open = False
    await db.flush()

    engine = StateMachineEngine(db)
    try:
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event=trigger,
            actor_id=user.id,
            actor_role=user.role or "student",
            payload=payload,
        )
    except InvalidTransitionError as e:
        slot.assigned_student_id = None
        slot.assigned_instance_id = None
        slot.booking_payment_deadline_at = None
        await db.flush()
        return {"success": False, "error": str(e)}

    if not result.success:
        slot.assigned_student_id = None
        slot.assigned_instance_id = None
        slot.booking_payment_deadline_at = None
        await db.flush()
        return {"success": False, "error": result.error or "انتقال فرایند انجام نشد."}

    await db.refresh(instance)
    if (
        instance.process_code == "introductory_course_registration"
        and instance.current_state_code == "interview_scheduled"
    ):
        try:
            pay_result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="proceed_to_payment",
                actor_id=user.id,
                actor_role=user.role or "student",
                payload=payload,
            )
            if not pay_result.success:
                logger.warning(
                    "book_slot auto proceed_to_payment failed instance=%s: %s",
                    instance.id,
                    pay_result.error,
                )
        except InvalidTransitionError as e:
            logger.warning(
                "book_slot auto proceed_to_payment invalid instance=%s: %s",
                instance.id,
                e,
            )
        await db.refresh(instance)

    slot.booking_payment_deadline_at = _booking_payment_deadline_at()
    await db.flush()

    await db.refresh(instance)
    await db.refresh(slot)

    if slot.interviewer_user_id:
        st_user = user
        if student.user_id != user.id:
            st_user = await db.get(User, student.user_id) or user
        await notify_interviewer_slot_booked(
            db,
            slot=slot,
            student=student,
            student_user=st_user,
        )

    deadline_iso: str | None = None
    if slot.booking_payment_deadline_at:
        deadline_iso = slot.booking_payment_deadline_at.isoformat()
    return {
        "success": True,
        "instance_id": str(instance.id),
        "current_state": instance.current_state_code,
        "slot_id": str(slot.id),
        "booking_payment_deadline_at": deadline_iso,
    }
