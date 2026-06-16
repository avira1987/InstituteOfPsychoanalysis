"""واکشی لاگ‌های مرتبط با /api/public/register از کانتینر API."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123

REMOTE_CMD = r"""
set -e
echo "=== curl /api/public/register (sample valid payload — non-destructive 409 if NC exists) ==="
curl -sS -o /tmp/reg_resp.json -w "HTTP %{http_code}\n" \
  -X POST -H "Content-Type: application/json" \
  -d '{"full_name_fa":"تست تشخیصی","phone":"09120000000","national_code":"0010000000","course_type":"introductory"}' \
  http://127.0.0.1:3000/api/public/register || true
echo "--- response body ---"
cat /tmp/reg_resp.json 2>/dev/null || true
echo ""
echo ""
echo "=== last 250 lines filtered for register/Traceback/500/Error ==="
docker logs --tail 800 anistito-api 2>&1 | grep -iE "register|public_routes|Traceback|NameError|TypeError|AttributeError|IntegrityError|Internal Server Error|500" | tail -200 || true
echo ""
echo "=== last 80 lines raw ==="
docker logs --tail 80 anistito-api 2>&1 || true
"""


def _pw() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("DEPLOY_SSH_PASSWORD="):
            return s.split("=", 1)[1].strip().strip("\"'")
    sys.exit("DEPLOY_SSH_PASSWORD missing")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username="root", password=_pw(), timeout=120)
    stdin, stdout, stderr = c.exec_command(REMOTE_CMD.strip(), get_pty=False)
    stdin.close()
    out_b = stdout.read()
    err_b = stderr.read()
    try:
        sys.stdout.write(out_b.decode("utf-8", errors="replace"))
    except UnicodeEncodeError:
        sys.stdout.buffer.write(out_b)
    try:
        sys.stderr.write(err_b.decode("utf-8", errors="replace"))
    except UnicodeEncodeError:
        sys.stderr.buffer.write(err_b)
    return stdout.channel.recv_exit_status()


if __name__ == "__main__":
    raise SystemExit(main())
