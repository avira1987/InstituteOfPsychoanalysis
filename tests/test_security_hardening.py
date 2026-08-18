"""Tests for production security guards and HTML sanitizer."""

import pytest

from app.config import Settings
from app.core.production_guards import validate_production_settings
from app.services.html_sanitize import sanitize_blog_html
from app.services.upload_signing import sign_upload_path, verify_upload_signature


def test_production_guards_reject_weak_secret():
    s = Settings(
        DEBUG=False,
        SECRET_KEY="short",
        PAYMENT_PROVIDER="zibal",
        ZIBAL_MERCHANT="m",
        SMS_PROVIDER="mellipayamak",
        CORS_ALLOW_ORIGINS="https://example.com",
        OTP_RESTRICT_TO_STUDENT_PHONES=True,
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_production_settings(s)


def test_production_guards_reject_http_cors():
    s = Settings(
        DEBUG=False,
        SECRET_KEY="x" * 40,
        PAYMENT_PROVIDER="zibal",
        ZIBAL_MERCHANT="m",
        SMS_PROVIDER="mellipayamak",
        CORS_ALLOW_ORIGINS="http://lms.psychoanalysis.ir",
        OTP_RESTRICT_TO_STUDENT_PHONES=True,
    )
    with pytest.raises(RuntimeError, match="https"):
        validate_production_settings(s)


def test_production_guards_pass_safe_config():
    s = Settings(
        DEBUG=False,
        SECRET_KEY="x" * 40,
        PAYMENT_PROVIDER="zibal",
        ZIBAL_MERCHANT="merchant",
        SMS_PROVIDER="mellipayamak",
        CORS_ALLOW_ORIGINS="https://lms.psychoanalysis.ir",
        OTP_RESTRICT_TO_STUDENT_PHONES=True,
        SMS_SIMULATION_UI=False,
        SEED_DEMO_ON_STARTUP=False,
        ALLOW_DEMO_SEED=False,
        FLOW_THROUGH_SEED_ENABLED=False,
        OTP_SHOW_CODE_IN_UI=False,
        PAYMENT_TEST_BYPASS=False,
    )
    validate_production_settings(s)


def test_production_guards_allow_intentional_public_otp_signup():
    s = Settings(
        DEBUG=False,
        SECRET_KEY="x" * 40,
        PAYMENT_PROVIDER="zibal",
        ZIBAL_MERCHANT="merchant",
        SMS_PROVIDER="mellipayamak",
        CORS_ALLOW_ORIGINS="https://lms.psychoanalysis.ir",
        OTP_RESTRICT_TO_STUDENT_PHONES=False,
        ALLOW_PUBLIC_OTP_SIGNUP=True,
        SMS_SIMULATION_UI=False,
        SEED_DEMO_ON_STARTUP=False,
        ALLOW_DEMO_SEED=False,
        FLOW_THROUGH_SEED_ENABLED=False,
        OTP_SHOW_CODE_IN_UI=False,
        PAYMENT_TEST_BYPASS=False,
    )
    validate_production_settings(s)


def test_sanitize_blog_strips_script():
    dirty = '<p>ok</p><script>alert(1)</script><a href="javascript:alert(1)">x</a>'
    clean = sanitize_blog_html(dirty)
    assert "<script" not in clean.lower()
    assert "javascript:" not in clean.lower()
    assert "<p>ok</p>" in clean


def test_upload_signing_roundtrip():
    signed = sign_upload_path("/uploads/process_instances/abc/file.pdf", user_id="u1")
    assert "sig=" in signed["signed_url"]
    assert verify_upload_signature(
        "/uploads/process_instances/abc/file.pdf",
        signed["expires_at"],
        signed["signed_url"].split("sig=")[1].split("&")[0],
        user_id="u1",
    )
