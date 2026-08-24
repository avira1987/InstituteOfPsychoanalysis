"""Log SQL statements that exceed SLOW_SQL_MS (no bind parameters — may contain PII)."""

from __future__ import annotations

import logging
import time

from sqlalchemy import event

logger = logging.getLogger("app.observability.sql")

_QUERY_START_KEY = "anistito_query_start"
_registered_engine_ids: set[int] = set()


def _truncate_sql(statement: object, limit: int = 500) -> str:
    text = " ".join(str(statement).split())
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def register_slow_sql_listener(async_engine) -> None:
    """Attach before/after cursor listeners on the sync engine behind AsyncEngine."""
    sync_engine = getattr(async_engine, "sync_engine", None)
    if sync_engine is None:
        return
    engine_id = id(sync_engine)
    if engine_id in _registered_engine_ids:
        return
    _registered_engine_ids.add(engine_id)

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info[_QUERY_START_KEY] = time.perf_counter()

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start = conn.info.pop(_QUERY_START_KEY, None)
        if start is None:
            return
        elapsed_ms = (time.perf_counter() - start) * 1000
        try:
            from app.config import get_settings

            threshold = float(getattr(get_settings(), "SLOW_SQL_MS", 500) or 500)
        except Exception:
            threshold = 500.0
        if elapsed_ms < threshold:
            return
        logger.warning(
            "db.slow_query",
            extra={
                "event": "db.slow_query",
                "duration_ms": round(elapsed_ms, 1),
                "sql": _truncate_sql(statement),
            },
        )
