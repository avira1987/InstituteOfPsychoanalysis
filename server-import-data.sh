#!/bin/bash
# انتقال داده به سرور - اجرا روی سرور
# پیش‌نیاز: فایل /tmp/anistito_export.json روی سرور باشد

set -e
cd /opt/anistito

if [ ! -f /tmp/anistito_export.json ]; then
  echo "Error: /tmp/anistito_export.json not found. Upload it first:"
  echo "  scp -P 2022 anistito_export.json root@80.191.11.129:/tmp/"
  exit 1
fi

echo "=== Importing data ==="
docker run --rm --network anistito-net -v /opt/anistito:/app -v /tmp:/tmp -w /app \
  -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito \
  python:3.12-slim sh -c "pip install sqlalchemy asyncpg -q && python scripts/truncate_and_import.py /tmp/anistito_export.json"

echo "=== Restarting API ==="
docker restart anistito-api
sleep 5

echo "=== Test ==="
curl -s http://localhost:3000/debug/process-count
echo ""
echo "Done."
