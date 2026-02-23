"""Import data from db_export.json directly into PostgreSQL via SQL."""
import json
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.database import engine, init_db
from sqlalchemy import text, inspect

TABLES_ORDER = [
    "users", "process_definitions", "rule_definitions",
    "state_definitions", "transition_definitions",
    "students", "process_instances", "state_history",
    "audit_logs", "therapy_sessions", "financial_records",
    "attendance_records",
]

BOOL_COLUMNS = {"is_active", "is_completed", "is_cancelled", "is_extra", "is_intern", "therapy_started"}
DATETIME_COLUMNS = {"created_at", "updated_at", "started_at", "completed_at", "last_transition_at", "entered_at", "timestamp", "enrollment_date", "record_date", "session_date"}

def fix_value(col, val):
    if val is None:
        return None
    if col in BOOL_COLUMNS:
        return bool(val)
    if col in DATETIME_COLUMNS and isinstance(val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str) and val == 'null':
        return None
    return val

async def main():
    await init_db()

    with open('/app/db_export.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    async with engine.begin() as conn:
        for table in reversed(TABLES_ORDER):
            if table in data:
                await conn.execute(text(f'DELETE FROM "{table}"'))
        logger.info("Cleared existing data.")

        for table in TABLES_ORDER:
            if table not in data:
                continue
            info = data[table]
            rows = info['rows']
            if not rows:
                logger.info(f"  {table}: 0 rows (skip)")
                continue

            columns = info['columns']
            col_list = ', '.join(f'"{c}"' for c in columns)
            param_list = ', '.join(f':{c}' for c in columns)
            sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({param_list})'

            ok = 0
            for row in rows:
                params = {c: fix_value(c, row.get(c)) for c in columns}
                try:
                    await conn.execute(text(sql), params)
                    ok += 1
                except Exception as e:
                    logger.error(f"  Error in {table}: {e}")

            logger.info(f"  {table}: {ok}/{len(rows)} rows imported")

    logger.info("Import complete!")

asyncio.run(main())
