#!/usr/bin/env python3
"""
پاک‌سازی دادهٔ اجرایی بدون دست زدن به ساختار فرایند و کاربران.

می‌ماند:
  - users
  - students (پروفایل؛ بدون نمونهٔ فرایند)
  - process_definitions / state_definitions / transition_definitions / rule_definitions
  - form_templates / form_template_versions / form_assignments / form_dynamic_sources
  - portal_nav_configs / blog_posts / site_settings

پاک می‌شود:
  - process_instances و وابسته‌ها (state_history، form_responses، …)
  - آماده‌سازی ترم (اسلات، دروس ترم، تقویم)
  - پرداخت‌ها و مالی
  - لاگ‌ها و outbox

استفاده:
  python scripts/purge_runtime_keep_users.py --dry-run          # لوکال DATABASE_URL
  python scripts/purge_runtime_keep_users.py --apply
  python scripts/purge_runtime_keep_users.py --host --dry-run   # DB داخل Docker هاست
  python scripts/purge_runtime_keep_users.py --host --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# ترتیب مهم نیست وقتی یک TRUNCATE چندجدولی با CASCADE استفاده شود؛
# لیست برای شمارش و گزارش است.
PURGE_TABLES: tuple[str, ...] = (
    "form_field_files",
    "form_approval_steps",
    "form_responses",
    "assignment_submissions",
    "assignments",
    "state_history",
    "payment_pending",
    "failed_actions",
    "ticket_comments",
    "support_tickets",
    "panel_task_reminders",
    "panel_flash_messages",
    "panel_action_notification_dismissals",
    "sms_simulation_dismissals",
    "sms_simulation_outbox",
    "notification_outbox",
    "payment_gateway_receipts",
    "financial_records",
    "therapy_sessions",
    "attendance_records",
    "interview_slots",
    "interview_slot_recurring_rules",
    "educational_therapist_slots",
    "term_course_offerings",
    "institute_calendars",
    "otp_codes",
    "login_challenges",
    "daily_overdue_run_logs",
    "audit_logs",
    "process_instances",
)

KEEP_TABLES: tuple[str, ...] = (
    "users",
    "students",
    "process_definitions",
    "state_definitions",
    "transition_definitions",
    "rule_definitions",
    "form_templates",
    "form_template_versions",
    "form_assignments",
    "form_dynamic_sources",
    "portal_nav_configs",
    "blog_posts",
    "site_settings",
)


def _parse_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip("\"'")
    return out


def _counts_sql(tables: tuple[str, ...]) -> str:
    parts = [
        f"(SELECT COUNT(*) FROM {t}) AS {t}" if t.replace("_", "").isalnum() else ""
        for t in tables
    ]
    # safer: one query per table in driver; for psql use UNION
    lines = [f"SELECT '{t}' AS tbl, COUNT(*)::bigint AS n FROM {t}" for t in tables]
    return " UNION ALL ".join(lines) + " ORDER BY 1;"


def run_local(apply: bool) -> int:
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    env = _parse_dotenv(ROOT / ".env")
    url = os.environ.get("DATABASE_URL") or env.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL missing", file=sys.stderr)
        return 1
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    async def _go() -> int:
        eng = create_async_engine(url)
        async with eng.connect() as conn:
            keep_before = {}
            purge_before = {}
            for t in KEEP_TABLES:
                try:
                    keep_before[t] = (await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))).scalar()
                except Exception:
                    keep_before[t] = None
            for t in PURGE_TABLES:
                try:
                    purge_before[t] = (await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))).scalar()
                except Exception:
                    purge_before[t] = None

            print("=== KEEP (before) ===")
            for t, n in keep_before.items():
                print(f"  {t}: {n}")
            print("=== PURGE (before) ===")
            total = 0
            for t, n in purge_before.items():
                print(f"  {t}: {n}")
                if isinstance(n, int):
                    total += n
            print(f"  TOTAL rows to clear: {total}")

            if not apply:
                print("Dry-run only. Re-run with --apply to truncate.")
                await conn.rollback()
                await eng.dispose()
                return 0

            existing = [t for t, n in purge_before.items() if n is not None]
            if not existing:
                print("No purge tables found.")
                await eng.dispose()
                return 0
            stmt = "TRUNCATE TABLE " + ", ".join(existing) + " RESTART IDENTITY CASCADE"
            await conn.execute(text(stmt))
            await conn.commit()

            print("=== KEEP (after) ===")
            for t in KEEP_TABLES:
                try:
                    n = (await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))).scalar()
                except Exception:
                    n = None
                before = keep_before.get(t)
                flag = "OK" if n == before else f"CHANGED was {before}"
                print(f"  {t}: {n} [{flag}]")
            print("=== PURGE (after) ===")
            for t in existing:
                n = (await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))).scalar()
                print(f"  {t}: {n}")
        await eng.dispose()
        print("Done (local).")
        return 0

    return asyncio.run(_go())


def run_host(apply: bool) -> int:
    import paramiko

    env = _parse_dotenv(ROOT / ".env")
    pw = (
        os.environ.get("ANISTITO_SSH_PASSWORD")
        or os.environ.get("DEPLOY_SSH_PASSWORD")
        or env.get("DEPLOY_SSH_PASSWORD")
        or env.get("ANISTITO_SSH_PASSWORD")
    )
    if not pw:
        print("Set DEPLOY_SSH_PASSWORD / ANISTITO_SSH_PASSWORD", file=sys.stderr)
        return 1
    host = os.environ.get("ANISTITO_HOST", "80.191.11.129")
    port = int(os.environ.get("ANISTITO_SSH_PORT", "9123"))
    user = os.environ.get("ANISTITO_SSH_USER", "root")

    count_sql = _counts_sql(KEEP_TABLES + PURGE_TABLES)
    # escape for remote single-quoted bash
    count_sql_q = count_sql.replace("'", "'\"'\"'")

    backup_and_count = f"""
set -e
DB=anistito-db
mkdir -p /var/backups/anistito
STAMP=$(date +%Y%m%d_%H%M%S)
DUMP=/var/backups/anistito/pre_purge_runtime_$STAMP.dump
echo "=== backup -> $DUMP ==="
docker exec $DB pg_dump -U anistito -Fc anistito > "$DUMP"
ls -lh "$DUMP"
echo "=== counts ==="
docker exec -i $DB psql -U anistito -d anistito -v ON_ERROR_STOP=1 -c '{count_sql_q}'
"""

    truncate_sql = (
        "TRUNCATE TABLE "
        + ", ".join(PURGE_TABLES)
        + " RESTART IDENTITY CASCADE;"
    )
    truncate_sql_q = truncate_sql.replace("'", "'\"'\"'")

    apply_block = f"""
echo "=== TRUNCATE runtime tables ==="
docker exec -i $DB psql -U anistito -d anistito -v ON_ERROR_STOP=1 -c '{truncate_sql_q}'
echo "=== counts after ==="
docker exec -i $DB psql -U anistito -d anistito -v ON_ERROR_STOP=1 -c '{count_sql_q}'
echo "=== verify process defs still present ==="
docker exec -i $DB psql -U anistito -d anistito -c "SELECT COUNT(*) AS process_definitions FROM process_definitions; SELECT COUNT(*) AS users FROM users; SELECT COUNT(*) AS students FROM students; SELECT COUNT(*) AS process_instances FROM process_instances;"
"""

    remote = backup_and_count + (apply_block if apply else "echo 'Dry-run only (backup taken). Re-run with --apply.'\n")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username=user, password=pw, timeout=60)
    _, stdout, stderr = c.exec_command(remote, timeout=600)
    out = (stdout.read() + stderr.read()).decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    c.close()
    print(out)
    if code != 0:
        print(f"Remote exit {code}", file=sys.stderr)
        return code
    print("Done (host)." if apply else "Dry-run done (host).")
    return 0


def main() -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Purge runtime data; keep users and process definitions")
    ap.add_argument("--dry-run", action="store_true", help="فقط شمارش (پیش‌فرض اگر --apply نباشد)")
    ap.add_argument("--apply", action="store_true", help="اجرای TRUNCATE")
    ap.add_argument("--host", action="store_true", help="روی PostgreSQL کانتینر هاست اینترنتی")
    ap.add_argument("--local", action="store_true", help="روی DATABASE_URL لوکال")
    args = ap.parse_args()
    apply = bool(args.apply)
    if args.host:
        return run_host(apply=apply)
    # default local if not --host
    return run_local(apply=apply)


if __name__ == "__main__":
    raise SystemExit(main())
