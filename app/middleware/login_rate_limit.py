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


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _is_login_path(path: str) -> bool:
    return path in (
        "/api/auth/login",
        "/api/auth/login-json",
        "/api/auth/otp/request",
    )


def check_login_rate_limit(request: Request) -> None:
    settings = get_settings()
    limit = getattr(settings, "LOGIN_RATE_LIMIT_COUNT", 10)
    window = getattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 600)
    if not _is_login_path(request.scope.get("path", "")):
        return
    key = (_client_key(request), request.scope.get("path", ""))
    now = time.time()
    cutoff = now - window
    bucket = [t for t in _attempts[key] if t > cutoff]
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد تلاش‌های ورود بیش از حد مجاز است. لطفاً چند دقیقه بعد دوباره تلاش کنید.",
        )
    bucket.append(now)
    _attempts[key] = bucket


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "POST" and _is_login_path(request.scope.get("path", "")):
            check_login_rate_limit(request)
        return await call_next(request)
