"""JSON and text formatters that always include correlation fields."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.observability.context import get_log_context
from app.observability.redact import redact_value

_RESERVED_RECORD_KEYS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
        "asctime",
        "otelSpanID",
        "otelTraceID",
        "otelServiceName",
        "otelTraceSampled",
    }
)


class ContextFilter(logging.Filter):
    """Copy contextvars + process identity onto every LogRecord."""

    def __init__(self, *, service: str, environment: str, release: str) -> None:
        super().__init__()
        self.service = service
        self.environment = environment
        self.release = release

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = get_log_context()
        record.service = self.service
        record.environment = self.environment
        record.release = self.release
        record.request_id = getattr(record, "request_id", None) or ctx.request_id or ""
        record.user_id = getattr(record, "user_id", None) or ctx.user_id or ""
        record.method = getattr(record, "method", None) or ctx.method or ""
        record.path = getattr(record, "path", None) or ctx.path or ""
        record.process_code = getattr(record, "process_code", None) or ctx.process_code or ""
        record.instance_id = getattr(record, "instance_id", None) or ctx.instance_id or ""
        return True


def _record_extras(record: logging.LogRecord) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in _RESERVED_RECORD_KEYS or key.startswith("_"):
            continue
        extra[key] = value
    return extra


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "service": getattr(record, "service", "") or "",
            "environment": getattr(record, "environment", "") or "",
            "release": getattr(record, "release", "") or "",
            "message": record.getMessage(),
        }
        extras = _record_extras(record)
        # Prefer explicit extra.event over message for the event field
        event = extras.pop("event", None) or None
        if event:
            payload["event"] = event
        for key in (
            "request_id",
            "user_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "error_type",
            "error_message",
            "error_id",
            "process_code",
            "instance_id",
            "service",
            "environment",
            "release",
        ):
            extras.pop(key, None)
        for key in (
            "request_id",
            "user_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "error_type",
            "error_message",
            "error_id",
            "process_code",
            "instance_id",
        ):
            value = getattr(record, key, None)
            if value not in (None, ""):
                payload[key] = value
        if extras:
            payload["extra"] = extras
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact_value(payload), ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(
            fmt="%(levelname)s %(name)s [rid=%(request_id)s] %(message)s",
        )
