# پشتیبان‌گیری و بازیابی PostgreSQL

## پشتیبان‌گیری روزانه (cron)

```bash
# روی میزبان با docker compose prod
docker exec anistito-db pg_dump -U anistito -Fc anistito > /var/backups/anistito-$(date +%Y%m%d).dump
```

نگهداری: حداقل ۷ روز on-site + کپی off-site هفتگی.

## بازیابی در محیط تست

```bash
docker exec -i anistito-db pg_restore -U anistito -d anistito_test --clean --if-exists < backup.dump
```

اسکریپت موجود: `scripts/restore_remote_db_from_dump.py`

## چک‌لیست پس از بازیابی

1. `alembic current` باید با نسخهٔ مورد انتظار هم‌خوان باشد.
2. `GET /health/ready` باید `db: true` برگرداند.
3. نمونهٔ دانشجو: ورود OTP، یک فرایند فعال، یک `payment_pending` (در صورت وجود).
4. پوشهٔ `uploads/` را همراه DB بازیابی کنید (volume `uploads_data`).

## RPO / RTO پیشنهادی

| معیار | هدف |
|-------|-----|
| RPO (حداکثر از دست رفتن داده) | ۲۴ ساعت (پشتیبان روزانه) |
| RTO (زمان بازیابی سرویس) | ۲–۴ ساعت |
