# رفع خطای Service Unavailable (503)

## علت
Apache به بک‌اند (کانتینر FastAPI روی پورت 3000) وصل نمی‌شود. معمولاً یکی از این موارد:

1. **کانتینر Docker متوقف شده** – خطای migration یا crash هنگام استارت
2. **ProxyPass در Apache تنظیم نشده** – vhost مربوط به bpms.psychoanalysis.ir
3. **شبکه Docker** – کانتینر anistito-db یا anistito-redis در دسترس نیست

---

## مرحله ۱: اتصال به سرور

```bash
ssh -p 2022 root@80.191.11.129
```

---

## مرحله ۲: بررسی وضعیت کانتینر

```bash
docker ps -a --filter name=anistito-api
```

- اگر **Exited** است، لاگ را ببینید:

```bash
docker logs anistito-api --tail 80
```

خطاهای رایج:
- `alembic.util.exc.CommandError` → مشکل migration
- `ModuleNotFoundError` → وابستگی کم
- `Connection refused` به anistito-db → دیتابیس بالا نیست

---

## مرحله ۳: بررسی ProxyPass در Apache

```bash
grep -r "anistito\|ProxyPass" /etc/apache2/sites-enabled/
```

باید چیزی شبیه این باشد:

```apache
ProxyPass /anistito/api/ http://127.0.0.1:3000/api/
ProxyPassReverse /anistito/api/ http://127.0.0.1:3000/api/
ProxyPass /anistito/ http://127.0.0.1:3000/
ProxyPassReverse /anistito/ http://127.0.0.1:3000/
```

اگر نیست، فایل vhost مربوط به `bpms.psychoanalysis.ir` را پیدا کنید و این بلوک را قبل از `</VirtualHost>` اضافه کنید:

```bash
# پیدا کردن فایل vhost
ls -la /etc/apache2/sites-enabled/
cat /etc/apache2/sites-enabled/*-le-ssl.conf | grep -A2 ServerName
```

سپس:

```bash
# اجرای اسکریپت fix (اگر در پروژه هست)
bash /opt/anistito/scripts/fix_apache_anistito.sh

# یا reload دستی
sudo systemctl reload apache2
```

---

## مرحله ۴: راه‌اندازی مجدد کانتینر

```bash
cd /opt/anistito
docker start anistito-api
```

اگر کانتینر وجود ندارد یا start کار نکرد، deploy مجدد:

```bash
cd /opt/anistito
docker rm -f anistito-api 2>/dev/null
docker build -t anistito-api .
docker run -d --name anistito-api --network anistito-net -p 3000:3000 \
  -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito \
  -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito \
  -e REDIS_URL=redis://anistito-redis:6379/0 \
  -e DEBUG=false \
  -e SECRET_KEY=anistito-prod-secret \
  anistito-api:latest sh -c 'python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000'
```

---

## مرحله ۵: تست

```bash
curl -s http://127.0.0.1:3000/health
```

باید `{"status":"healthy"}` برگردد.

---

## Deploy مجدد از ویندوز

اگر migration اصلاح شده و می‌خواهید از اول deploy کنید:

```powershell
cd C:\Users\Administrator\Desktop\anistito
.\deploy-to-host.ps1
```

Migration جدید با `server_default=sa.text('false')` برای PostgreSQL سازگار است.
