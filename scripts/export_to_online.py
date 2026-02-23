#!/usr/bin/env python3
"""Export local SQLite data to JSON for import into online PostgreSQL."""

import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

# Tables in dependency order (parents before children)
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


def serialize_value(val):
    """Convert SQLite values to JSON-serializable format."""
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, bytes):
        return val.hex()
    if hasattr(val, "isoformat"):  # datetime, date
        return val.isoformat()
    return str(val)


def export_db(db_path: str, output_path: str) -> dict:
    """Export SQLite database to JSON file."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    result = {"exported_at": datetime.utcnow().isoformat(), "tables": {}}

    for table in TABLES:
        try:
            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            data = []
            for row in rows:
                d = {}
                for key in row.keys():
                    d[key] = serialize_value(row[key])
                data.append(d)
            result["tables"][table] = data
            print(f"  {table}: {len(data)} rows")
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                result["tables"][table] = []
                print(f"  {table}: (skipped - not exists)")
            else:
                raise

    conn.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    db_path = project_root / "anistito.db"
    output_path = project_root / "anistito_export.json"

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        exit(1)

    print(f"Exporting from {db_path} to {output_path}")
    export_db(str(db_path), str(output_path))
    print(f"Done. Output: {output_path}")
