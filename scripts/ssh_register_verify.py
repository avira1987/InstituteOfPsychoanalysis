"""تست لایو ثبت‌نام عمومی روی هاست + خواندن لاگ‌های جدید."""
from __future__ import annotations

import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = "80.191.11.129"
PORT = 9123

REMOTE_CMD = r"""
set -e
echo "=== ensure API healthy ==="
for i in 1 2 3 4 5 6 7 8 9 10; do
  code="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/health || true)"
  if [ "$code" = "200" ]; then echo "ok ($i)"; break; fi
  sleep 2
done

# تولید کد ملی معتبر تصادفی (با check digit صحیح) و موبایل تصادفی
{ python3 <<'PY'
import random
def gen_nc():
    while True:
        d = [random.randint(0,9) for _ in range(9)]
        s = sum(d[i]*(10-i) for i in range(9))
        r = s % 11
        cd = r if r < 2 else 11 - r
        nc = ''.join(map(str, d)) + str(cd)
        if len(set(nc)) > 1:
            return nc
print("NC=" + gen_nc())
print("PH=09" + ''.join(str(random.randint(0,9)) for _ in range(9)))
PY
} > /tmp/reg_vars.txt
. /tmp/reg_vars.txt

echo ""
echo "=== POST /api/public/register (NC=$NC PH=$PH) ==="
curl -sS -o /tmp/reg_resp.json -w "HTTP %{http_code}\n" \
  -X POST -H "Content-Type: application/json" \
  -d "{\"full_name_fa\":\"تست تشخیصی پس از فیکس\",\"phone\":\"$PH\",\"national_code\":\"$NC\",\"course_type\":\"introductory\"}" \
  http://127.0.0.1:3000/api/public/register || true
echo "--- response ---"
cat /tmp/reg_resp.json 2>/dev/null || true
echo ""
echo ""
echo "=== last 200 lines filtered for register/Traceback/IntegrityError/student_code ==="
docker logs --tail 1500 anistito-api 2>&1 | grep -iE "register|public_routes|Traceback|IntegrityError|student_code|UniqueViolation|collision" | tail -150 || true
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
