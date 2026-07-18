#!/usr/bin/env python3
"""
One-shot deploy: tar پروژه (شامل admin-ui/dist)، آپلود، استخراج در /opt/anistito،
بیلد API با Dockerfile.prod (بدون pull ایمیج node).

حالت پیش‌فرض (--replace-db لوکال): pg_dump از anistito-db لوکال، pg_restore کامل روی سرور.

حالت حفظ دیتابیس سرور (--preserve-remote-db یا DEPLOY_PRESERVE_REMOTE_DB=1):
بدون pg_dump/pg_restore؛ دادهٔ تولیدی روی سرور دست‌نخورده می‌ماند. اسکیما با alembic
upgrade head که در command ایمیج API اجرا می‌شود به‌روز می‌شود (برای ستون‌های جدید
در migration نوع nullable یا default تنظیم شود تا ردیف‌های قدیم خطا ندهند).

نکته: فایل .env کنار compose روی سرور فقط نام متغیرهایی با حروف/عدد/_ داشته باشد؛
کلیدهایی مثل VAR(NAME)= ارزش خطای compose می‌دهند. انتهای خط باید Unix LF باشد
(اگر CRLF مانده، قبل از compose با sed یا dos2unix اصلاح شود).

Requires: pip install paramiko؛ در حالت replace-db همچنین Docker لوکال با anistito-db
رمز SSH: اول از متغیر محیطی DEPLOY_SSH_PASSWORD، در غیر این صورت از فایل <ریشه>/.env
(کلید DEPLOY_SSH_PASSWORD؛ در صورت نبودن در env ست می‌شود).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123
REMOTE_TAR = "/tmp/anistito_sync.tgz"
REMOTE_DUMP = "/tmp/anistito_local.dump"


def _parse_dotenv_file(path: Path) -> dict[str, str]:
    """Parse minimal KEY=value lines (no python-dotenv dependency)."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def apply_repo_dotenv(repo_root: Path) -> None:
    """Merge <repo>/.env into os.environ without overriding existing vars."""
    for k, v in _parse_dotenv_file(repo_root / ".env").items():
        if k not in os.environ:
            os.environ[k] = v


def _tar_filter(ti: tarfile.TarInfo) -> tarfile.TarInfo | None:
    n = ti.name.replace("\\", "/").lstrip("./")
    parts = n.split("/") if n else []
    if ".git" in parts:
        return None
    if "node_modules" in parts:
        return None
    if "__pycache__" in parts:
        return None
    if parts and parts[-1] == ".env":
        return None
    return ti


def make_tar() -> Path:
    out = Path(tempfile.gettempdir()) / "anistito_sync.tgz"
    with tarfile.open(out, "w:gz", format=tarfile.GNU_FORMAT) as tf:
        tf.add(ROOT, arcname=".", filter=_tar_filter)
    return out


def ensure_admin_ui_dist() -> None:
    """همیشه قبل از دیپلوی dist تازه بساز — وجود index.html قدیمی کافی نیست."""
    print("=== Building admin-ui (docker compose admin-ui-build) ===", flush=True)
    subprocess.run(
        [
            "docker",
            "compose",
            "--profile",
            "admin-ui-build",
            "run",
            "-T",
            "--rm",
            "admin-ui-build",
        ],
        cwd=str(ROOT),
        check=True,
    )
    idx = ROOT / "admin-ui" / "dist" / "index.html"
    if not idx.is_file():
        raise FileNotFoundError(f"admin-ui build failed: {idx} missing")


def run_pg_dump_local() -> Path:
    dump_path = ROOT / "anistito_local.dump"
    subprocess.run(
        [
            "docker",
            "exec",
            "anistito-db",
            "pg_dump",
            "-U",
            "anistito",
            "-Fc",
            "anistito",
            "-f",
            "/tmp/anistito_local.dump",
        ],
        check=True,
    )
    subprocess.run(
        ["docker", "cp", "anistito-db:/tmp/anistito_local.dump", str(dump_path)],
        check=True,
    )
    return dump_path


def sftp_put(local: Path, remote: str, password: str) -> None:
    t = paramiko.Transport((HOST, PORT))
    t.connect(username="root", password=password)
    sftp = paramiko.SFTPClient.from_transport(t)
    sftp.put(str(local), remote)
    sftp.close()
    t.close()


def remote_deploy_script(*, preserve_remote_db: bool) -> str:
    if preserve_remote_db:
        db_block = '''
echo "=== Database: SKIP pg_restore (preserving remote data) ==="
echo "=== Schema migrations: alembic upgrade head runs in API container on start ==="
'''
    else:
        db_block = r'''
echo "=== Restore database from pg_dump (full replace) ==="
docker cp /tmp/anistito_local.dump anistito-db:/tmp/restore.dump
set +e
docker exec anistito-db pg_restore -U anistito -d anistito --clean --if-exists --no-owner --no-acl /tmp/restore.dump 2>&1
RV=$?
set -e
if [ "$RV" -gt 1 ]; then echo "pg_restore failed: $RV"; exit "$RV"; fi
'''
    return rf"""
set -e
cd /opt/anistito
echo "=== Extracting (server .env unchanged if not in archive) ==="
tar -xzf /tmp/anistito_sync.tgz

echo "=== Stopping API ==="
docker stop anistito-api 2>/dev/null || true

{db_block}

echo "=== Rebuild and start API (Dockerfile.prod — no Node image pull) ==="
# اگر POSTGRES_PASSWORD در .env نیست، compose خطا می‌دهد — از مقدار قبلی کانتینر db بازیابی کن
if ! grep -q '^POSTGRES_PASSWORD=' .env 2>/dev/null; then
  echo "POSTGRES_PASSWORD missing in .env — restoring from anistito-db container"
  PG_PW=$(docker exec anistito-db printenv POSTGRES_PASSWORD 2>/dev/null || echo anistito)
  echo "POSTGRES_PASSWORD=${{PG_PW}}" >> .env
fi
docker compose -f docker-compose.prod.yml build --pull=false --no-cache api
docker compose -f docker-compose.prod.yml up -d api

echo "=== UI bundle on server ==="
grep -o 'index-[^"]*\\.js' /opt/anistito/admin-ui/dist/index.html 2>/dev/null || true
curl -s http://127.0.0.1:3000/ | grep -o 'index-[^"]*\\.js' || true

echo "=== Health ==="
sleep 10
curl -s -o /dev/null -w "HTTP %{{http_code}}\n" http://127.0.0.1:3000/health || true
docker ps --filter name=anistito-api --format "{{{{.Status}}}}"
echo "Done."
"""


def ssh_bash(password: str, script: str) -> tuple[int, str, str]:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username="root", password=password, timeout=600)
    stdin, stdout, stderr = c.exec_command("bash -s", get_pty=False)
    stdin.write(script)
    stdin.channel.shutdown_write()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    c.close()
    return code, out, err


def _safe_print(stream, text: str) -> None:
    """Avoid UnicodeEncodeError on Windows consoles when remote output is Persian."""
    if not text:
        return
    try:
        stream.write(text)
    except UnicodeEncodeError:
        stream.buffer.write(text.encode("utf-8", errors="replace"))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Deploy anistito to remote host via SSH.")
    ap.add_argument(
        "--preserve-remote-db",
        action="store_true",
        help="Do not pg_dump/pg_restore; keep server PostgreSQL data; migrations via Alembic on API start.",
    )
    ap.add_argument(
        "--replace-db-from-local",
        action="store_true",
        help="Explicitly replace remote DB from local Docker anistito-db (default unless PRESERVE set).",
    )
    args, _unknown = ap.parse_known_args()

    apply_repo_dotenv(ROOT)

    pw = os.environ.get("DEPLOY_SSH_PASSWORD")
    if not pw:
        print(
            "Set DEPLOY_SSH_PASSWORD in the environment or in .env at repo root.",
            file=sys.stderr,
        )
        return 1

    preserve_env = os.environ.get("DEPLOY_PRESERVE_REMOTE_DB", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    preserve_db = args.preserve_remote_db or preserve_env
    if args.replace_db_from_local and preserve_db:
        print("Conflicting flags: use either --preserve-remote-db or --replace-db-from-local", file=sys.stderr)
        return 2
    if args.replace_db_from_local:
        preserve_db = False

    ensure_admin_ui_dist()

    dump_path: Path | None = None
    if not preserve_db:
        print("=== pg_dump from local anistito-db ===", flush=True)
        dump_path = run_pg_dump_local()
        print(f"  {dump_path} ({dump_path.stat().st_size // 1024} KB)", flush=True)

    print("=== Building tar (excludes .git, node_modules, .env — includes admin-ui/dist) ===", flush=True)
    tar_path = make_tar()
    print(f"  {tar_path} ({tar_path.stat().st_size // 1024} KB)", flush=True)

    if preserve_db:
        print("=== Uploading archive only (remote DB untouched) ===", flush=True)
    else:
        print("=== Uploading archive + database dump ===", flush=True)
    sftp_put(tar_path, REMOTE_TAR, pw)
    if dump_path is not None:
        sftp_put(dump_path, REMOTE_DUMP, pw)

    remote_script = remote_deploy_script(preserve_remote_db=preserve_db)
    print("=== Running remote deploy ===")
    code, out, err = ssh_bash(pw, remote_script)
    _safe_print(sys.stdout, out)
    _safe_print(sys.stderr, err)
    if code != 0:
        print(f"Remote exit code: {code}", file=sys.stderr)
        return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
