# دستورات ری‌بیلد و تست روی سرور اینترنتی

## ۱. ری‌بیلد (اجرا روی ویندوز محلی)

```powershell
cd C:\Users\Administrator\Desktop\anistito

# بیلد فرانت
cd admin-ui; npm run build; cd ..

# آپلود به سرور (رمز را وارد کنید)
scp -r -P 2022 app admin-ui metadata alembic scripts requirements.txt Dockerfile docker-compose.yml deploy-server.sh root@80.191.11.129:/opt/anistito/

# اتصال و ری‌بیلد روی سرور
ssh -p 2022 root@80.191.11.129
```

## ۲. روی سرور (بعد از ssh)

```bash
cd /opt/anistito

# ری‌بیلد و اجرا
docker rm -f anistito-api 2>/dev/null || true
docker build -t anistito-api .
docker run -d --name anistito-api --network anistito-net \
  -p 3000:3000 \
  -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito \
  -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito \
  -e REDIS_URL=redis://anistito-redis:6379/0 \
  -e DEBUG=false \
  -e SECRET_KEY=anistito-prod-secret \
  anistito-api:latest sh -c "python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000"

# تست تعداد فرایندها
sleep 12
curl -s http://localhost:3000/debug/process-count
```

خروجی باید `{"process_count": 7}` یا عددی مشابه باشد.

## ۳. اگر process_count صفر بود – انتقال داده

### روی ویندوز (خروجی از PostgreSQL محلی — همان `DATABASE_URL`):

```powershell
cd C:\Users\Administrator\Desktop\anistito
python scripts/export_from_pg.py
# خروجی: anistito_export.json
```

### آپلود فایل export به سرور:

```powershell
scp -P 2022 anistito_export.json root@80.191.11.129:/tmp/
```

### روی سرور (وارد کردن در PostgreSQL):

```bash
docker run --rm --network anistito-net -v /opt/anistito:/app -v /tmp:/tmp -w /app \
  -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito \
  python:3.12-slim sh -c "pip install sqlalchemy asyncpg -q && python scripts/truncate_and_import.py /tmp/anistito_export.json"
```

### ری‌استارت API (برای اطمینان):

```bash
docker restart anistito-api
sleep 5
curl -s http://localhost:3000/debug/process-count
```
