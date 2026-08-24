"""HTTP request correlation, access logging, and slow-request detection."""

from __future__ import annotations

import logging
import random
import re
import time
import uuid

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import get_settings
from app.observability.context import bind_request_context, reset_request_context
from app.observability.ring_buffer import record_event
from app.observability.sentry import bind_sentry_request

logger = logging.getLogger("app.observability.access")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_SKIP_EXACT = frozenset({"/health", "/health/ready", "/favicon.ico"})
_ALWAYS_LOG_PREFIXES = ("/api/payment", "/api/auth")


def normalize_request_id(raw: str | None) -> str:
    value = (raw or "").strip()
    if value and _REQUEST_ID_RE.match(value):
        return value
    return uuid.uuid4().hex


def should_skip_access_log(path: str) -> bool:
    if path in _SKIP_EXACT:
        return True
    return path.startswith("/assets/") or path.startswith("/anistito/assets/")


def is_sensitive_path(path: str) -> bool:
    return any(path.startswith(p) for p in _ALWAYS_LOG_PREFIXES)


def user_id_from_authorization(header: str | None) -> str:
    if not header:
        return ""
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    token = parts[1].strip()
    if not token:
        return ""
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub else ""
    except (JWTError, Exception):
        return ""


def should_emit_access(
    *,
    path: str,
    status_code: int,
    duration_ms: float,
    slow_ms: float,
    sample_rate: float,
) -> bool:
    if should_skip_access_log(path):
        return False
    if status_code >= 400:
        return True
    if duration_ms >= slow_ms:
        return True
    if is_sensitive_path(path):
        return True
    rate = max(0.0, min(float(sample_rate), 1.0))
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    return random.random() < rate


def _finish_request(
    *,
    request_id: str,
    user_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    settings,
) -> None:
    slow_ms = float(getattr(settings, "SLOW_REQUEST_MS", 1000) or 1000)
    sample_rate = float(getattr(settings, "LOG_ACCESS_SAMPLE_RATE", 1.0) or 1.0)
    extra = {
        "event": "http.request",
        "request_id": request_id,
        "user_id": user_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 1),
    }
    if should_emit_access(
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        slow_ms=slow_ms,
        sample_rate=sample_rate,
    ):
        logger.info("http.request", extra=extra)
    if duration_ms >= slow_ms and not should_skip_access_log(path):
        extra_slow = dict(extra)
        extra_slow["event"] = "http.slow_request"
        logger.warning("http.slow_request", extra=extra_slow)
        record_event(
            kind="slow_request",
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            event="http.slow_request",
        )
    if status_code >= 500 and not should_skip_access_log(path):
        record_event(
            kind="http_5xx",
            request_id=request_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            event="http.request",
        )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.scope.get("path", "") or ""
        method = request.method
        request_id = normalize_request_id(request.headers.get("x-request-id"))
        user_id = user_id_from_authorization(request.headers.get("authorization"))
        bind_request_context(
            request_id=request_id,
            user_id=user_id,
            method=method,
            path=path,
        )
        bind_sentry_request(request_id, user_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            _finish_request(
                request_id=request_id,
                user_id=user_id,
                method=method,
                path=path,
                status_code=500,
                duration_ms=duration_ms,
                settings=settings,
            )
            reset_request_context()
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        status_code = int(getattr(response, "status_code", 500) or 500)
        _finish_request(
            request_id=request_id,
            user_id=user_id,
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            settings=settings,
        )
        response.headers["X-Request-ID"] = request_id
        reset_request_context()
        return response
