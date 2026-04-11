#!/usr/bin/env python3
"""
بعد از دیپلوی: بازیابی pg_dump (فرمت custom -Fc) روی Postgres سرور.

پیش‌نیاز: فایل dump محلی (مثلاً anistito_local.dump از docker exec pg_dump).

متغیرهای محیطی:
  ANISTITO_SSH_PASSWORD (الزامی)
  ANISTITO_HOST (پیش‌فرض 80.191.11.129)
  ANISTITO_SSH_PORT (پیش‌فرض 9123)
  ANISTITO_SSH_USER (پیش‌فرض root)
  ANISTITO_LOCAL_DUMP (پیش‌فرض: ریشهٔ ریپو / anistito_local.dump)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    pw = os.environ.get("ANISTITO_SSH_PASSWORD")
    if not pw:
        print("خطا: ANISTITO_SSH_PASSWORD را تنظیم کنید.", file=sys.stderr)
        return 1

    host = os.environ.get("ANISTITO_HOST", "80.191.11.129")
    port = int(os.environ.get("ANISTITO_SSH_PORT", "9123"))
    user = os.environ.get("ANISTITO_SSH_USER", "root")
    dump_path = Path(os.environ.get("ANISTITO_LOCAL_DUMP", str(REPO / "anistito_local.dump")))

    if not dump_path.is_file():
        print(f"خطا: فایل dump یافت نشد: {dump_path}", file=sys.stderr)
        return 1

    data = dump_path.read_bytes()
    print(f"=== dump: {dump_path} ({len(data) // 1024} KB) ===")

    import paramiko  # noqa: PLC0415

    remote_dump = "/tmp/anistito_restore.dump"
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username=user, password=pw, timeout=120)
    sftp = c.open_sftp()
    with sftp.file(remote_dump, "wb") as f:
        f.write(data)
    sftp.close()
    print(f"=== uploaded -> {host}:{remote_dump} ===")

    script = r"""
set -e
REMOTE_DUMP="/tmp/anistito_restore.dump"
echo "=== stop API (قطع اتصال به DB) ==="
docker stop anistito-api 2>/dev/null || true

echo "=== copy dump into postgres container ==="
docker cp "$REMOTE_DUMP" anistito-db:/tmp/restore.dump

echo "=== recreate database anistito ==="
docker exec anistito-db psql -U anistito -d postgres -v ON_ERROR_STOP=1 -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'anistito' AND pid <> pg_backend_pid();" \
  || true
docker exec anistito-db psql -U anistito -d postgres -v ON_ERROR_STOP=1 -c \
  "DROP DATABASE IF EXISTS anistito WITH (FORCE);"
docker exec anistito-db psql -U anistito -d postgres -v ON_ERROR_STOP=1 -c \
  "CREATE DATABASE anistito OWNER anistito;"

echo "=== pg_restore ==="
set +e
docker exec anistito-db pg_restore -U anistito -d anistito --no-owner --no-acl --verbose /tmp/restore.dump
rv=$?
set -e
if [ "$rv" != "0" ]; then echo "pg_restore exit=$rv (اگر فقط warning بود معمولاً مشکلی نیست)"; fi

rm -f "$REMOTE_DUMP"
docker exec anistito-db rm -f /tmp/restore.dump

echo "=== start API ==="
docker start anistito-api

sleep 6
h=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 http://127.0.0.1:3000/health 2>/dev/null || echo 000)
echo "health_http_code=${h}"
"""
    _, stdout, stderr = c.exec_command(script, timeout=600)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace")
    print(out)
    c.close()
    print("=== پایان restore DB ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
