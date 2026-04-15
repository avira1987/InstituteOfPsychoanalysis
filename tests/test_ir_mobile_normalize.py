"""Tests for Iranian mobile normalization (OTP / SMS)."""

from app.services.sms_gateway import normalize_ir_mobile


def test_normalize_persian_digits_full():
    assert normalize_ir_mobile("۰۹۱۲۳۴۵۶۷۸۹") == "09123456789"


def test_normalize_plus98():
    assert normalize_ir_mobile("+989123456789") == "09123456789"


def test_normalize_0098():
    assert normalize_ir_mobile("00989123456789") == "09123456789"


def test_normalize_spaces():
    assert normalize_ir_mobile(" 09 12 345 6789 ") == "09123456789"
