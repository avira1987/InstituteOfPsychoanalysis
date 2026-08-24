"""Strip secrets and obvious PII from log extras and Sentry events."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "hashed_password",
        "secret",
        "secret_key",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "authorization",
        "api_key",
        "apikey",
        "sms_api_key",
        "sms_password",
        "cookie",
        "set_cookie",
        "otp",
        "otp_code",
        "dev_code",
        "dev_hint",
        "credit_card",
        "card_number",
        "cardnumber",
        "cvv",
        "cvc",
        "sep_password",
        "initial_admin_password",
    }
)

_SENSITIVE_SUFFIXES = (
    "_password",
    "_secret",
    "_token",
    "_api_key",
    "_apikey",
    "_otp",
)

_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_BEARER_RE = re.compile(r"(?i)(bearer\s+)[^\s]+")


def is_sensitive_key(key: str) -> bool:
    k = str(key).lower().replace("-", "_")
    if k in _SENSITIVE_KEYS:
        return True
    return any(k.endswith(suf) for suf in _SENSITIVE_SUFFIXES)


def redact_string(value: str) -> str:
    text = _BEARER_RE.sub(r"\1" + REDACTED, value)
    return _CARD_RE.sub(REDACTED, text)


def redact_value(value: Any, *, key: str = "") -> Any:
    if key and is_sensitive_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {str(k): redact_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        kind = list if isinstance(value, list) else tuple
        return kind(redact_value(item) for item in value)
    if isinstance(value, str):
        return redact_string(value)
    return value


def redact_sentry_event(event: dict, hint: dict | None = None) -> dict:
    """Sentry before_send: never ship passwords, tokens, or card numbers."""
    del hint
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = redact_value(headers)
        cookies = request.get("cookies")
        if cookies:
            request["cookies"] = REDACTED
        data = request.get("data")
        if data is not None:
            request["data"] = redact_value(data)
        query = request.get("query_string")
        if isinstance(query, str):
            request["query_string"] = redact_string(query)
    extra = event.get("extra")
    if isinstance(extra, dict):
        event["extra"] = redact_value(extra)
    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        values = breadcrumbs.get("values")
        if isinstance(values, list):
            for crumb in values:
                if isinstance(crumb, dict) and isinstance(crumb.get("data"), dict):
                    crumb["data"] = redact_value(crumb["data"])
    return event
