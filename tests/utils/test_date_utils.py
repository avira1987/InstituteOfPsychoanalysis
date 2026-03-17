"""Tests for date_utils."""

import pytest
from datetime import date, datetime, timezone

from app.utils.date_utils import get_current_shamsi_year, get_current_term_week


def test_get_current_term_week_with_start():
    """Term week is 1-based from term_start."""
    term_start = date(2024, 9, 1)
    assert get_current_term_week(term_start=term_start, today=date(2024, 9, 1)) == 1
    assert get_current_term_week(term_start=term_start, today=date(2024, 9, 7)) == 1
    assert get_current_term_week(term_start=term_start, today=date(2024, 9, 8)) == 2
    assert get_current_term_week(term_start=term_start, today=date(2024, 10, 20)) == 8


def test_get_current_term_week_before_term():
    """When today is before term_start, return 1."""
    term_start = date(2024, 9, 1)
    assert get_current_term_week(term_start=term_start, today=date(2024, 8, 15)) == 1


def test_get_current_term_week_default_fall():
    """When term_start is None, uses default fall term (Sept 1)."""
    # Today in October -> same year Sept 1
    week = get_current_term_week(term_start=None, today=date(2024, 10, 1))
    assert week >= 4  # ~4 weeks into October from Sept 1


def test_get_current_shamsi_year_march():
    """March is in next Shamsi year (Farvardin)."""
    # 2024-03-21 ≈ 1403/01/01
    dt = date(2024, 3, 21)
    assert get_current_shamsi_year(dt) == 1403


def test_get_current_shamsi_year_january():
    """January is still previous Shamsi year."""
    dt = date(2024, 1, 15)
    assert get_current_shamsi_year(dt) == 1402


def test_get_current_shamsi_year_none_uses_now():
    """When dt is None, uses current UTC time."""
    year = get_current_shamsi_year(None)
    assert 1390 < year < 1450  # sanity range
