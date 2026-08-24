#!/usr/bin/env python3
"""
گرفتن کل دیتابیس هاست اینترنتی (کاربران و بقیهٔ داده‌ها) و وارد کردن آن روی
Postgres لوکال (کانتینر anistito-db).

مسیر معکوس اسکریپت restore_remote_db_from_dump.py است:
  هاست --pg_dump--> /tmp روی سرور --sftp--> لوکال --pg_restore--> anistito-db لوکال

متغیرهای محیطی:
  ANISTITO_SSH_PASSWORD یا DEPLOY_SSH_PASSWORD (اگر نبود از .env ریشه خوانده می‌شود)
  ANISTITO_HOST       (پیش‌فرض 80.191.11.129)
  ANISTITO_SSH_PORT   (پیش‌فرض 9123)
  ANISTITO_SSH_USER   (پیش‌فرض root)
  ANISTITO_LOCAL_DB_CONTAINER (پیش‌فرض anistito-db)
  ANISTITO_LOCAL_API_CONTAINER (پیش‌فرض anistito-api)

سوییچ‌ها:
  --dump-only     فقط دانلود dump از هاست (بدون تغییر دیتابیس لوکال)
  --skip-download استفاده از فایل dump موجود
  --no-backup     بدون بکاپ گرفتن از دیتابیس لوکال قبل از بازنویسی
  --yes           بدون پرسش تأیید
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DB_NAME = "anistito"
DB_USER = "anistito"
REMOTE_DB_CONTAINER = "anistito-db"
REMOTE_DUMP_PATH = "/tmp/anistito_host_pull.dump"


def _read_env_file() -> dict[str, str]:
    env_path = REPO / ".env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _ssh_password() -> str:
    env_file = _read_env_file()
    pw = (
        os.environ.get("ANISTITO_SSH_PASSWORD")
        or os.environ.get("DEPLOY_SSH_PASSWORD")
        or env_file.get("DEPLOY_SSH_PASSWORD")
        or env_file.get("ANISTITO_SSH_PASSWORD")
    )
    if not pw:
        raise SystemExit("رمز SSH پیدا نشد: ANISTITO_SSH_PASSWORD یا DEPLOY_SSH_PASSWORD را تنظیم کنید.")
    return pw


def _host_settings() -> tuple[str, int, str]:
    env_file = _read_env_file()
    host = os.environ.get("ANISTITO_HOST") or env_file.get("DEPLOY_REFERENCE_HOST", "80.191.11.129")
    port = int(os.environ.get("ANISTITO_SSH_PORT") or env_file.get("DEPLOY_REFERENCE_PORT", "9123"))
    user = os.environ.get("ANISTITO_SSH_USER") or env_file.get("DEPLOY_REFERENCE_USER", "root")
    return host, port, user


def local_docker(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if check and proc.returncode != 0:
        raise SystemExit(f"docker {' '.join(args)} شکست خورد:\n{proc.stdout}\n{proc.stderr}")
    return proc


def psql_local(container: str, sql: str, db: str = DB_NAME, check: bool = True) -> str:
    proc = local_docker(
        ["exec", container, "psql", "-U", DB_USER, "-d", db, "-t", "-A", "-c", sql], check=check
    )
    return proc.stdout.strip()


def remote_exec(client, script: str, timeout: int = 1800) -> tuple[str, int]:
    _, stdout, stderr = client.exec_command(script, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return (out + err).strip(), code


def dump_from_host(dump_path: Path) -> None:
    import paramiko  # noqa: PLC0415

    host, port, user = _host_settings()
    pw = _ssh_password()

    print(f"=== اتصال به هاست {user}@{host}:{port} ===")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=port, username=user, password=pw, timeout=120)

    try:
        counts, _ = remote_exec(
            client,
            f"docker exec {REMOTE_DB_CONTAINER} psql -U {DB_USER} -d {DB_NAME} -t -A -F'|' "
            "-c \"SELECT relname, n_live_tup FROM pg_stat_user_tables "
            "WHERE n_live_tup > 0 ORDER BY n_live_tup DESC LIMIT 15\"",
        )
        print("=== پرترافیک‌ترین جدول‌های هاست ===")
        print(counts)

        script = f"""
set -e
rm -f {REMOTE_DUMP_PATH}
docker exec {REMOTE_DB_CONTAINER} sh -c \
  'pg_dump -U {DB_USER} -d {DB_NAME} -Fc --no-owner --no-acl -f /tmp/pull.dump'
docker cp {REMOTE_DB_CONTAINER}:/tmp/pull.dump {REMOTE_DUMP_PATH}
docker exec {REMOTE_DB_CONTAINER} rm -f /tmp/pull.dump
ls -l {REMOTE_DUMP_PATH}
"""
        out, code = remote_exec(client, script)
        print(out)
        if code != 0:
            raise SystemExit(f"pg_dump روی هاست شکست خورد (exit={code})")

        print("=== دانلود dump ===")
        sftp = client.open_sftp()
        try:
            size = sftp.stat(REMOTE_DUMP_PATH).st_size or 0
            sftp.get(REMOTE_DUMP_PATH, str(dump_path))
        finally:
            sftp.close()
        remote_exec(client, f"rm -f {REMOTE_DUMP_PATH}")
        print(f"دانلود شد: {dump_path} ({dump_path.stat().st_size // 1024} KB از {size // 1024} KB)")
    finally:
        client.close()


def backup_local(container: str, backup_path: Path) -> None:
    print(f"=== بکاپ دیتابیس لوکال -> {backup_path.name} ===")
    local_docker(
        [
            "exec", container, "sh", "-c",
            f"pg_dump -U {DB_USER} -d {DB_NAME} -Fc --no-owner --no-acl -f /tmp/local_backup.dump",
        ]
    )
    local_docker(["cp", f"{container}:/tmp/local_backup.dump", str(backup_path)])
    local_docker(["exec", container, "rm", "-f", "/tmp/local_backup.dump"], check=False)
    print(f"بکاپ لوکال: {backup_path} ({backup_path.stat().st_size // 1024} KB)")


def restore_local(container: str, api_container: str, dump_path: Path) -> None:
    print("=== توقف API لوکال ===")
    local_docker(["stop", api_container], check=False)

    print("=== انتقال dump به کانتینر دیتابیس ===")
    local_docker(["cp", str(dump_path), f"{container}:/tmp/restore.dump"])

    print("=== ساخت دوبارهٔ دیتابیس anistito ===")
    psql_local(
        container,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{DB_NAME}' AND pid <> pg_backend_pid();",
        db="postgres",
        check=False,
    )
    psql_local(container, f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE);", db="postgres")
    psql_local(container, f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};", db="postgres")

    print("=== pg_restore ===")
    proc = local_docker(
        [
            "exec", container, "pg_restore", "-U", DB_USER, "-d", DB_NAME,
            "--no-owner", "--no-acl", "/tmp/restore.dump",
        ],
        check=False,
    )
    if proc.returncode != 0:
        print(f"pg_restore exit={proc.returncode} (اگر فقط warning باشد معمولاً مشکلی نیست)")
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        print("\n".join(tail[-25:]))
    local_docker(["exec", container, "rm", "-f", "/tmp/restore.dump"], check=False)

    print("=== راه‌اندازی دوبارهٔ API لوکال ===")
    local_docker(["start", api_container], check=False)


def report(container: str) -> None:
    print("\n=== وضعیت دیتابیس لوکال بعد از import ===")
    rows = psql_local(
        container,
        "SELECT relname || ': ' || n_live_tup FROM pg_stat_user_tables "
        "WHERE n_live_tup > 0 ORDER BY n_live_tup DESC LIMIT 20;",
    )
    print(rows)
    version = psql_local(container, "SELECT version_num FROM alembic_version;", check=False)
    print(f"alembic_version: {version or '(نامشخص)'}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="انتقال دیتابیس هاست اینترنتی به لوکال")
    parser.add_argument("--dump-only", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dump-file", default=str(REPO / "anistito_host.dump"))
    args = parser.parse_args()

    container = os.environ.get("ANISTITO_LOCAL_DB_CONTAINER", "anistito-db")
    api_container = os.environ.get("ANISTITO_LOCAL_API_CONTAINER", "anistito-api")
    dump_path = Path(args.dump_file)

    if not args.skip_download:
        dump_from_host(dump_path)
    if not dump_path.is_file():
        raise SystemExit(f"فایل dump یافت نشد: {dump_path}")
    if args.dump_only:
        print("--dump-only: دیتابیس لوکال تغییری نکرد.")
        return 0

    before_users = psql_local(container, "SELECT count(*) FROM users;", check=False)
    print(f"\nکاربران فعلی لوکال: {before_users or '?'}")
    if not args.yes:
        answer = input("دیتابیس لوکال با دادهٔ هاست بازنویسی می‌شود. ادامه؟ [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("لغو شد.")
            return 1

    if not args.no_backup:
        backups = REPO / "backups"
        backups.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_local(container, backups / f"anistito_local_pre_pull_{stamp}.dump")

    restore_local(container, api_container, dump_path)
    report(container)
    print("\n=== پایان: دادهٔ هاست روی لوکال وارد شد ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
