import sqlite3, json, os

db_path = os.path.join(os.path.dirname(__file__), 'anistito.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version'").fetchall()]
print(f"Tables found: {tables}")

export = {}
for table in tables:
    rows = c.execute(f"SELECT * FROM {table}").fetchall()
    cols = [d[0] for d in c.description]
    export[table] = {"columns": cols, "rows": [dict(r) for r in rows]}
    print(f"  {table}: {len(rows)} rows")

with open(os.path.join(os.path.dirname(__file__), 'db_export.json'), 'w', encoding='utf-8') as f:
    json.dump(export, f, ensure_ascii=False, default=str, indent=2)

print("Exported to db_export.json")
conn.close()
