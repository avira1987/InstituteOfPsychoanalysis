"""Short-lived HMAC signatures for protected upload URLs (no long-lived JWT in query)."""

from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import quote, urlencode

from app.config import get_settings

DEFAULT_TTL_SECONDS = 300


def _secret() -> bytes:
    return (get_settings().SECRET_KEY or "").encode("utf-8")


def sign_upload_path(path: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS, user_id: str = "") -> dict:
    """Return exp + sig for a /uploads/... path."""
    if not path.startswith("/uploads/"):
        raise ValueError("path must start with /uploads/")
    exp = int(time.time()) + max(30, int(ttl_seconds))
    msg = f"{path}|{exp}|{user_id}".encode("utf-8")
    sig = hmac.new(_secret(), msg, hashlib.sha256).hexdigest()
    qs = urlencode({"exp": str(exp), "sig": sig, "uid": user_id})
    return {
        "path": path,
        "expires_at": exp,
        "signed_url": f"{path}?{qs}",
    }


def verify_upload_signature(path: str, exp: str | int | None, sig: str | None, user_id: str = "") -> bool:
    if not path or not exp or not sig:
        return False
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_i < int(time.time()):
        return False
    msg = f"{path}|{exp_i}|{user_id or ''}".encode("utf-8")
    expected = hmac.new(_secret(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(sig).strip())


def quote_upload_path(path: str) -> str:
    return quote(path, safe="/")
