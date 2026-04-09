#!/bin/bash
# همگام‌سازی /opt/anistito با کانتینر anistito-api بدون docker build (وقتی pip از طریق پروکسی خطا می‌دهد)
set -euo pipefail
ROOT="${1:-/opt/anistito}"
CT="${2:-anistito-api}"
cd "$ROOT"
docker cp ./app/. "$CT:/app/app/"
docker cp ./admin-ui/dist/. "$CT:/app/admin-ui/dist/"
docker cp ./metadata/. "$CT:/app/metadata/"
docker cp ./alembic/. "$CT:/app/alembic/"
docker exec "$CT" alembic upgrade head
docker restart "$CT"
sleep 6
curl -s -o /dev/null -w "health:%{http_code}\n" http://127.0.0.1:3000/health
echo "OK sync -> $CT"
