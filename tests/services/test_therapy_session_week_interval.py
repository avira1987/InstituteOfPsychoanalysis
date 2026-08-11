"""تست بذر تاریخ جلسات با week_interval (هفتگی / هفته‌درمیان)."""

from datetime import date
from types import SimpleNamespace

from app.services.therapy_session_schedule import (
    expand_session_dates_for_slots,
    expand_weekly_session_dates,
)


def test_expand_weekly_every_week():
    first = date(2026, 8, 10)  # دوشنبه
    until = date(2026, 9, 7)
    out = expand_weekly_session_dates(first, [0], until, week_interval=1)
    assert out[0] == first
    assert all((b - a).days == 7 for a, b in zip(out, out[1:]))


def test_expand_weekly_biweekly():
    first = date(2026, 8, 10)  # دوشنبه
    until = date(2026, 10, 5)
    out = expand_weekly_session_dates(first, [0], until, week_interval=2)
    assert out[0] == first
    assert all((b - a).days == 14 for a, b in zip(out, out[1:]))


def test_expand_session_dates_for_slots_mixed_intervals():
    first = date(2026, 8, 10)
    until = date(2026, 9, 21)
    slots = [
        SimpleNamespace(day_of_week=0, week_interval=1),  # هر دوشنبه
        SimpleNamespace(day_of_week=2, week_interval=2),  # چهارشنبه هفته‌درمیان
    ]
    out = expand_session_dates_for_slots(first, slots, until)
    mondays = [d for d in out if d.weekday() == 0]
    wednesdays = [d for d in out if d.weekday() == 2]
    assert len(mondays) >= 4
    assert all((b - a).days == 7 for a, b in zip(mondays, mondays[1:]))
    assert wednesdays
    assert all((b - a).days == 14 for a, b in zip(wednesdays, wednesdays[1:]))
