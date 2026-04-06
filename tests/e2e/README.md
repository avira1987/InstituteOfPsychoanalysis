# تست‌های E2E (Playwright)

مرورگر واقعی علیه **uvicorn** روی پورت محلی و **PostgreSQL** (پیش‌فرض: `127.0.0.1:5432/anistito` — همان docker-compose). قبل از تست: `alembic upgrade head` روی همان DB (فیکسچر خودش اجرا می‌کند). متغیر اختیاری: `E2E_DATABASE_URL`.

## پیش‌نیاز

1. **PostgreSQL در حال اجرا** (مثلاً `docker compose up -d db`)
2. **بیلد فرانت**
   ```bash
   cd admin-ui && npm install && npm run build
   ```
3. **پکیج Python**
   ```bash
   pip install -r requirements.txt
   ```
4. **مرورگر**
   - ترجیحاً: `python -m playwright install chromium`
   - اگر CDN در دسترس نبود، با **Google Chrome** یا **Microsoft Edge** نصب‌شده روی ویندوز هم تست‌ها سعی می‌کنند از همان استفاده کنند (`channel=chrome` / `msedge`).

## اجرا

```bash
# فقط E2E
pytest tests/e2e -v -m e2e

# همهٔ تست‌ها به‌جز E2E (سریع‌تر در CI)
pytest -m "not e2e"
```

زمان اجرای هر دور معمولاً ده‌ها ثانیه است (بالا آوردن سرور + Chromium).
