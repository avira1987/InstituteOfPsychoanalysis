# پشتیبان‌گیری و بازیابی PostgreSQL + فایل‌های uploads

## پشتیبان‌گیری روزانه (cron — ساعت ۰۴:۰۰)

اسکریپت اصلی: [`scripts/backup_daily.sh`](../scripts/backup_daily.sh)

هر اجرا یک پوشهٔ تاریخ‌دار می‌سازد:

```text
/var/backups/anistito/YYYY-MM-DD/
  db.dump
  uploads.tar.gz
  manifest.json   # اندازه + sha256 + وضعیت
```

نگهداری پیش‌فرض: **۱۴ روز** (با `RETAIN_DAYS` قابل تنظیم).

### نصب روی هاست

```bash
sudo mkdir -p /var/backups/anistito
sudo chmod 755 /var/backups/anistito

# کپی/لینک اسکریپت کنار دیپلوی (مثال مسیر پروژه روی سرور)
# /opt/anistito/scripts/backup_daily.sh باید executable باشد
chmod +x /opt/anistito/scripts/backup_daily.sh

# یک‌بار تست دستی
sudo BACKUP_ROOT=/var/backups/anistito /opt/anistito/scripts/backup_daily.sh

# cron روزانه ساعت ۴ صبح (زمان محلی هاست)
sudo crontab -e
# این خط را اضافه کنید:
# 0 4 * * * /opt/anistito/scripts/backup_daily.sh >> /var/log/anistito-backup.log 2>&1
```

در `docker-compose.prod.yml` پوشهٔ هاست به‌صورت فقط‌خواندنی به API مانت می‌شود:

- هاست: `HOST_BACKUP_DIR` (پیش‌فرض `/var/backups/anistito`)
- داخل کانتینر: `BACKUP_DIR=/backups`

پس از تغییر compose یک‌بار `docker compose -f docker-compose.prod.yml up -d` لازم است تا mount فعال شود.

پنل ادمین: **بکاپ‌ها** (`/panel/backups`) — فهرست تاریخ‌ها، اعتبارسنجی sha256، دانلود.  
**بازگردانی خودکار روی دیتابیس زنده از UI انجام نمی‌شود.**

## بازیابی یک تاریخ خاص روی محیط تست

اسکریپت: [`scripts/restore_snapshot.sh`](../scripts/restore_snapshot.sh)

```bash
chmod +x scripts/restore_snapshot.sh
# پیش‌فرض: TARGET_DB=anistito_test — از نام دیتابیس production امتناع می‌کند
./scripts/restore_snapshot.sh 2026-08-10

# استخراج uploads در پوشهٔ موقت (volume زنده دست‌نخورده می‌ماند)
RESTORE_UPLOADS=1 ./scripts/restore_snapshot.sh 2026-08-10
```

معادل دستی:

```bash
docker exec -i anistito-db pg_restore -U anistito -d anistito_test --clean --if-exists \
  < /var/backups/anistito/2026-08-10/db.dump
```

اسکریپت قدیمی‌تر: `scripts/restore_remote_db_from_dump.py`

## چک‌لیست پس از بازیابی

1. `alembic current` باید با نسخهٔ مورد انتظار هم‌خوان باشد.
2. `GET /health/ready` باید `db: true` برگرداند.
3. نمونهٔ دانشجو: ورود OTP، یک فرایند فعال، یک `payment_pending` (در صورت وجود).
4. پوشهٔ `uploads/` را همراه DB بازیابی کنید (volume `uploads_data` یا خروجی `RESTORE_UPLOADS=1`).

## RPO / RTO پیشنهادی

| معیار | هدف |
|-------|-----|
| RPO (حداکثر از دست رفتن داده) | ۲۴ ساعت (پشتیبان روزانه ساعت ۰۴:۰۰) |
| RTO (زمان بازیابی سرویس) | ۲–۴ ساعت |
