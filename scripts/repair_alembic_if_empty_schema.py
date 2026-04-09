#!/usr/bin/env python3
"""
If alembic_version was stamped (e.g. alembic stamp) but no application tables exist,
alembic upgrade would skip 001–007 and fail on later migrations (e.g. 008 on students).

Detect the orphan case: public schema has only the alembic_version table — then clear
alembic_version so `alembic upgrade head` can create the full schema from scratch.
"""

from __future__ import annotations

import asyncio
import os


def _async_dsn() -> str:
    u = os.environ.get("DATABASE_URL", "").strip()
    if not u:
        return ""
    if "+asyncpg" in u:
        return u.replace("postgresql+asyncpg://", "postgresql://", 1)
    return u


async def _main() -> None:
    import asyncpg

    dsn = _async_dsn()
    if not dsn:
        print("repair_alembic: DATABASE_URL not set, skip", flush=True)
        return
    if not dsn.startswith("postgresql://"):
        print("repair_alembic: unexpected DATABASE_URL, skip", flush=True)
        return

    conn = await asyncpg.connect(dsn)
    try:
        n = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
        if n != 1:
            return
        only = await conn.fetchval(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            LIMIT 1
            """
        )
        if only != "alembic_version":
            return
        print(
            "repair_alembic: clearing orphan alembic_version (schema has no app tables)",
            flush=True,
        )
        await conn.execute("DELETE FROM alembic_version")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
