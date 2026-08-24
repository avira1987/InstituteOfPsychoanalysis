"""Optional Sentry/GlitchTip init. No-op when DSN is empty or SDK is missing."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_initialized = False
_sdk: Any = None


def sentry_sdk_module():
    global _sdk
    if _sdk is False:
        return None
    if _sdk is not None:
        return _sdk
    try:
        import sentry_sdk as sdk

        _sdk = sdk
        return sdk
    except ImportError:
        _sdk = False
        return None


def sentry_enabled(settings=None) -> bool:
    if settings is None:
        from app.config import get_settings

        settings = get_settings()
    dsn = (getattr(settings, "SENTRY_DSN", None) or "").strip()
    return bool(dsn) and sentry_sdk_module() is not None


def frontend_sentry_dsn(settings=None) -> str:
    if settings is None:
        from app.config import get_settings

        settings = get_settings()
    return (getattr(settings, "SENTRY_DSN_FRONTEND", None) or "").strip()


def dsn_connect_hosts(settings=None) -> list[str]:
    """Hosts to allow in CSP connect-src for Sentry ingest."""
    if settings is None:
        from app.config import get_settings

        settings = get_settings()
    hosts: list[str] = []
    for raw in (
        getattr(settings, "SENTRY_DSN", "") or "",
        getattr(settings, "SENTRY_DSN_FRONTEND", "") or "",
    ):
        host = urlparse(raw.strip()).hostname
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def init_sentry(settings=None) -> bool:
    """Initialize Sentry once. Returns True if enabled."""
    global _initialized
    if _initialized:
        return sentry_sdk_module() is not None and sentry_enabled(settings)

    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    dsn = (getattr(settings, "SENTRY_DSN", None) or "").strip()
    sdk = sentry_sdk_module()
    if not dsn:
        _initialized = True
        return False
    if sdk is None:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed — skipping Sentry")
        _initialized = True
        return False

    from app.observability.redact import redact_sentry_event
    from app.observability.setup import effective_environment

    traces = float(getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0) or 0)
    traces = max(0.0, min(traces, 0.05))

    integrations = []
    try:
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        integrations = [
            StarletteIntegration(middleware_spans=False),
            FastApiIntegration(middleware_spans=False),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ]
    except Exception:
        logger.exception("Sentry integrations failed to load")

    sdk.init(
        dsn=dsn,
        environment=effective_environment(settings),
        release=f"anistito@{getattr(settings, 'APP_VERSION', '0')}",
        send_default_pii=False,
        traces_sample_rate=traces,
        profiles_sample_rate=0,
        before_send=redact_sentry_event,
        integrations=integrations,
    )
    _initialized = True
    logger.info("Sentry initialized (environment=%s)", effective_environment(settings))
    return True


def bind_sentry_request(request_id: str, user_id: str = "") -> None:
    sdk = sentry_sdk_module()
    if sdk is None or not _initialized:
        return
    try:
        sdk.set_tag("request_id", request_id or "")
        if user_id:
            sdk.set_user({"id": user_id})
        else:
            sdk.set_user(None)
    except Exception:
        pass
