#!/usr/bin/env python3
"""
If alembic_version was stamped (e.g. alembic stamp) but application tables are missing
or incomplete, alembic upgrade would skip 001–007 and fail on later migrations.

Detect orphan / drift cases and clear alembic_version so `alembic upgrade head` can
create or repair the full schema from scratch.
"""

from __future__ import annotations

import asyncio
import os

# جداول پایه که بدون آن‌ها اسکیما ناقص است (مثلاً stamp روی head ولی users وجود ندارد)
_CORE_TABLES = (
    "users",
    "students",
    "process_instances",
    "process_definitions",
    "interview_slots",
    "payment_pending",
    "otp_codes",
)


async def _table_exists(conn, name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                  AND table_name = $1
            )
            """,
            name,
        )
    )


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
        has_alembic = await _table_exists(conn, "alembic_version")
        if not has_alembic:
            return

        stamped = await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
        if not stamped:
            return

        n = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
        if n == 1:
            only = await conn.fetchval(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                LIMIT 1
                """
            )
            if only == "alembic_version":
                print(
                    "repair_alembic: clearing orphan alembic_version (schema has no app tables)",
                    flush=True,
                )
                await conn.execute("DELETE FROM alembic_version")
                return

        missing_core = [t for t in _CORE_TABLES if not await _table_exists(conn, t)]
        if missing_core:
            print(
                "repair_alembic: stamped %s but missing core tables %s — clearing alembic_version"
                % (stamped, ", ".join(missing_core)),
                flush=True,
            )
            await conn.execute("DELETE FROM alembic_version")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(_main())
