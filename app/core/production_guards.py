"""Startup validation for production-unsafe configuration."""

from __future__ import annotations

import logging

from app.config import Settings

logger = logging.getLogger(__name__)

_WEAK_SECRET_KEYS = frozenset(
    {
        "change-me-in-production-use-a-real-secret-key",
        "anistito-prod-secret-change-me",
        "secret",
        "changeme",
    }
)


def validate_production_settings(settings: Settings) -> None:
    """Raise RuntimeError when DEBUG=false but config is unsafe for real deployment."""
    if settings.DEBUG:
        logger.info("DEBUG=true — production guards skipped")
        return

    errors: list[str] = []

    sk = (settings.SECRET_KEY or "").strip()
    if not sk or sk.lower() in _WEAK_SECRET_KEYS or len(sk) < 32:
        errors.append("SECRET_KEY must be a strong random value (≥32 chars) when DEBUG=false")

    if settings.PAYMENT_TEST_BYPASS:
        errors.append("PAYMENT_TEST_BYPASS must be false in production")

    provider = (settings.PAYMENT_PROVIDER or "mock").strip().lower()
    if provider == "mock":
        errors.append("PAYMENT_PROVIDER must not be 'mock' when DEBUG=false")

    if provider == "saman" and not (settings.SEP_TERMINAL_ID or "").strip():
        errors.append("SEP_TERMINAL_ID is required when PAYMENT_PROVIDER=saman")

    if provider == "zibal" and not (settings.ZIBAL_MERCHANT or "").strip():
        errors.append("ZIBAL_MERCHANT is required when PAYMENT_PROVIDER=zibal")

    if provider == "zarinpal" and not (settings.ZARINPAL_MERCHANT_ID or "").strip():
        errors.append("ZARINPAL_MERCHANT_ID is required when PAYMENT_PROVIDER=zarinpal")

    sms = (settings.SMS_PROVIDER or "log").strip().lower()
    if sms != "mellipayamak":
        errors.append("SMS_PROVIDER must be 'mellipayamak' when DEBUG=false")

    cors = (settings.CORS_ALLOW_ORIGINS or "").strip()
    if cors in ("", "*"):
        errors.append("CORS_ALLOW_ORIGINS must list explicit domains (not *) when DEBUG=false")

    if settings.OTP_SHOW_CODE_IN_UI:
        errors.append("OTP_SHOW_CODE_IN_UI must be false in production")

    if errors:
        msg = "Production configuration unsafe:\n  - " + "\n  - ".join(errors)
        raise RuntimeError(msg)

    logger.info("Production configuration guards passed")
