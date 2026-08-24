"""Unit and HTTP tests for structured logging, redaction, and request IDs."""

from __future__ import annotations

import json
import logging

from app.observability.context import bind_request_context, get_log_context, reset_request_context
from app.observability.frontend import observability_bootstrap_script
from app.observability.json_formatter import ContextFilter, JsonFormatter
from app.observability.redact import REDACTED, redact_sentry_event, redact_value
from app.observability.sentry import init_sentry, sentry_enabled
from app.middleware.request_context import (
    normalize_request_id,
    should_emit_access,
    should_skip_access_log,
)


def test_redact_sensitive_keys():
    out = redact_value(
        {
            "username": "ali",
            "password": "hunter2",
            "authorization": "Bearer abc.def",
            "nested": {"otp_code": "123456", "ok": True},
        }
    )
    assert out["username"] == "ali"
    assert out["password"] == REDACTED
    assert out["authorization"] == REDACTED
    assert out["nested"]["otp_code"] == REDACTED
    assert out["nested"]["ok"] is True


def test_redact_card_and_bearer_in_strings():
    text = redact_value("Bearer super-secret-token 4111111111111111")
    assert "super-secret-token" not in text
    assert "4111111111111111" not in text
    assert REDACTED in text


def test_redact_sentry_event_headers():
    event = {
        "request": {
            "headers": {"Authorization": "Bearer abc", "Content-Type": "application/json"},
            "cookies": {"session": "xyz"},
        }
    }
    out = redact_sentry_event(event, None)
    assert out["request"]["headers"]["Authorization"] == REDACTED
    assert out["request"]["headers"]["Content-Type"] == "application/json"
    assert out["request"]["cookies"] == REDACTED


def test_json_formatter_includes_correlation_fields():
    bind_request_context(request_id="rid-test-001", user_id="user-1", method="GET", path="/api/x")
    try:
        record = logging.LogRecord(
            name="tests.obs",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="boom",
            args=(),
            exc_info=None,
        )
        ContextFilter(service="anistito-api", environment="test", release="anistito@1").filter(record)
        record.event = "unhandled_exception"
        record.error_type = "RuntimeError"
        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_request_context()
    assert payload["request_id"] == "rid-test-001"
    assert payload["user_id"] == "user-1"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/x"
    assert payload["event"] == "unhandled_exception"
    assert payload["service"] == "anistito-api"
    assert payload["error_type"] == "RuntimeError"


def test_normalize_and_skip_access_log():
    assert should_skip_access_log("/health")
    assert should_skip_access_log("/health/ready")
    assert should_skip_access_log("/assets/app.js")
    assert not should_skip_access_log("/api/auth/login")
    custom = normalize_request_id("abcDEF12-ok")
    assert custom == "abcDEF12-ok"
    generated = normalize_request_id("bad id")
    assert len(generated) == 32


def test_access_log_always_emits_errors_even_when_sampled_out():
    assert should_emit_access(
        path="/api/foo",
        status_code=500,
        duration_ms=10,
        slow_ms=1000,
        sample_rate=0.0,
    )
    assert should_emit_access(
        path="/api/foo",
        status_code=200,
        duration_ms=5000,
        slow_ms=1000,
        sample_rate=0.0,
    )
    assert not should_emit_access(
        path="/health",
        status_code=200,
        duration_ms=5,
        slow_ms=1000,
        sample_rate=1.0,
    )
    assert not should_emit_access(
        path="/api/foo",
        status_code=200,
        duration_ms=10,
        slow_ms=1000,
        sample_rate=0.0,
    )


def test_sentry_disabled_without_dsn():
    assert sentry_enabled() is False
    assert init_sentry() is False


def test_frontend_bootstrap_script():
    from app.config import get_settings

    html = observability_bootstrap_script(get_settings())
    assert "window.__ANISTITO_OBS__" in html
    assert "sentryDsn" in html


def test_bind_process_fields_on_context():
    from app.observability.context import bind_process_fields

    bind_request_context(request_id="r1", method="POST", path="/api/process")
    bind_process_fields(process_code="start_therapy", instance_id="inst-9")
    try:
        ctx = get_log_context()
        assert ctx.process_code == "start_therapy"
        assert ctx.instance_id == "inst-9"
        assert ctx.request_id == "r1"
    finally:
        reset_request_context()
