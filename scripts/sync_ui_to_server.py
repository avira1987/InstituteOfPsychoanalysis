#!/usr/bin/env python3
"""Hot-sync admin-ui/dist to production and restart API (no full docker rebuild)."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123


def _pw() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("DEPLOY_SSH_PASSWORD="):
            return s.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("DEPLOY_SSH_PASSWORD missing in .env")


REMOTE_CMD = r"""
set -e
cd /opt/anistito
echo "=== dist on disk ==="
grep -o 'index-[^"]*\.js' admin-ui/dist/index.html || true
echo "=== sync dist -> container ==="
docker cp ./admin-ui/dist/. anistito-api:/app/admin-ui/dist/
docker cp ./app/. anistito-api:/app/app/ 2>/dev/null || true
docker start anistito-api 2>/dev/null || docker restart anistito-api
sleep 8
echo "=== health ==="
curl -s http://127.0.0.1:3000/health || true
echo ""
echo "=== served bundle ==="
curl -s http://127.0.0.1:3000/ | grep -o 'index-[^"]*\.js' || true
"""


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username="root", password=_pw(), timeout=120)
    _, stdout, stderr = c.exec_command(REMOTE_CMD.strip(), timeout=180)
    sys.stdout.write(stdout.read().decode(errors="replace"))
    sys.stderr.write(stderr.read().decode(errors="replace"))
    code = stdout.channel.recv_exit_status()
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
