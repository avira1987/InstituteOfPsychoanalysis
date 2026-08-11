"""Simple in-memory rate limiting for login endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import DefaultDict

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

# (client_key, endpoint) -> list of attempt timestamps
_attempts: DefaultDict[tuple[str, str], list[float]] = defaultdict(list)

_PASSWORD_LOGIN_PATHS = frozenset({
    "/api/auth/login",
    "/api/auth/login-json",
})

_OTP_REQUEST_PATH = "/api/auth/otp/request"


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _bucket_key(request: Request, path: str) -> tuple[str, str]:
    return (_client_key(request), path)


def _prune_bucket(bucket: list[float], window: float, now: float) -> list[float]:
    cutoff = now - window
    return [t for t in bucket if t > cutoff]


def check_login_rate_limit(request: Request, path: str | None = None) -> None:
    """اگر سقف تلاش‌ها پر شده باشد 429 می‌دهد؛ خودِ درخواست را ثبت نمی‌کند."""
    settings = get_settings()
    limit = getattr(settings, "LOGIN_RATE_LIMIT_COUNT", 10)
    window = getattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 600)
    path = path or request.scope.get("path", "")
    if path not in _PASSWORD_LOGIN_PATHS and path != _OTP_REQUEST_PATH:
        return
    key = _bucket_key(request, path)
    now = time.time()
    bucket = _prune_bucket(_attempts[key], window, now)
    _attempts[key] = bucket
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد تلاش‌های ورود بیش از حد مجاز است. لطفاً چند دقیقه بعد دوباره تلاش کنید.",
        )


def record_login_attempt(request: Request, path: str | None = None) -> None:
    """ثبت یک تلاش ناموفق یا درخواست OTP."""
    settings = get_settings()
    window = getattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 600)
    path = path or request.scope.get("path", "")
    if path not in _PASSWORD_LOGIN_PATHS and path != _OTP_REQUEST_PATH:
        return
    key = _bucket_key(request, path)
    now = time.time()
    bucket = _prune_bucket(_attempts.get(key, []), window, now)
    bucket.append(now)
    _attempts[key] = bucket


def reset_login_rate_limits() -> None:
    """برای تست — پاک کردن شمارندهٔ حافظه."""
    _attempts.clear()


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.scope.get("path", "")
        if request.method == "POST" and path in _PASSWORD_LOGIN_PATHS.union({_OTP_REQUEST_PATH}):
            check_login_rate_limit(request, path)
        response = await call_next(request)
        if request.method != "POST":
            return response
        if path in _PASSWORD_LOGIN_PATHS and response.status_code in (400, 401):
            record_login_attempt(request, path)
        elif path == _OTP_REQUEST_PATH:
            # هر درخواست OTP (موفق یا ناموفق) برای جلوگیری از اسپم پیامک شمرده می‌شود
            record_login_attempt(request, path)
        return response
