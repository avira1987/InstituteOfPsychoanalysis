"""In-memory ring of recent errors / slow requests for the admin diagnostics panel."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

_LOCK = threading.Lock()
_RECENT: deque[dict[str, Any]] = deque(maxlen=200)
_STARTED_AT = time.time()
_HTTP_5XX = 0
_SLOW_REQUESTS = 0
_UNHANDLED = 0


def record_event(
    *,
    kind: str,
    request_id: str = "",
    method: str = "",
    path: str = "",
    status_code: int | None = None,
    duration_ms: float | None = None,
    error_type: str = "",
    error_message: str = "",
    event: str = "",
) -> None:
    global _HTTP_5XX, _SLOW_REQUESTS, _UNHANDLED
    item = {
        "ts": time.time(),
        "kind": kind,
        "event": event or kind,
        "request_id": request_id or "",
        "method": method or "",
        "path": path or "",
        "status_code": status_code,
        "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        "error_type": error_type or "",
        "error_message": (error_message or "")[:400],
    }
    with _LOCK:
        _RECENT.appendleft(item)
        if kind == "http_5xx":
            _HTTP_5XX += 1
        if kind == "slow_request":
            _SLOW_REQUESTS += 1
        if kind == "unhandled":
            _UNHANDLED += 1


def snapshot(limit: int = 50) -> dict[str, Any]:
    with _LOCK:
        items = list(_RECENT)[: max(0, min(limit, 200))]
        http_5xx = _HTTP_5XX
        slow = _SLOW_REQUESTS
        unhandled = _UNHANDLED
    return {
        "started_at": _STARTED_AT,
        "uptime_seconds": int(time.time() - _STARTED_AT),
        "http_5xx": http_5xx,
        "slow_requests": slow,
        "unhandled_exceptions": unhandled,
        "recent": items,
    }


def reset_for_tests() -> None:
    global _HTTP_5XX, _SLOW_REQUESTS, _UNHANDLED
    with _LOCK:
        _RECENT.clear()
        _HTTP_5XX = 0
        _SLOW_REQUESTS = 0
        _UNHANDLED = 0
