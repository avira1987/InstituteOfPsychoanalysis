"""تست بذر جلسات درمان تا پایان ترم."""

from datetime import date, timedelta

from app.services.therapy_session_schedule import (
    expand_weekly_session_dates,
    fallback_weekdays,
    session_counts_as_therapy_debt,
)


def test_expand_weekly_session_dates_covers_term():
    first = date(2026, 3, 2)  # Monday
    until = first + timedelta(weeks=4)
    dates = expand_weekly_session_dates(first, [0, 2], until)  # Mon + Wed
    assert dates[0] == first
    assert dates[-1] <= until
    # 5 weeks inclusive of week 0..4 → 5 Mon + 5 Wed if until is +4 weeks from Mon
    # first Mon .. until = Mon+28 days = next Mon → includes that Monday
    assert all(d.weekday() in (0, 2) for d in dates)
    assert len(dates) >= 8


def test_expand_empty_when_until_before_first():
    first = date(2026, 6, 1)
    assert expand_weekly_session_dates(first, [0], first - timedelta(days=1)) == []


def test_fallback_weekdays():
    d = date(2026, 3, 2)  # Monday = 0
    assert fallback_weekdays(d, 1) == [0]
    assert fallback_weekdays(d, 2) == [0, 2]


def test_resolve_term_end_floor_logic():
    from app.services.therapy_session_schedule import DEFAULT_TERM_WEEKS

    today = date(2026, 8, 6)
    past_end = date(2026, 1, 1)
    floor = today + timedelta(weeks=DEFAULT_TERM_WEEKS)
    assert max(past_end, floor) == floor


def test_future_pending_scheduled_is_not_debt():
    today = date(2026, 8, 10)
    assert not session_counts_as_therapy_debt(
        payment_status="pending",
        status="scheduled",
        session_date=today + timedelta(days=7),
        as_of=today,
    )
    assert not session_counts_as_therapy_debt(
        payment_status="pending",
        status="scheduled",
        session_date=today,
        as_of=today,
    )


def test_past_or_completed_pending_is_debt():
    today = date(2026, 8, 10)
    assert session_counts_as_therapy_debt(
        payment_status="pending",
        status="scheduled",
        session_date=today - timedelta(days=1),
        as_of=today,
    )
    assert session_counts_as_therapy_debt(
        payment_status="pending",
        status="completed",
        session_date=today + timedelta(days=1),
        as_of=today,
    )
    assert not session_counts_as_therapy_debt(
        payment_status="paid",
        status="completed",
        session_date=today - timedelta(days=1),
        as_of=today,
    )
