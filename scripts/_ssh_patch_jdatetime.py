"""Patch running anistito-api image with pip install jdatetime (no full rebuild)."""
import os
import sys
import paramiko

pw = os.environ.get("REMOTESSH_PASSWORD")
if not pw:
    print("REMOTESSH_PASSWORD", file=sys.stderr)
    sys.exit(1)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("80.191.11.129", 9123, "root", password=pw, timeout=30, allow_agent=False, look_for_keys=False)


def run(cmd: str, timeout: int = 300) -> str:
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode() + e.read().decode()


# Stop crash-loop, get image id, run one-off container to pip install, commit to same tag compose uses
script = r"""
set -e
cd /opt/anistito
docker compose -f docker-compose.prod.yml stop api || true
sleep 2
IMG_ID=$(docker inspect anistito-api --format '{{.Image}}' 2>/dev/null || docker compose -f docker-compose.prod.yml images -q api)
REF=$(docker inspect anistito-api --format '{{.Config.Image}}' 2>/dev/null || echo "")
echo "IMAGE_ID=$IMG_ID REF=$REF"
docker rm -f anistito-api-patch 2>/dev/null || true
docker run --name anistito-api-patch "$IMG_ID" sh -c 'pip install --no-cache-dir "jdatetime>=4.1.0"'
docker commit anistito-api-patch anistito-api-with-jd:latest
docker rm -f anistito-api-patch
if [ -n "$REF" ] && [ "$REF" != "<no value>" ]; then
  docker tag anistito-api-with-jd:latest "$REF"
else
  docker tag anistito-api-with-jd:latest anistito-api-with-jd:latest
fi
docker compose -f docker-compose.prod.yml up -d --no-build api
sleep 8
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | head -6
curl -sS -o /dev/null -w 'health:%{http_code}\n' http://127.0.0.1:3000/health || echo curl_fail
ss -tlnp | grep 3000 || echo NO_3000
"""

print(run(script, timeout=400))

c.close()
