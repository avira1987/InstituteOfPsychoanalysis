#!/usr/bin/env python3
"""
One-shot deploy: pg_dump از anistito-db لوکال، tar پروژه (شامل admin-ui/dist)،
آپلود، استخراج در /opt/anistito، pg_restore روی سرور، بیلد API با Dockerfile.prod (بدون pull ایمیج node).

Requires: pip install paramiko، Docker لوکال با کانتینر anistito-db
Environment: DEPLOY_SSH_PASSWORD
"""
from __future__ import annotations

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
    idx = ROOT / "admin-ui" / "dist" / "index.html"
    if idx.is_file():
        return
    print("=== Building admin-ui (npm run build) ===", flush=True)
    subprocess.run(
        "npm run build",
        cwd=str(ROOT / "admin-ui"),
        shell=True,
        check=True,
    )


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

    pw = os.environ.get("DEPLOY_SSH_PASSWORD")
    if not pw:
        print("Set DEPLOY_SSH_PASSWORD", file=sys.stderr)
        return 1

    ensure_admin_ui_dist()

    print("=== pg_dump from local anistito-db ===", flush=True)
    dump_path = run_pg_dump_local()
    print(f"  {dump_path} ({dump_path.stat().st_size // 1024} KB)", flush=True)

    print("=== Building tar (excludes .git, node_modules, .env — includes admin-ui/dist) ===", flush=True)
    tar_path = make_tar()
    print(f"  {tar_path} ({tar_path.stat().st_size // 1024} KB)", flush=True)

    print("=== Uploading archive + database dump ===", flush=True)
    sftp_put(tar_path, REMOTE_TAR, pw)
    sftp_put(dump_path, REMOTE_DUMP, pw)

    remote_script = r"""
set -e
cd /opt/anistito
echo "=== Extracting (server .env unchanged if not in archive) ==="
tar -xzf /tmp/anistito_sync.tgz

echo "=== Stopping API ==="
docker stop anistito-api 2>/dev/null || true

echo "=== Restore database from pg_dump (full replace) ==="
docker cp /tmp/anistito_local.dump anistito-db:/tmp/restore.dump
set +e
docker exec anistito-db pg_restore -U anistito -d anistito --clean --if-exists --no-owner --no-acl /tmp/restore.dump 2>&1
RV=$?
set -e
if [ "$RV" -gt 1 ]; then echo "pg_restore failed: $RV"; exit "$RV"; fi

echo "=== Rebuild and start API (Dockerfile.prod — no Node image pull) ==="
docker compose -f docker-compose.prod.yml build --pull=false api
docker compose -f docker-compose.prod.yml up -d api

echo "=== Health ==="
sleep 10
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:3000/health || true
docker ps --filter name=anistito-api --format "{{.Status}}"
echo "Done."
"""
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
