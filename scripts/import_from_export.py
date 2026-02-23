#!/usr/bin/env python3
"""Import data from JSON export into PostgreSQL. Run on server."""

import asyncio
import json
import uuid
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import async_sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://anistito:anistito@localhost:5433/anistito",
)


def esc(s):
    """Escape string for SQL."""
    if s is None:
        return "NULL"
    if isinstance(s, bool):
        return "TRUE" if s else "FALSE"
    if isinstance(s, (int, float)):
        return str(s)
    if isinstance(s, (dict, list)):
        return f"'{json.dumps(s).replace(chr(39), chr(39)+chr(39))}'::jsonb"
    s = str(s).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"


async def import_data(json_path: str):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    tables = data.get("tables", {})

    async with async_session() as session:
        for table, rows in tables.items():
            if not rows:
                continue
            for row in rows:
                try:
                    cols = []
                    vals = []
                    for k, v in row.items():
                        cols.append(f'"{k}"')
                        vals.append(esc(v))
                    cols_s = ", ".join(cols)
                    vals_s = ", ".join(vals)
                    sql = f'INSERT INTO {table} ({cols_s}) VALUES ({vals_s})'
                    await session.execute(text(sql))
                except Exception as e:
                    if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                        pass  # skip duplicate
                    else:
                        print(f"  Error {table}: {e}")
            await session.commit()
            print(f"  {table}: {len(rows)} rows")
        print("Import done.")
    await engine.dispose()


if __name__ == "__main__":
    import_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not import_path:
        import_path = Path(__file__).parent / "anistito_export.json"
        if not import_path.exists():
            import_path = Path(__file__).parent.parent / "anistito_export.json"
    if not Path(import_path).exists():
        print(f"Export file not found: {import_path}")
        exit(1)
    asyncio.run(import_data(str(import_path)))
