# همگام‌سازی فرایندها با هاست اینترنتی

برای انتقال فرایندها (و قواعد) از لوکال به هاست اینترنتی:

## روش ۱: Export/Import فایل JSON

### مرحله ۱: Export از لوکال

```powershell
cd C:\Users\Administrator\Desktop\anistito

# اطمینان از اتصال به دیتابیس لوکال (Docker)
$env:DATABASE_URL = "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito"
python scripts/export_from_pg.py
```

خروجی: `anistito_export.json`

### مرحله ۲: آپلود به سرور

با WinSCP یا SCP:
```
فایل: anistito_export.json
مقصد: /tmp/anistito_export.json
```

### مرحله ۳: Import روی سرور

با SSH به سرور وصل شوید:

```bash
cd /opt/anistito
./server-import-data.sh
```

یا دستی:
```bash
docker run --rm --network anistito-net -v /opt/anistito:/app -v /tmp:/tmp -w /app \
  -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito \
  python:3.12-slim sh -c "pip install sqlalchemy asyncpg -q && python scripts/truncate_and_import.py /tmp/anistito_export.json"

docker restart anistito-api
```

---

## روش ۲: API Export/Import (در صورت نیاز)

می‌توان endpoint های زیر را به API اضافه کرد:
- `GET /api/admin/export/processes` - دانلود JSON
- `POST /api/admin/import/processes` - آپلود JSON

---

## نکات

- **کاربر admin** در import حفظ می‌شود (truncate users را نمی‌زند)
- **داده‌های عملیاتی** (process_instances, students و...) در truncate پاک می‌شوند
- برای حفظ فقط فرایندها و قواعد، اسکریپت truncate_and_import را می‌توانید با جداول خاصی اجرا کنید
