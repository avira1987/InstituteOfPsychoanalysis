"""Unit tests for class_session_cancellation_service — فرایند ۵۶."""

from datetime import date

import pytest

from app.utils.date_utils import add_minutes_to_hhmm, friday_of_term_week
from app.services.class_session_cancellation_service import (
    compute_makeup_datetime,
    parse_session_key,
    session_key,
)


def test_friday_of_term_week_week_one():
    # 2024-09-01 is Sunday; week 1 Friday is 2024-09-06
    term_start = date(2024, 9, 1)
    assert friday_of_term_week(term_start, 1) == date(2024, 9, 6)


def test_friday_of_term_week_15():
    term_start = date(2024, 9, 1)
    friday_15 = friday_of_term_week(term_start, 15)
    assert friday_15.weekday() == 4
    assert (friday_15 - term_start).days >= 14 * 7


def test_add_minutes_to_hhmm():
    assert add_minutes_to_hhmm("10:00", 90) == "11:30"
    assert add_minutes_to_hhmm("14:30", 90) == "16:00"


def test_compute_makeup_datetime_ordinals():
    term_start = date(2024, 9, 1)
    d1, t1, s1 = compute_makeup_datetime(term_start, 1, "10:00")
    d2, t2, s2 = compute_makeup_datetime(term_start, 2, "10:00")
    d3, t3, s3 = compute_makeup_datetime(term_start, 3, "10:00")
    d4, t4, s4 = compute_makeup_datetime(term_start, 4, "10:00")

    assert d1 == friday_of_term_week(term_start, 15)
    assert d2 == d1
    assert t1 == "10:00"
    assert t2 == "11:30"
    assert d3 == friday_of_term_week(term_start, 16)
    assert d4 == d3
    assert t3 == "10:00"
    assert t4 == "11:30"
    assert "کنسلی اول" in s1
    assert "هفته ۱۵" in s1
    assert "هفته ۱۶" in s3


def test_session_key_roundtrip():
    key = session_key("theory_1", 3, "2024-10-15")
    parsed = parse_session_key(key)
    assert parsed is not None
    assert parsed["course_code"] == "theory_1"
    assert parsed["session_number"] == "3"
    assert parsed["session_date"] == "2024-10-15"
