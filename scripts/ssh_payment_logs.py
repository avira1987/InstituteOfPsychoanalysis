"""واکشی لاگ‌های مرتبط با کال‌بک پرداخت از کانتینر API روی هاست."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123

REMOTE_CMD = r"""
set -e
echo "=== /api/payment/callback related logs (last 600 lines, filtered) ==="
docker logs --tail 600 anistito-api 2>&1 | grep -iE "PAYMENT|callback|StateMachineEngine|NameError|Internal Server|Traceback|500" | tail -200 || true
echo ""
echo "=== last 60 lines of api log (raw) ==="
docker logs --tail 60 anistito-api 2>&1 || true
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
    sys.stdout.write(stdout.read().decode(errors="replace"))
    sys.stderr.write(stderr.read().decode(errors="replace"))
    return stdout.channel.recv_exit_status()


if __name__ == "__main__":
    raise SystemExit(main())
