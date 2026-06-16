"""Compare key table row counts on remote after pg_restore."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123

REMOTE_CMD = r"""
echo "=== remote row counts ==="
docker exec anistito-db psql -U anistito -d anistito -t -c "
SELECT 'users' AS t, count(*) FROM users
UNION ALL SELECT 'students', count(*) FROM students
UNION ALL SELECT 'process_instances', count(*) FROM process_instances;
"
echo ""
echo "=== health ==="
curl -sS -w "\nHTTP %{http_code}\n" http://127.0.0.1:3000/health
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
    out = stdout.read().decode("utf-8", errors="replace")
    sys.stdout.write(out)
    return stdout.channel.recv_exit_status()


if __name__ == "__main__":
    raise SystemExit(main())
