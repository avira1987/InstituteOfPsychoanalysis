"""محاسبات و دادهٔ UI برای فرایند ۱۷ — کنسل جلسات درمان آموزشی توسط دانشجو."""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import TherapySession


def _iso_week_key(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso.year, iso.week)


async def _session_counts(db: AsyncSession, student_id: uuid.UUID) -> tuple[int, int]:
    """(completed_or_held, already_cancelled) — بدون جلسات فوق‌العاده."""
    stmt = (
        select(TherapySession.status)
        .where(
            TherapySession.student_id == student_id,
            TherapySession.is_extra.is_(False),
            TherapySession.status.in_(("completed", "cancelled")),
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    completed = sum(1 for s in rows if s == "completed")
    cancelled = sum(1 for s in rows if s == "cancelled")
    return completed, cancelled


def compute_cancellation_percent(completed: int, cancelled: int) -> float:
    total = completed + cancelled
    if total <= 0:
        return 0.0
    return round((cancelled / total) * 100.0, 2)


def compute_percent_after(completed: int, cancelled: int, additional: int) -> float:
    return compute_cancellation_percent(completed, cancelled + max(0, additional))


async def get_cancellation_stats(
    db: AsyncSession,
    student_id: uuid.UUID,
    additional_cancellations: int = 0,
) -> dict[str, Any]:
    completed, cancelled = await _session_counts(db, student_id)
    percent_now = compute_cancellation_percent(completed, cancelled)
    percent_after = compute_percent_after(completed, cancelled, additional_cancellations)
    total_base = completed + cancelled + max(0, additional_cancellations)
    allowed_cap = math.ceil(total_base * 0.12) if total_base > 0 else 0
    return {
        "completed_sessions": completed,
        "cancelled_sessions": cancelled,
        "cancellation_percent_now": percent_now,
        "cancellation_percent_after": percent_after,
        "allowed_cancellation_cap_count": allowed_cap,
        "warning_threshold_percent": 10,
        "max_threshold_percent": 12,
    }


def _weeks_empty_after_selection(
    sessions_by_week: dict[tuple[int, int], list[dict]],
    selected_ids: set[str],
) -> set[tuple[int, int]]:
    empty: set[tuple[int, int]] = set()
    for wk, items in sessions_by_week.items():
        if not items:
            continue
        all_cancelled = all(
            it["status"] == "cancelled" or str(it["id"]) in selected_ids
            for it in items
        )
        if all_cancelled:
            empty.add(wk)
    return empty


def _max_consecutive_weeks(weeks: set[tuple[int, int]]) -> int:
    if not weeks:
        return 0
    sorted_weeks = sorted(weeks)
    best = 1
    run = 1
    for i in range(1, len(sorted_weeks)):
        py, pw = sorted_weeks[i - 1]
        cy, cw = sorted_weeks[i]
        if (cy == py and cw == pw + 1) or (cy == py + 1 and pw >= 52 and cw == 1):
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


async def would_exceed_consecutive_cancel_weeks(
    db: AsyncSession,
    student_id: uuid.UUID,
    selected_ids: list[uuid.UUID],
    *,
    lookback_weeks: int = 8,
    lookahead_weeks: int = 4,
) -> bool:
    """آیا انتخاب جدید زنجیرهٔ بیش از ۳ هفتهٔ متوالی بدون جلسهٔ فعال ایجاد می‌کند؟"""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(weeks=lookback_weeks)
    end = today + timedelta(weeks=lookahead_weeks)

    stmt = (
        select(TherapySession)
        .where(
            TherapySession.student_id == student_id,
            TherapySession.is_extra.is_(False),
            TherapySession.session_date >= start,
            TherapySession.session_date <= end,
        )
        .order_by(TherapySession.session_date.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    sel = {str(x) for x in selected_ids}

    by_week: dict[tuple[int, int], list[dict]] = {}
    for ts in rows:
        wk = _iso_week_key(ts.session_date)
        by_week.setdefault(wk, []).append({"id": str(ts.id), "status": ts.status})

    empty = _weeks_empty_after_selection(by_week, sel)
    return _max_consecutive_weeks(empty) > 3


async def get_upcoming_cancellation_sessions(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    display_weeks: int = 3,
) -> list[dict[str, Any]]:
    """جلسات برنامه‌ریزی‌شده در N هفتهٔ آینده برای checkbox_list."""
    today = datetime.now(timezone.utc).date()
    end = today + timedelta(weeks=display_weeks)
    stmt = (
        select(TherapySession)
        .where(
            TherapySession.student_id == student_id,
            TherapySession.session_date >= today,
            TherapySession.session_date <= end,
            TherapySession.status == "scheduled",
            TherapySession.is_extra.is_(False),
        )
        .order_by(TherapySession.session_date.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())

    options: list[dict[str, Any]] = []
    for ts in rows:
        options.append(
            {
                "value": str(ts.id),
                "label_fa": f"{ts.session_date.isoformat()} — جلسهٔ درمان",
                "session_date": ts.session_date.isoformat(),
            }
        )
    return options


async def build_student_cancellation_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    selected_sessions_raw=None,
    display_weeks: int = 3,
) -> dict[str, Any]:
    from app.services.action_handler import parse_therapy_session_id_list

    selected_ids = parse_therapy_session_id_list(selected_sessions_raw)
    stats = await get_cancellation_stats(db, student_id, len(selected_ids))
    upcoming = await get_upcoming_cancellation_sessions(db, student_id, display_weeks=display_weeks)
    would_exceed = False
    if selected_ids:
        would_exceed = await would_exceed_consecutive_cancel_weeks(db, student_id, selected_ids)

    consecutive_block_message_fa = (
        "دانشجوی گرامی، شما مجاز به کنسل کردن جلسات درمان آموزشی به صورت بیش از "
        "۳ هفته متوالی نمی‌باشید و باید برای این کار فرایند «وقفه در درمان آموزشی» را اجرا کنید."
    )
    violation_warning_fa = (
        "دانشجوی محترم، با کنسل کردن جلسات فوق، تعداد کنسلی‌های درمان آموزشی شما از ابتدا "
        "تا به حال به بیشتر از ۱۲ درصد که غیرمجاز است افزایش پیدا خواهد کرد. در صورت ثبت "
        "این جلسات کنسلی جدید، شما مرتکب تخلف می‌شوید و به کمیته نظارت گزارش داده خواهد شد."
    )

    percent_after = float(stats["cancellation_percent_after"])
    return {
        **stats,
        "upcoming_cancellation_sessions": upcoming,
        "would_exceed_consecutive_weeks": would_exceed,
        "consecutive_block_message_fa": consecutive_block_message_fa,
        "violation_warning_message_fa": violation_warning_fa,
        "requires_violation_ack": percent_after > 12,
        "requires_warning_notice": 10 <= percent_after <= 12,
        "display_weeks_ahead": display_weeks,
    }


async def validate_student_cancellation_selection(
    db: AsyncSession,
    student_id: uuid.UUID,
    selected_sessions_raw,
    *,
    require_violation_ack: bool = False,
    violation_ack: bool = False,
) -> Optional[str]:
    from app.services.action_handler import parse_therapy_session_id_list

    selected_ids = parse_therapy_session_id_list(selected_sessions_raw)
    if not selected_ids:
        return "حداقل یک جلسه را برای کنسل انتخاب کنید."

    today = datetime.now(timezone.utc).date()
    end = today + timedelta(weeks=3)
    for sid in selected_ids:
        ts = await db.get(TherapySession, sid)
        if not ts or ts.student_id != student_id:
            return "یکی از جلسات انتخاب‌شده یافت نشد یا متعلق به شما نیست."
        if ts.is_extra:
            return "جلسات فوق‌العاده از این مسیر قابل کنسل نیستند."
        if ts.status != "scheduled":
            return f"فقط جلسات «برنامه‌ریزی‌شده» قابل کنسل هستند ({ts.session_date})."
        if ts.session_date < today or ts.session_date > end:
            return "فقط جلسات ۳ هفتهٔ آینده در این فرایند قابل انتخاب هستند."

    if await would_exceed_consecutive_cancel_weeks(db, student_id, selected_ids):
        return (
            "انتخاب شما منجر به کنسل بیش از ۳ هفته متوالی می‌شود. "
            "برای وقفهٔ طولانی‌تر از فرایند «وقفه در درمان آموزشی» استفاده کنید."
        )

    stats = await get_cancellation_stats(db, student_id, len(selected_ids))
    if float(stats["cancellation_percent_after"]) > 12 and require_violation_ack and not violation_ack:
        return "برای ثبت کنسلی بالای ۱۲٪، تأیید هشدار تخلف در فرم الزامی است."

    return None
