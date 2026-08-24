"""Request-scoped logging context via contextvars (safe across asyncio tasks)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

_request_id: ContextVar[str] = ContextVar("anistito_request_id", default="")
_user_id: ContextVar[str] = ContextVar("anistito_user_id", default="")
_method: ContextVar[str] = ContextVar("anistito_method", default="")
_path: ContextVar[str] = ContextVar("anistito_path", default="")
_process_code: ContextVar[str] = ContextVar("anistito_process_code", default="")
_instance_id: ContextVar[str] = ContextVar("anistito_instance_id", default="")


@dataclass(frozen=True)
class LogContext:
    request_id: str = ""
    user_id: str = ""
    method: str = ""
    path: str = ""
    process_code: str = ""
    instance_id: str = ""


def get_log_context() -> LogContext:
    return LogContext(
        request_id=_request_id.get() or "",
        user_id=_user_id.get() or "",
        method=_method.get() or "",
        path=_path.get() or "",
        process_code=_process_code.get() or "",
        instance_id=_instance_id.get() or "",
    )


def bind_request_context(
    *,
    request_id: str = "",
    user_id: str = "",
    method: str = "",
    path: str = "",
) -> None:
    _request_id.set(request_id or "")
    _user_id.set(user_id or "")
    _method.set(method or "")
    _path.set(path or "")
    _process_code.set("")
    _instance_id.set("")


def reset_request_context() -> None:
    _request_id.set("")
    _user_id.set("")
    _method.set("")
    _path.set("")
    _process_code.set("")
    _instance_id.set("")


def bind_process_fields(
    *,
    process_code: Optional[str] = None,
    instance_id: Optional[str] = None,
) -> None:
    """Attach process identifiers to the current request (or background task) context."""
    if process_code is not None:
        _process_code.set(str(process_code))
    if instance_id is not None:
        _instance_id.set(str(instance_id))
