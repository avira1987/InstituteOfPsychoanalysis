"""Tests for process title normalization (duplicate detection by title)."""

from app.services.process_title import normalize_process_title


def test_normalize_trim_and_spaces():
    assert normalize_process_title("  مرخصی  آموزشی  ") == normalize_process_title("مرخصی آموزشی")


def test_normalize_persian_digits():
    a = normalize_process_title("مرحله ۱۲")
    b = normalize_process_title("مرحله 12")
    assert a == b
