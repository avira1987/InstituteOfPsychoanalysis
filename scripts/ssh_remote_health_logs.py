"""Fetch diagnostic output from remote anistito host (SSH password from repo .env)."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123

REMOTE_CMD = r"""
set -e
echo "=== load / memory (quick) ==="
uptime 2>/dev/null || true
free -h 2>/dev/null | head -n 3 || true
echo ""
echo "=== curl localhost:3000/health ==="
curl -sS -w "\nHTTP_CODE:%{http_code}\n" http://127.0.0.1:3000/health || echo "curl failed"
echo ""
echo "=== docker stats (no stream) ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || true
echo ""
echo ""
echo "=== docker ps anistito-* ==="
docker ps -a --filter name=anistito --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || true
echo ""
echo "=== anistito-api logs (last 150 lines) ==="
docker logs --tail 150 anistito-api 2>&1 || true
"""


def _pw() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("DEPLOY_SSH_PASSWORD="):
            return s.split("=", 1)[1].strip().strip("\"'")
    sys.exit("DEPLOY_SSH_PASSWORD missing")


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username="root", password=_pw(), timeout=120)
    stdin, stdout, stderr = c.exec_command(REMOTE_CMD.strip(), get_pty=False)
    stdin.close()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    sys.stdout.write(out)
    sys.stderr.write(err)
    return stdout.channel.recv_exit_status()


if __name__ == "__main__":
    raise SystemExit(main())
