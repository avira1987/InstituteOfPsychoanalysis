"""Tehran-local datetime formatting for notifications."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.utils.shamsi_calendar_utils import (
    format_shamsi_date,
    format_shamsi_datetime_for_sms,
    normalize_sms_context_dates,
    tehran_datetime_parts,
)


def test_tehran_datetime_parts_converts_from_utc() -> None:
    # 2026-05-07 10:30 Tehran == 2026-05-07 07:00 UTC (no DST in May)
    dt = datetime(2026, 5, 7, 7, 0, tzinfo=timezone.utc)
    date_s, time_s = tehran_datetime_parts(dt)
    assert date_s == "1405/02/17"
    assert time_s == "10:30"


def test_tehran_datetime_parts_handles_naive_as_utc() -> None:
    dt = datetime(2026, 5, 7, 7, 0)
    date_s, time_s = tehran_datetime_parts(dt)
    assert date_s == "1405/02/17"
    assert time_s == "10:30"


def test_format_shamsi_date_from_iso() -> None:
    assert format_shamsi_date("2026-05-07") == "1405/02/17"
    assert format_shamsi_date("1405/02/17") == "1405/02/17"


def test_format_shamsi_datetime_for_sms() -> None:
    dt = datetime(2026, 5, 7, 7, 0, tzinfo=timezone.utc)
    assert format_shamsi_datetime_for_sms(dt) == "1405/02/17 10:30"


def test_normalize_sms_context_dates_converts_known_fields() -> None:
    ctx = normalize_sms_context_dates(
        {
            "student_name": "علی",
            "deadline": "2026-05-07",
            "session_date": date(2026, 5, 7),
            "day": "شنبه",
            "session_time": "10:30",
            "absence_dates": "2026-05-01, 2026-05-07",
        }
    )
    assert ctx["deadline"] == "1405/02/17"
    assert ctx["session_date"] == "1405/02/17"
    assert ctx["day"] == "شنبه"
    assert ctx["session_time"] == "10:30"
    assert "1405" in ctx["absence_dates"]
