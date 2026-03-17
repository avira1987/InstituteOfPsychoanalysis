"""Date utilities for Shamsi (Jalali) calendar and academic term week."""

from datetime import date, datetime, timezone


def get_current_term_week(term_start: date | None = None, today: date | None = None) -> int:
    """Return current academic week number (1-based) since term start.

    Used by rules such as week_9_deadline. If term_start is None, uses a default
    fall term start (September 1 of current or previous year).
    """
    if today is None:
        today = datetime.now(timezone.utc).date()
    if term_start is None:
        # Default: fall term starts Sept 1
        if today.month >= 9:
            term_start = date(today.year, 9, 1)
        else:
            term_start = date(today.year - 1, 9, 1)
    if today < term_start:
        return 1
    days = (today - term_start).days
    week = days // 7 + 1
    return max(1, week)


def get_current_shamsi_year(dt: datetime | date | None = None) -> int:
    """Return current Shamsi (Jalali) year.

    Uses approximate conversion: Shamsi year ≈ Gregorian year - 621 for March onwards,
    else Gregorian year - 622. For precise conversion, consider using jdatetime.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if isinstance(dt, datetime):
        dt = dt.date()
    g_year = dt.year
    g_month = dt.month
    # Approximate: from ~March 21 (Farvardin 1) onward, Shamsi year = Gregorian - 621
    if g_month >= 3:
        return g_year - 621
    return g_year - 622
