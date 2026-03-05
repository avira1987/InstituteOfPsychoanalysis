#!/usr/bin/env python3
"""Truncate meta tables and import from JSON."""
import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito")


BOOL_COLUMNS = {"is_active", "is_intern", "therapy_started", "is_completed", "is_cancelled", "is_extra"}


def esc(s, col_name=""):
    if s is None:
        return "NULL"
    if isinstance(s, bool):
        return "TRUE" if s else "FALSE"
    if isinstance(s, int) and col_name in BOOL_COLUMNS:
        return "TRUE" if s == 1 else "FALSE"
    if isinstance(s, (int, float)):
        return str(s)
    if isinstance(s, (dict, list)):
        return f"'{json.dumps(s).replace(chr(39), chr(39)+chr(39))}'::jsonb"
    if isinstance(s, str) and s.lower() == "null":
        return "NULL"
    return f"'{str(s).replace(chr(39), chr(39)+chr(39))}'"


async def main():
    json_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/anistito_export.json"
    if not Path(json_path).exists():
        print(f"File not found: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Truncate all tables for full sync (including users)
    truncate_order = [
        "state_history", "process_instances", "therapy_sessions", "financial_records", "attendance_records",
        "state_definitions", "transition_definitions", "students", "process_definitions", "rule_definitions",
        "audit_logs", "users"
    ]
    async with engine.begin() as conn:
        for t in truncate_order:
            try:
                await conn.execute(text(f'TRUNCATE TABLE "{t}" CASCADE'))
                print(f"Truncated {t}")
            except Exception as e:
                pass  # table may not exist

    # Import
    async with session_factory() as session:
        for table, rows in data.get("tables", {}).items():
            if not rows:
                continue
            count = 0
            for row in rows:
                try:
                    cols = [f'"{k}"' for k in row.keys()]
                    vals = [esc(row[k], k) for k in row.keys()]
                    sql = f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({", ".join(vals)})'
                    await session.execute(text(sql))
                    await session.commit()
                    count += 1
                except Exception as e:
                    await session.rollback()
                    if "duplicate" not in str(e).lower() and "unique" not in str(e).lower():
                        print(f"  Error {table}: {e}")
            print(f"  {table}: {count}/{len(rows)} rows")

    print("Import done.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
