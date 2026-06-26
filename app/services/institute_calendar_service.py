"""مدیریت تقویم آموزشی فعال انستیتو."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import InstituteCalendar, ProcessInstance, Student


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

    reg_open = _parse_datetime(
        ctx.get("registration_open_at")
        or ctx.get("registration_open_date")
        or ctx.get("registration_payment_window_start")
    )
    reg_deadline = _parse_datetime(
        ctx.get("registration_deadline_at")
        or ctx.get("registration_deadline")
        or ctx.get("next_term_registration_deadline")
        or ctx.get("registration_payment_window_end")
    )
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
    await deactivate_all_calendars(db)
    term_code = payload["term_code"]
    stmt = select(InstituteCalendar).where(InstituteCalendar.term_code == term_code)
    row = (await db.execute(stmt)).scalars().first()
    now = datetime.now(timezone.utc)
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


async def sync_term_dates_to_students(db: AsyncSession, calendar: InstituteCalendar) -> int:
    """term_start_date / term_end_date را روی extra_data دانشجویان فعال sync می‌کند."""
    if not calendar or not calendar.term_start_date:
        return 0
    stmt = select(Student).where(Student.is_sample_data.is_(False))
    students = list((await db.execute(stmt)).scalars().all())
    n = 0
    ts = calendar.term_start_date.isoformat()
    te = calendar.term_end_date.isoformat() if calendar.term_end_date else None
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
) -> InstituteCalendar:
    payload = calendar_payload_from_context(context, source_process_code=instance.process_code)
    snapshot_keys = (
        "nowruz_holiday_start",
        "nowruz_holiday_end",
        "fall_start_date",
        "fall_end_date",
        "winter_start_date",
        "winter_end_date",
        "registration_payment_window_start",
        "registration_payment_window_end",
    )
    payload["extra_data"] = {
        "source_process_code": instance.process_code,
        **{k: context.get(k) for k in snapshot_keys if context.get(k)},
    }
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
    return cal


def calendar_to_response_dict(cal: InstituteCalendar | None) -> dict[str, Any] | None:
    """سریال‌سازی تقویم فعال برای API (admin و panel)."""
    if cal is None:
        return None
    return {
        "id": str(cal.id),
        "term_code": cal.term_code,
        "is_active": bool(cal.is_active),
        "term_start_date": cal.term_start_date.isoformat() if cal.term_start_date else None,
        "term_end_date": cal.term_end_date.isoformat() if cal.term_end_date else None,
        "registration_open_at": cal.registration_open_at.isoformat() if cal.registration_open_at else None,
        "registration_deadline_at": cal.registration_deadline_at.isoformat() if cal.registration_deadline_at else None,
        "evaluation_open_at": cal.evaluation_open_at.isoformat() if cal.evaluation_open_at else None,
        "evaluation_close_at": cal.evaluation_close_at.isoformat() if cal.evaluation_close_at else None,
        "published_at": cal.published_at.isoformat() if cal.published_at else None,
        "extra_data": cal.extra_data if isinstance(cal.extra_data, dict) else {},
    }
