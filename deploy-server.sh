#!/bin/bash
# اجرا روی سرور: bash deploy-server.sh
set -e
cd /opt/anistito

echo "=== Stopping old API container ==="
docker rm -f anistito-api 2>/dev/null || true

echo "=== Building Docker image (2-5 min) ==="
docker build -t anistito-api .

echo "=== Starting API container ==="
docker run -d --name anistito-api --network anistito-net \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito \
  -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito \
  -e REDIS_URL=redis://anistito-redis:6379/0 \
  -e DEBUG=false \
  -e SECRET_KEY=anistito-prod-secret \
  anistito-api:latest sh -c "python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo "=== Waiting for API to start ==="
sleep 15
curl -s http://localhost:8000/health && echo " OK" || docker logs anistito-api --tail 20

echo ""
echo "=== دسترسی: http://80.191.11.129:8000 ==="
echo "=== ورود پیش‌فرض: admin / admin123 ==="
