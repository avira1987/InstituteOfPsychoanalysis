"""Upload jdatetime wheel via SFTP, pip install from file into API image, restart."""
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
WHEEL = ROOT / "docker" / "wheels" / "jdatetime-5.2.0-py3-none-any.whl"

pw = os.environ.get("REMOTESSH_PASSWORD")
if not pw:
    print("REMOTESSH_PASSWORD", file=sys.stderr)
    sys.exit(1)
if not WHEEL.is_file():
    print("missing", WHEEL, file=sys.stderr)
    sys.exit(1)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("80.191.11.129", 9123, "root", password=pw, timeout=30, allow_agent=False, look_for_keys=False)

sftp = c.open_sftp()
try:
    try:
        sftp.mkdir("/opt/anistito/docker/wheels")
    except IOError:
        pass
    remote = "/opt/anistito/docker/wheels/jdatetime-5.2.0-py3-none-any.whl"
    sftp.put(str(WHEEL), remote)
finally:
    sftp.close()


def run(cmd: str, timeout: int = 120) -> str:
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode() + e.read().decode()


script = r"""
set -e
cd /opt/anistito
docker compose -f docker-compose.prod.yml stop api || true
sleep 2
IMG_ID=$(docker inspect anistito-api --format '{{.Image}}' 2>/dev/null || docker compose -f docker-compose.prod.yml images -q api)
REF=$(docker inspect anistito-api --format '{{.Config.Image}}' 2>/dev/null || echo "")
echo "IMG_ID=$IMG_ID REF=$REF"
docker rm -f anistito-api-patch 2>/dev/null || true
docker run --name anistito-api-patch \
  -v /opt/anistito/docker/wheels:/wheels:ro \
  "$IMG_ID" \
  pip install --no-cache-dir /wheels/jdatetime-5.2.0-py3-none-any.whl
docker commit anistito-api-patch anistito-api-with-jd:latest
docker rm -f anistito-api-patch
if [ -n "$REF" ] && [ "$REF" != "<no value>" ]; then
  docker tag anistito-api-with-jd:latest "$REF"
fi
docker compose -f docker-compose.prod.yml up -d --no-build api
sleep 10
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -6
curl -sS -o /dev/null -w 'health:%{http_code}\n' http://127.0.0.1:3000/health || echo curl_fail
docker logs anistito-api --tail 25 2>&1
"""

print(run(script, timeout=180))
c.close()
