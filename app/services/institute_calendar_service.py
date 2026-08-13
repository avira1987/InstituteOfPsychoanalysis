"""مدیریت تقویم آموزشی فعال انستیتو."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import InstituteCalendar, ProcessInstance, Student
from app.services.semester_prep_service import WINTER_PREP
from app.utils.shamsi_calendar_utils import (
    iso_value_has_explicit_time,
    parse_iso_date,
    tehran_day_end_utc,
    tehran_day_start_utc,
)

ACADEMIC_CALENDAR_SNAPSHOT_KEYS: tuple[str, ...] = (
    "nowruz_holiday_start",
    "nowruz_holiday_end",
    "fall_start_date",
    "fall_end_date",
    "winter_start_date",
    "winter_end_date",
    "registration_payment_window_start",
    "registration_payment_window_end",
    "fall_break_periods",
    "winter_break_periods",
    "intern_interview_deadline_start",
    "intern_interview_deadline_end",
    "teaching_assistant_interview_deadline_start",
    "teaching_assistant_interview_deadline_end",
)


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except (TypeError, ValueError):
        return None


def _registration_open_from_context(ctx: dict[str, Any]) -> Optional[datetime]:
    for key in ("registration_open_at", "registration_open_date"):
        raw = ctx.get(key)
        if raw in (None, ""):
            continue
        if iso_value_has_explicit_time(raw):
            return _parse_datetime(raw)
        day = parse_iso_date(raw)
        if day:
            return tehran_day_start_utc(day)
    raw = ctx.get("registration_payment_window_start")
    if raw in (None, ""):
        return None
    day = parse_iso_date(raw)
    return tehran_day_start_utc(day) if day else _parse_datetime(raw)


def _registration_deadline_from_context(ctx: dict[str, Any]) -> Optional[datetime]:
    for key in (
        "registration_deadline_at",
        "registration_deadline",
        "next_term_registration_deadline",
    ):
        raw = ctx.get(key)
        if raw in (None, ""):
            continue
        if iso_value_has_explicit_time(raw):
            return _parse_datetime(raw)
        day = parse_iso_date(raw)
        if day:
            return tehran_day_end_utc(day)
    raw = ctx.get("registration_payment_window_end")
    if raw in (None, ""):
        return None
    day = parse_iso_date(raw)
    return tehran_day_end_utc(day) if day else _parse_datetime(raw)


def _snapshot_value_present(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list):
        return len(value) > 0
    return True


def _registration_window_snapshot_present(extra: dict[str, Any]) -> bool:
    return _snapshot_value_present(extra.get("registration_payment_window_start")) or _snapshot_value_present(
        extra.get("registration_payment_window_end")
    )


def _align_registration_window_payload(payload: dict[str, Any]) -> None:
    """ستون‌های پنجرهٔ ثبت‌نام را با snapshot فرم تقویم در extra_data هم‌تراز می‌کند."""
    extra = payload.get("extra_data") if isinstance(payload.get("extra_data"), dict) else {}
    if not _registration_window_snapshot_present(extra):
        return
    reg_open = _registration_open_from_context(extra)
    reg_deadline = _registration_deadline_from_context(extra)
    if reg_open is not None:
        payload["registration_open_at"] = reg_open
    if reg_deadline is not None:
        payload["registration_deadline_at"] = reg_deadline


def resolve_registration_window(
    cal: InstituteCalendar | None,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """مهلت ثبت‌نام: snapshot پنجرهٔ پرداخت در extra_data یا ستون‌های تقویم."""
    if cal is None:
        return None, None
    extra = cal.extra_data if isinstance(cal.extra_data, dict) else {}
    extra_open = _registration_open_from_context(extra)
    extra_deadline = _registration_deadline_from_context(extra)
    col_open = cal.registration_open_at
    col_deadline = cal.registration_deadline_at

    if not _registration_window_snapshot_present(extra):
        return col_open, col_deadline

    if col_open is None and col_deadline is None:
        return extra_open, extra_deadline

    # اگر snapshot و ستون‌ها ناهماهنگ باشند، ستون‌ها ملاک‌اند (اصلاح scheduler / republish).
    if extra_open != col_open or extra_deadline != col_deadline:
        return col_open, col_deadline

    return extra_open, extra_deadline


async def get_active_calendar(db: AsyncSession) -> Optional[InstituteCalendar]:
    stmt = (
        select(InstituteCalendar)
        .where(InstituteCalendar.is_active.is_(True))
        .order_by(InstituteCalendar.published_at.desc().nullslast(), InstituteCalendar.updated_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def deactivate_all_calendars(db: AsyncSession) -> None:
    await db.execute(update(InstituteCalendar).values(is_active=False))


def calendar_payload_from_context(
    ctx: dict[str, Any],
    *,
    source_process_code: str | None = None,
) -> dict[str, Any]:
    """استخراج تاریخ‌ها از context فرم تقویم یا instance."""
    proc = (source_process_code or ctx.get("source_process_code") or "").strip()
    is_winter = proc == "winter_semester_preparation"

    if is_winter:
        term_start = _parse_date(
            ctx.get("term_start_date")
            or ctx.get("winter_start_date")
            or ctx.get("winter_term_start")
        )
        term_end = _parse_date(
            ctx.get("term_end_date")
            or ctx.get("winter_end_date")
            or ctx.get("term_end")
        )
    else:
        term_start = _parse_date(
            ctx.get("term_start_date")
            or ctx.get("fall_start_date")
            or ctx.get("fall_term_start")
            or ctx.get("winter_term_start")
        )
        term_end = _parse_date(
            ctx.get("term_end_date")
            or ctx.get("fall_end_date")
            or ctx.get("term_end")
        )

    reg_open = _registration_open_from_context(ctx)
    reg_deadline = _registration_deadline_from_context(ctx)
    eval_open = _parse_datetime(ctx.get("evaluation_open_at"))
    eval_close = _parse_datetime(ctx.get("evaluation_close_at"))
    if term_end and not eval_open:
        eval_open = datetime.combine(term_end, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=14)
    if term_end and not eval_close:
        eval_close = datetime.combine(term_end, datetime.min.time(), tzinfo=timezone.utc)
    term_code = (
        str(ctx.get("term_code") or "").strip()
        or (
            f"winter-{term_start.isoformat()}"
            if is_winter and term_start
            else f"fall-{term_start.isoformat()}"
            if term_start
            else f"term-{datetime.now(timezone.utc).date().isoformat()}"
        )
    )
    return {
        "term_code": term_code,
        "term_start_date": term_start,
        "term_end_date": term_end,
        "registration_open_at": reg_open,
        "registration_deadline_at": reg_deadline,
        "evaluation_open_at": eval_open,
        "evaluation_close_at": eval_close,
    }


async def upsert_active_calendar(
    db: AsyncSession,
    *,
    payload: dict[str, Any],
    published_by: Optional[uuid.UUID] = None,
    source_instance: Optional[ProcessInstance] = None,
) -> InstituteCalendar:
    previous_active = await get_active_calendar(db)
    await deactivate_all_calendars(db)
    term_code = payload["term_code"]
    stmt = select(InstituteCalendar).where(InstituteCalendar.term_code == term_code)
    row = (await db.execute(stmt)).scalars().first()
    now = datetime.now(timezone.utc)
    _align_registration_window_payload(payload)
    for field in ("registration_open_at", "registration_deadline_at"):
        if payload.get(field) is not None:
            continue
        if row is not None and getattr(row, field) is not None:
            payload[field] = getattr(row, field)
        elif previous_active is not None and getattr(previous_active, field) is not None:
            payload[field] = getattr(previous_active, field)
    if row is None:
        row = InstituteCalendar(
            id=uuid.uuid4(),
            term_code=term_code,
            is_active=True,
            published_at=now,
            published_by=published_by,
            source_process_instance_id=source_instance.id if source_instance else None,
        )
        db.add(row)
    else:
        row.is_active = True
        row.published_at = now
        row.published_by = published_by
        row.source_process_instance_id = source_instance.id if source_instance else None

    row.term_start_date = payload.get("term_start_date")
    row.term_end_date = payload.get("term_end_date")
    row.registration_open_at = payload.get("registration_open_at")
    row.registration_deadline_at = payload.get("registration_deadline_at")
    row.evaluation_open_at = payload.get("evaluation_open_at")
    row.evaluation_close_at = payload.get("evaluation_close_at")
    row.extra_data = payload.get("extra_data") or {}
    return row


async def _enrich_context_for_calendar_publish(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
) -> dict[str, Any]:
    """برای publish زمستان، فیلدهای تقویم دو ترم را از instance پاییز تکمیل می‌کند."""
    merged = dict(context)
    if instance.process_code != WINTER_PREP:
        return merged
    from app.services.semester_prep_service import load_fall_prep_context_field

    for key in ACADEMIC_CALENDAR_SNAPSHOT_KEYS:
        if _snapshot_value_present(merged.get(key)):
            continue
        val = await load_fall_prep_context_field(db, key)
        if _snapshot_value_present(val):
            merged[key] = val
    return merged


def _calendar_extra_data_snapshot(
    instance: ProcessInstance,
    context: dict[str, Any],
) -> dict[str, Any]:
    extra: dict[str, Any] = {"source_process_code": instance.process_code}
    for key in ACADEMIC_CALENDAR_SNAPSHOT_KEYS:
        val = context.get(key)
        if _snapshot_value_present(val):
            extra[key] = val
    return extra


async def sync_term_dates_to_students(db: AsyncSession, calendar: InstituteCalendar) -> int:
    """term_start_date / term_end_date و پرچم انتشار را روی extra_data دانشجویان فعال sync می‌کند."""
    if not calendar or not calendar.term_start_date:
        return 0
    stmt = select(Student).where(Student.is_sample_data.is_(False))
    students = list((await db.execute(stmt)).scalars().all())
    n = 0
    ts = calendar.term_start_date.isoformat()
    te = calendar.term_end_date.isoformat() if calendar.term_end_date else None
    published_at = (
        calendar.published_at.isoformat()
        if calendar.published_at
        else datetime.now(timezone.utc).isoformat()
    )
    for st in students:
        extra = dict(st.extra_data or {})
        changed = False
        if extra.get("term_start_date") != ts:
            extra["term_start_date"] = ts
            changed = True
        if te and extra.get("term_end_date") != te:
            extra["term_end_date"] = te
            changed = True
        if calendar.term_code and extra.get("active_term_code") != calendar.term_code:
            extra["active_term_code"] = calendar.term_code
            changed = True
        if not extra.get("academic_calendar_published"):
            extra["academic_calendar_published"] = True
            changed = True
        if not extra.get("academic_calendar_published_at"):
            extra["academic_calendar_published_at"] = published_at
            changed = True
        if changed:
            st.extra_data = extra
            flag_modified(st, "extra_data")
            n += 1
    return n


async def publish_calendar_from_instance_context(
    db: AsyncSession,
    instance: ProcessInstance,
    context: dict[str, Any],
    published_by: Optional[uuid.UUID] = None,
    *,
    notify: bool = True,
) -> InstituteCalendar:
    enriched = await _enrich_context_for_calendar_publish(db, instance, context)
    payload = calendar_payload_from_context(enriched, source_process_code=instance.process_code)
    payload["extra_data"] = _calendar_extra_data_snapshot(instance, enriched)
    cal = await upsert_active_calendar(
        db,
        payload=payload,
        published_by=published_by,
        source_instance=instance,
    )
    await sync_term_dates_to_students(db, cal)
    try:
        from app.services.registration_readiness_service import (
            unlock_intro_students_after_calendar_publish,
        )

        await unlock_intro_students_after_calendar_publish(db)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "unlock_intro_students_after_calendar_publish failed"
        )
    if notify:
        try:
            await notify_institute_members_calendar_published(db, term_code=cal.term_code)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "notify_institute_members_calendar_published failed"
            )
    return cal


_INSTITUTE_CALENDAR_NOTIFY_ROLES = frozenset(
    {
        "student",
        "applicant",
        "admin",
        "staff",
        "finance",
        "therapist",
        "supervisor",
        "instructor",
        "site_manager",
        "interviewer",
        "deputy_education",
        "course_committee",
        "teaching_assistant",
        "monitoring_committee_officer",
        "progress_committee",
        "education_committee",
        "supervision_committee",
        "specialized_commission",
        "therapy_committee_chair",
        "therapy_committee_executor",
    }
)

ACADEMIC_CALENDAR_PAGE_PATH = "/panel/academic-calendar"


async def notify_institute_members_calendar_published(
    db: AsyncSession,
    *,
    term_code: str | None = None,
) -> int:
    """اعلان پاپ‌آپ با لینک تقویم آموزشی برای همهٔ کاربران فعال پرتال."""
    from app.models.operational_models import User
    from app.services.panel_flash_messages import create_panel_flash_message

    term_part = f" ({term_code})" if term_code else ""
    message = (
        f"تقویم آموزشی انستیتو{term_part} منتشر شد. "
        "تاریخ‌های ترم پاییز و زمستان و مهلت‌های مهم را مشاهده کنید."
    )
    stmt = select(User.id).where(
        User.is_active.is_(True),
        User.role.in_(tuple(_INSTITUTE_CALENDAR_NOTIFY_ROLES)),
    )
    user_ids = list((await db.execute(stmt)).scalars().all())
    for uid in user_ids:
        await create_panel_flash_message(
            db,
            user_id=uid,
            message=message,
            level="success",
            source_path=ACADEMIC_CALENDAR_PAGE_PATH,
            category="system",
        )
    return len(user_ids)


def calendar_to_response_dict(cal: InstituteCalendar | None) -> dict[str, Any] | None:
    """سریال‌سازی تقویم فعال برای API (admin و panel)."""
    if cal is None:
        return None
    extra = cal.extra_data if isinstance(cal.extra_data, dict) else {}
    source_process_code = (extra.get("source_process_code") or "").strip() or None
    reg_open, reg_deadline = resolve_registration_window(cal)
    return {
        "id": str(cal.id),
        "term_code": cal.term_code,
        "is_active": bool(cal.is_active),
        "term_start_date": cal.term_start_date.isoformat() if cal.term_start_date else None,
        "term_end_date": cal.term_end_date.isoformat() if cal.term_end_date else None,
        "registration_open_at": reg_open.isoformat() if reg_open else None,
        "registration_deadline_at": reg_deadline.isoformat() if reg_deadline else None,
        "evaluation_open_at": cal.evaluation_open_at.isoformat() if cal.evaluation_open_at else None,
        "evaluation_close_at": cal.evaluation_close_at.isoformat() if cal.evaluation_close_at else None,
        "published_at": cal.published_at.isoformat() if cal.published_at else None,
        "source_process_instance_id": str(cal.source_process_instance_id)
        if cal.source_process_instance_id
        else None,
        "source_process_code": source_process_code,
        "extra_data": extra,
    }
