#!/usr/bin/env python3
"""
صفر کردن داده‌های ذخیره‌شدهٔ صفحهٔ «اعلان‌ها و پیام‌ها» و صف اعلان/پیامک.

جداول:
  - panel_flash_messages              (پیام‌های پاپ‌آپ)
  - panel_task_reminders              (اعلان‌های ذخیره‌شدهٔ پنل)
  - panel_action_notification_dismissals
  - sms_simulation_outbox
  - sms_simulation_dismissals
  - notification_outbox

توجه: اعلان‌های محاسبه‌شده از کارتابل فرایند پاک نمی‌شوند
(تا وقتی نمونهٔ فرایند باز باشد در فید دیده می‌شوند).

استفاده:
  python scripts/purge_notifications_messages.py --dry-run
  python scripts/purge_notifications_messages.py --apply
  python scripts/purge_notifications_messages.py --host --dry-run
  python scripts/purge_notifications_messages.py --host --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PURGE_TABLES: tuple[str, ...] = (
    "panel_flash_messages",
    "panel_task_reminders",
    "panel_action_notification_dismissals",
    "sms_simulation_outbox",
    "sms_simulation_dismissals",
    "notification_outbox",
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
            before: dict[str, int | None] = {}
            for t in PURGE_TABLES:
                try:
                    before[t] = (await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))).scalar()
                except Exception:
                    before[t] = None

            print("=== BEFORE ===")
            total = 0
            for t, n in before.items():
                print(f"  {t}: {n}")
                if isinstance(n, int):
                    total += n
            print(f"  TOTAL: {total}")

            if not apply:
                print("Dry-run only. Re-run with --apply to truncate.")
                await conn.rollback()
                await eng.dispose()
                return 0

            existing = [t for t, n in before.items() if n is not None]
            if not existing:
                print("No tables found.")
                await eng.dispose()
                return 0
            stmt = "TRUNCATE TABLE " + ", ".join(existing) + " RESTART IDENTITY CASCADE"
            await conn.execute(text(stmt))
            await conn.commit()

            print("=== AFTER ===")
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

    count_sql = _counts_sql(PURGE_TABLES)
    count_sql_q = count_sql.replace("'", "'\"'\"'")

    backup_and_count = f"""
set -e
DB=anistito-db
mkdir -p /var/backups/anistito
STAMP=$(date +%Y%m%d_%H%M%S)
DUMP=/var/backups/anistito/pre_purge_notifications_$STAMP.dump
echo "=== backup -> $DUMP ==="
docker exec $DB pg_dump -U anistito -Fc -t panel_flash_messages -t panel_task_reminders -t panel_action_notification_dismissals -t sms_simulation_outbox -t sms_simulation_dismissals -t notification_outbox anistito > "$DUMP"
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
echo "=== TRUNCATE notification/message tables ==="
docker exec -i $DB psql -U anistito -d anistito -v ON_ERROR_STOP=1 -c '{truncate_sql_q}'
echo "=== counts after ==="
docker exec -i $DB psql -U anistito -d anistito -v ON_ERROR_STOP=1 -c '{count_sql_q}'
"""

    remote = backup_and_count + (
        apply_block if apply else "echo 'Dry-run only (backup taken). Re-run with --apply.'\n"
    )

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

    ap = argparse.ArgumentParser(description="Purge stored notifications and flash messages")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--host", action="store_true")
    ap.add_argument("--local", action="store_true")
    args = ap.parse_args()
    apply = bool(args.apply)
    if args.host:
        return run_host(apply=apply)
    return run_local(apply=apply)


if __name__ == "__main__":
    raise SystemExit(main())
