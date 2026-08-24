"""Central logging configuration — call before creating the FastAPI app and again in lifespan."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.observability.json_formatter import ContextFilter, JsonFormatter, TextFormatter

_configured = False

_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "uvicorn.access",
    "uvicorn.error",
    "asyncio",
)


def effective_environment(settings) -> str:
    raw = (getattr(settings, "ENVIRONMENT", None) or "").strip()
    if raw:
        return raw
    return "development" if getattr(settings, "DEBUG", False) else "production"


def _level_from_name(name: str) -> int:
    return getattr(logging, (name or "INFO").upper(), logging.INFO)


def setup_logging(settings=None, *, force: bool = False) -> None:
    """Configure root logging for JSON (prod) or text (tests/dev override)."""
    global _configured
    if _configured and not force:
        return

    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    level = _level_from_name(getattr(settings, "LOG_LEVEL", "INFO"))
    fmt = (getattr(settings, "LOG_FORMAT", "json") or "json").strip().lower()
    service = (getattr(settings, "LOG_SERVICE_NAME", None) or "anistito-api").strip()
    environment = effective_environment(settings)
    release = f"anistito@{getattr(settings, 'APP_VERSION', '0')}"

    ctx_filter = ContextFilter(service=service, environment=environment, release=release)
    formatter: logging.Formatter = JsonFormatter() if fmt == "json" else TextFormatter()

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(level)
    stream.addFilter(ctx_filter)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    log_file = (getattr(settings, "LOG_FILE", None) or "").strip()
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=20 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.addFilter(ctx_filter)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    if getattr(settings, "DATABASE_ECHO", False):
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _configured = True


def is_logging_configured() -> bool:
    return _configured
