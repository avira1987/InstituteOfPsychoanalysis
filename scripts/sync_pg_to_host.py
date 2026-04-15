#!/usr/bin/env python3
"""
Sync local Docker Postgres (anistito-db) to remote host via pg_dump / pg_restore.

Requires: pip install paramiko
Env: DEPLOY_SSH_PASSWORD
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123
DUMP_LOCAL = ROOT / "anistito_local.dump"
REMOTE_DUMP = "/tmp/anistito_local.dump"


def run_dump() -> None:
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
        ["docker", "cp", "anistito-db:/tmp/anistito_local.dump", str(DUMP_LOCAL)],
        check=True,
    )


def sftp_put(local: Path, remote: str, password: str) -> None:
    t = paramiko.Transport((HOST, PORT))
    t.connect(username="root", password=password)
    sftp = paramiko.SFTPClient.from_transport(t)
    sftp.put(str(local), remote)
    sftp.close()
    t.close()


def ssh_restore(password: str) -> tuple[int, bytes, bytes]:
    script = f"""
set -e
echo "=== Stopping API ==="
docker stop anistito-api 2>/dev/null || true

echo "=== Copy dump into DB container ==="
docker cp {REMOTE_DUMP} anistito-db:/tmp/restore.dump

echo "=== Restore (replace DB content) ==="
set +e
docker exec anistito-db pg_restore -U anistito -d anistito --clean --if-exists --no-owner --no-acl --verbose /tmp/restore.dump 2>&1
RV=$?
set -e
if [ "$RV" -gt 1 ]; then echo "pg_restore failed: $RV"; exit "$RV"; fi

echo "=== Start API ==="
cd /opt/anistito
docker compose -f docker-compose.prod.yml up -d api

sleep 10
curl -s -o /dev/null -w "health HTTP %{{http_code}}\\n" http://127.0.0.1:3000/health || true
docker ps --filter name=anistito-api --format "{{{{.Status}}}}"
echo Done.
"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username="root", password=password, timeout=600)
    stdin, stdout, stderr = c.exec_command("bash -s", get_pty=False)
    stdin.write(script)
    stdin.channel.shutdown_write()
    out = stdout.read()
    err = stderr.read()
    code = stdout.channel.recv_exit_status()
    c.close()
    return code, out, err


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

    print("=== pg_dump from local anistito-db ===")
    run_dump()
    print(f"  {DUMP_LOCAL} ({DUMP_LOCAL.stat().st_size // 1024} KB)")

    print("=== Upload to server ===")
    sftp_put(DUMP_LOCAL, REMOTE_DUMP, pw)

    print("=== pg_restore on server ===")
    code, out, err = ssh_restore(pw)
    sys.stdout.buffer.write(out)
    sys.stderr.buffer.write(err)
    return 0 if code == 0 else code


if __name__ == "__main__":
    raise SystemExit(main())
