"""اعلان تخصیص اسلات مصاحبه و رزرو دانشجو برای مصاحبه‌گر."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InterviewSlot, Student, User
from app.services.notification_service import notification_service
from app.utils.shamsi_calendar_utils import tehran_datetime_parts
from app.services.panel_flash_messages import create_panel_flash_message
from app.services.sms_gateway import normalize_ir_mobile

logger = logging.getLogger(__name__)

INTERVIEWER_PORTAL_PATH = "/panel/portal/interviewer"

_COURSE_LABEL_FA = {
    "introductory": "دوره آشنایی",
    "comprehensive": "دوره جامع",
}


def _course_label_fa(course_type: str | None) -> str:
    if course_type in _COURSE_LABEL_FA:
        return _COURSE_LABEL_FA[course_type]
    return "پذیرش"


def _slot_datetime_parts(slot: InterviewSlot) -> tuple[str, str]:
    st = slot.starts_at
    if st is None:
        return "—", "—"
    return tehran_datetime_parts(st)


def _slot_notification_context(slot: InterviewSlot, *, student_name: str | None = None) -> dict[str, str]:
    interview_date, interview_time = _slot_datetime_parts(slot)
    course_label = _course_label_fa(slot.course_type)
    mode_fa = "آنلاین" if slot.mode == "online" else "حضوری"
    ctx: dict[str, str] = {
        "course_label": course_label,
        "course_type": course_label,
        "interview_date": interview_date,
        "interview_time": interview_time,
        "mode_fa": mode_fa,
    }
    if student_name:
        ctx["student_name"] = student_name
    return ctx


async def notify_interviewer_slot_assigned(
    db: AsyncSession,
    *,
    slot: InterviewSlot,
    interviewer_user_id: uuid.UUID,
) -> None:
    """پس از تخصیص اسلات آزاد به مصاحبه‌گر: پاپ‌آپ پنل + پیامک."""
    interviewer = await db.get(User, interviewer_user_id)
    if not interviewer or not interviewer.is_active:
        return

    interview_date, interview_time = _slot_datetime_parts(slot)
    course_label = _course_label_fa(slot.course_type)
    mode_fa = "آنلاین" if slot.mode == "online" else "حضوری"
    flash_msg = (
        f"وقت مصاحبه {course_label} ({mode_fa}) در تاریخ {interview_date} ساعت {interview_time} "
        "به شما اختصاص یافت. جزئیات در پنل مصاحبه‌گر قابل مشاهده است."
    )
    await create_panel_flash_message(
        db,
        user_id=interviewer_user_id,
        message=flash_msg,
        level="success",
        source_path=INTERVIEWER_PORTAL_PATH,
        category="system",
    )

    phone = normalize_ir_mobile(interviewer.phone or "")
    if not phone:
        return
    try:
        await notification_service.send_notification(
            "sms",
            "interview_slot_assigned_interviewer",
            phone,
            _slot_notification_context(slot),
        )
    except Exception:
        logger.exception("notify_interviewer_slot_assigned SMS failed slot=%s", slot.id)


async def notify_interviewer_slot_booked(
    db: AsyncSession,
    *,
    slot: InterviewSlot,
    student: Student,
    student_user: User,
) -> None:
    """پس از انتخاب وقت توسط دانشجو (قبل از پرداخت): پاپ‌آپ پنل + پیامک."""
    iv_id = getattr(slot, "interviewer_user_id", None)
    if not iv_id:
        return

    interviewer = await db.get(User, iv_id)
    if not interviewer or not interviewer.is_active:
        return

    student_name = (student_user.full_name_fa or "").strip() or (student.student_code or "").strip() or "دانشجو"
    interview_date, interview_time = _slot_datetime_parts(slot)
    course_label = _course_label_fa(slot.course_type)
    flash_msg = (
        f"دانشجو {student_name} وقت مصاحبه {course_label} در تاریخ {interview_date} "
        f"ساعت {interview_time} را انتخاب کرد. مهلت پرداخت ۱۰ دقیقه است."
    )
    await create_panel_flash_message(
        db,
        user_id=iv_id,
        message=flash_msg,
        level="success",
        source_path=INTERVIEWER_PORTAL_PATH,
        category="system",
    )

    phone = normalize_ir_mobile(interviewer.phone or "")
    if not phone:
        return
    try:
        await notification_service.send_notification(
            "sms",
            "interview_slot_booked_interviewer",
            phone,
            _slot_notification_context(slot, student_name=student_name),
        )
    except Exception:
        logger.exception("notify_interviewer_slot_booked SMS failed slot=%s", slot.id)
