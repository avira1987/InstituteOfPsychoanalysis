#!/usr/bin/env python3
"""
همگام‌سازی کاربران اپراتوری لوکال → هاست اینترنتی.

- فقط پرسنل/کمیته/مدرس (نه دانشجویان دمو)
- کاربر جدید: رمز demo123 (hash از لوکال کپی می‌شود)
- کاربر موجود: نقش/نام/فعال‌بودن به‌روز؛ رمز هاست حفظ می‌شود

استفاده:
  python scripts/sync_operator_users_to_host.py --dry-run
  python scripts/sync_operator_users_to_host.py --apply
  python scripts/sync_operator_users_to_host.py --seed-local   # فقط seed لوکال
  python scripts/sync_operator_users_to_host.py --apply --seed-local

نیاز: ANISTITO_SSH_PASSWORD یا DEPLOY_SSH_PASSWORD؛ Docker لوکال anistito-db
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REMOTE_JSON = "/tmp/anistito_operator_users.json"
REMOTE_PY = "/tmp/anistito_upsert_operators.py"


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


def _ssh_creds() -> tuple[str, int, str, str]:
    env = _parse_dotenv(ROOT / ".env")
    pw = (
        os.environ.get("ANISTITO_SSH_PASSWORD")
        or os.environ.get("DEPLOY_SSH_PASSWORD")
        or env.get("DEPLOY_SSH_PASSWORD")
        or env.get("ANISTITO_SSH_PASSWORD")
    )
    if not pw:
        raise SystemExit("Set ANISTITO_SSH_PASSWORD or DEPLOY_SSH_PASSWORD")
    host = os.environ.get("ANISTITO_HOST", env.get("ANISTITO_HOST", "80.191.11.129"))
    port = int(os.environ.get("ANISTITO_SSH_PORT", env.get("ANISTITO_SSH_PORT", "9123")))
    user = os.environ.get("ANISTITO_SSH_USER", env.get("ANISTITO_SSH_USER", "root"))
    return host, port, user, pw


async def _local_session():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    env = _parse_dotenv(ROOT / ".env")
    url = os.environ.get("DATABASE_URL") or env.get("DATABASE_URL")
    if not url:
        url = "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito"
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, factory


async def seed_local() -> None:
    from app.demo_role_users import ensure_demo_role_users

    engine, factory = await _local_session()
    async with factory() as db:
        await ensure_demo_role_users(db)
    await engine.dispose()
    print("Local ensure_demo_role_users done.")


async def export_local_operators() -> list[dict]:
    from app.operator_users_sync import list_operator_payloads, roles_missing_coverage

    engine, factory = await _local_session()
    async with factory() as db:
        payloads = await list_operator_payloads(db)
    await engine.dispose()
    missing = roles_missing_coverage(payloads)
    print(f"Local operators: {len(payloads)}")
    if missing:
        print("WARNING missing role coverage:", ", ".join(missing))
    else:
        print("All operator catalog roles covered (excluding merged aliases).")
    return payloads


def _ssh_exec(cmd: str, timeout: int = 300) -> tuple[int, str]:
    import paramiko

    host, port, user, pw = _ssh_creds()
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username=user, password=pw, timeout=60)
    try:
        _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = (stdout.read() + stderr.read()).decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        return code, out
    finally:
        c.close()


def _sftp_put(local: Path, remote: str) -> None:
    import paramiko

    host, port, user, pw = _ssh_creds()
    t = paramiko.Transport((host, port))
    t.connect(username=user, password=pw)
    sftp = paramiko.SFTPClient.from_transport(t)
    assert sftp is not None
    try:
        sftp.put(str(local), remote)
    finally:
        sftp.close()
        t.close()


def host_usernames() -> set[str]:
    code, out = _ssh_exec(
        "docker exec anistito-db psql -U anistito -d anistito -t -A "
        "-c \"SELECT username FROM users WHERE is_active IS TRUE;\""
    )
    if code != 0:
        raise SystemExit(f"Host query failed ({code}): {out}")
    return {line.strip() for line in out.splitlines() if line.strip()}


_REMOTE_UPSERT_SCRIPT = r'''
import asyncio
import json
import sys

sys.path.insert(0, "/app")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings
from app.operator_users_sync import upsert_operators_from_payloads, roles_missing_coverage

async def main():
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        payloads = json.load(f)
    settings = get_settings()
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        summary = await upsert_operators_from_payloads(
            db, payloads, keep_existing_password=True
        )
    await engine.dispose()
    print("CREATED", len(summary["created"]), ",".join(summary["created"]))
    print("UPDATED", len(summary["updated"]), ",".join(summary["updated"]))
    print("UNCHANGED", len(summary["unchanged"]), ",".join(summary["unchanged"]))
    print("PASSWORD_KEPT", len(summary["skipped_password"]))
    miss = roles_missing_coverage(payloads)
    print("MISSING_COVERAGE", ",".join(miss) if miss else "")

asyncio.run(main())
'''


def apply_to_host(payloads: list[dict]) -> int:
    # backup
    print("=== host backup pg_dump ===")
    code, out = _ssh_exec(
        "set -e; mkdir -p /var/backups/anistito; "
        "STAMP=$(date +%Y%m%d_%H%M%S); "
        "DUMP=/var/backups/anistito/pre_operator_sync_$STAMP.dump; "
        "docker exec anistito-db pg_dump -U anistito -Fc anistito > \"$DUMP\"; "
        "ls -lh \"$DUMP\""
    )
    print(out)
    if code != 0:
        return code

    with tempfile.TemporaryDirectory() as td:
        local_json = Path(td) / "operators.json"
        local_py = Path(td) / "upsert.py"
        # strip nothing — hashed_password only used for creates
        local_json.write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
        local_py.write_text(_REMOTE_UPSERT_SCRIPT, encoding="utf-8")
        print("=== upload payload ===")
        _sftp_put(local_json, REMOTE_JSON)
        _sftp_put(local_py, REMOTE_PY)

    print("=== upsert inside anistito-api ===")
    code, out = _ssh_exec(
        "docker cp /tmp/anistito_operator_users.json anistito-api:/tmp/anistito_operator_users.json && "
        "docker cp /tmp/anistito_upsert_operators.py anistito-api:/tmp/anistito_upsert_operators.py && "
        "docker exec -w /app -e PYTHONPATH=/app anistito-api "
        "python /tmp/anistito_upsert_operators.py /tmp/anistito_operator_users.json"
    )
    print(out)
    return code


def print_diff(payloads: list[dict], remote: set[str]) -> None:
    local_names = {p["username"] for p in payloads}
    only_local = sorted(local_names - remote)
    only_remote_ops = sorted(remote & local_names)  # overlap
    missing_on_host = only_local
    print(f"On host (active usernames sampled overlap): {len(only_remote_ops)} already present")
    print(f"Missing on host (will create): {len(missing_on_host)}")
    for u in missing_on_host:
        print(f"  + {u}")
    already = sorted(local_names & remote)
    print(f"Already on host (roles update, password kept): {len(already)}")
    for u in already[:40]:
        print(f"  ~ {u}")
    if len(already) > 40:
        print(f"  ... +{len(already) - 40} more")


def main() -> int:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Sync local operator users to internet host")
    ap.add_argument("--dry-run", action="store_true", help="Compare only; no host writes")
    ap.add_argument("--apply", action="store_true", help="Backup host DB and upsert operators")
    ap.add_argument("--seed-local", action="store_true", help="Run ensure_demo_role_users locally first")
    args = ap.parse_args()
    if not args.dry_run and not args.apply and not args.seed_local:
        ap.print_help()
        return 1
    if args.apply and args.dry_run:
        print("Use either --dry-run or --apply", file=sys.stderr)
        return 1

    if args.seed_local:
        asyncio.run(seed_local())

    if not args.dry_run and not args.apply:
        return 0

    payloads = asyncio.run(export_local_operators())
    print("=== compare with host ===")
    remote = host_usernames()
    print(f"Host active users: {len(remote)}")
    print_diff(payloads, remote)

    if args.dry_run:
        print("Dry-run only. Re-run with --apply to sync.")
        return 0

    return apply_to_host(payloads)


if __name__ == "__main__":
    raise SystemExit(main())
