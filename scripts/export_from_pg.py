#!/usr/bin/env python3
"""Export from PostgreSQL to JSON for import into host. Run locally with Docker DB."""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Tables in order - meta first, then operational
TABLES = [
    "rule_definitions",
    "process_definitions",
    "state_definitions",
    "transition_definitions",
    "users",
    "students",
    "process_instances",
    "state_history",
    "therapy_sessions",
    "financial_records",
    "attendance_records",
    "audit_logs",
]

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito",
)


def serialize(val):
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if hasattr(val, "isoformat"):
        return val.isoformat()
    if isinstance(val, (dict, list)):
        return val
    return str(val)


async def main():
    out_path = Path(__file__).parent.parent / "anistito_export.json"
    engine = create_async_engine(DATABASE_URL)

    result = {"exported_at": datetime.now(timezone.utc).isoformat(), "tables": {}}

    async with engine.begin() as conn:
        for table in TABLES:
            try:
                r = await conn.execute(text(f'SELECT * FROM "{table}"'))
                rows = r.fetchall()
                cols = r.keys()
                data = [dict(zip(cols, [serialize(v) for v in row])) for row in rows]
                result["tables"][table] = data
                print(f"  {table}: {len(data)} rows")
            except Exception as e:
                if "does not exist" in str(e):
                    result["tables"][table] = []
                    print(f"  {table}: (skip)")
                else:
                    raise

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Output: {out_path}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
