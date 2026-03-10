#!/bin/bash
# اجرا روی سرور: bash server-rebuild.sh
# یا: ssh -p 2022 root@80.191.11.129 'bash -s' < server-rebuild.sh

set -e
cd /opt/anistito

echo "=== Stopping API ==="
docker rm -f anistito-api 2>/dev/null || true

echo "=== Building ==="
docker build -t anistito-api .

echo "=== Starting API ==="
docker run -d --name anistito-api --network anistito-net \
  -p 3000:3000 \
  -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito \
  -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito \
  -e REDIS_URL=redis://anistito-redis:6379/0 \
  -e DEBUG=false \
  -e SECRET_KEY=anistito-prod-secret \
  anistito-api:latest sh -c "python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000"

echo "=== Waiting 12s ==="
sleep 12

echo "=== Test: process count ==="
curl -s http://localhost:3000/debug/process-count
echo ""

echo "=== Done ==="
