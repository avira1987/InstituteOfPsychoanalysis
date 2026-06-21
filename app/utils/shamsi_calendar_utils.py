"""Shamsi calendar helpers for semester-prep scheduling."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import jdatetime

TEHRAN = ZoneInfo("Asia/Tehran")


def tehran_today() -> date:
    return datetime.now(TEHRAN).date()


def shamsi_parts(d: date | None = None) -> tuple[int, int, int]:
    g = d or tehran_today()
    j = jdatetime.date.fromgregorian(date=g)
    return j.year, j.month, j.day


def is_farvardin_15_20(d: date | None = None) -> bool:
    """True when today (Tehran) is Farvardin 15–20."""
    _, month, day = shamsi_parts(d)
    return month == 1 and 15 <= day <= 20


def farvardin_20_end_tehran(shamsi_year: int | None = None) -> datetime:
    """End of Farvardin 20 (23:59:59 Tehran) as UTC-aware datetime."""
    sy = shamsi_year or shamsi_parts()[0]
    g = jdatetime.date(sy, 1, 20).togregorian()
    local_end = datetime.combine(g, time(23, 59, 59), tzinfo=TEHRAN)
    return local_end.astimezone(timezone.utc)


def days_before_date(target: date, days: int, today: date | None = None) -> bool:
    ref = today or tehran_today()
    return ref >= (target - __import__("datetime").timedelta(days=days))


def parse_iso_date(value) -> Optional[date]:
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
