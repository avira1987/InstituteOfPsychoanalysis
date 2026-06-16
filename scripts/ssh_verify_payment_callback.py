"""روی سرور: لاگ‌های پرداخت + تست HTTP کال‌بک با همان query stringهای کاربر."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123

REMOTE_CMD = r"""
set -e
echo "=== curl health (sanity) ==="
curl -sS -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:3000/health || true
echo ""
echo "=== curl callback CANCEL (success=0,status=3) ==="
curl -sS -o /dev/null -w "HTTP %{http_code} | redirect=%{redirect_url}\n" \
  "http://127.0.0.1:3000/api/payment/callback?success=0&status=3&trackId=4576267584&orderId=748ac8118b944b80" || true
echo ""
echo "=== curl callback OK (success=1,status=2) ==="
curl -sS -o /dev/null -w "HTTP %{http_code} | redirect=%{redirect_url}\n" \
  "http://127.0.0.1:3000/api/payment/callback?success=1&status=2&trackId=4575645857&orderId=964ae7461a234acc" || true
echo ""
echo "=== last 80 lines of api logs ==="
docker logs --tail 80 anistito-api 2>&1 || true
echo ""
echo "=== any NameError in last 600 lines? ==="
docker logs --tail 600 anistito-api 2>&1 | grep -E "NameError|Internal Server Error" | tail -20 || echo "(none)"
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
