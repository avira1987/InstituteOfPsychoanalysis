# چک‌لیست امنیتی استقرار اینترنتی (Anistito)

قبل از باز کردن سایت روی اینترنت، همهٔ موارد زیر را انجام دهید.

## ۱) فایل `.env` روی سرور

- `DEBUG=false`
- `SECRET_KEY=` مقدار تصادفی قوی (≥ ۳۲ کاراکتر؛ مثلاً `python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `INITIAL_ADMIN_PASSWORD=` رمز قوی یک‌بارمصرف برای ساخت ادمین (اگر هنوز ساخته نشده)
- `POSTGRES_PASSWORD=` رمز قوی و یکتا
- `SMS_PROVIDER=mellipayamak` + `SMS_USERNAME` / `SMS_PASSWORD` یا `SMS_API_KEY` + `SMS_LINE_NUMBER`
- `PAYMENT_PROVIDER=` واقعی (`zibal` / `saman` / `zarinpal`) و کلیدهای درگاه
- `PAYMENT_TEST_BYPASS=false`
- `OTP_SHOW_CODE_IN_UI=false`
- ثبت‌نام عمومی از صفحهٔ ورود باز است: `ALLOW_PUBLIC_OTP_SIGNUP=true` (شمارهٔ جدید → OTP → فرم ثبت‌نام). برای بستن: `ALLOW_PUBLIC_OTP_SIGNUP=false` و `OTP_RESTRICT_TO_STUDENT_PHONES=true`
- `SEED_DEMO_ON_STARTUP=false`
- `ALLOW_DEMO_SEED=false`
- `FLOW_THROUGH_SEED_ENABLED=false`
- `SMS_SIMULATION_UI=false`
- `CORS_ALLOW_ORIGINS=` فقط `https://...` (بدون `http://`)
- `APP_BASE_URL=` و `PAYMENT_CALLBACK_URL=` با HTTPS

## ۲) شبکه و TLS

- فقط از `docker-compose.prod.yml` استفاده کنید (نه `docker-compose.yml` توسعه).
- Postgres روی اینترنت publish نشود (در compose تولید فقط `expose` داخلی است).
- API فقط روی `127.0.0.1:3000` bind شده؛ reverse proxy (Apache/Nginx) روی همان میزبان.
- TLS در لبه فعال باشد؛ HSTS و هدرهای امنیتی را با `scripts/apply_apache_security_headers.sh` اعمال و با `curl -I` تأیید کنید.
- فایروال: فقط ۸۰/۴۴۳ عمومی؛ پورت‌های ۳۰۰۰ و ۵۴۳۲/۵۴۳۳ از اینترنت بسته.

## ۳) بلافاصله پس از اولین بوت

1. با ادمین وارد شوید و رمز را عوض کنید.
2. حساب‌های دمو (`demo123` / کاربران seed) را غیرفعال یا حذف کنید.
3. مطمئن شوید `/docs` و `/openapi.json` در پاسخ ۴۰۴ هستند.
4. لاگ استارت پیام `Production configuration guards passed` را نشان دهد.

## ۴) چرخش اسرار

- کلیدهای SMS، درگاه پرداخت، Alocom و `SECRET_KEY` را اگر قبلاً در لاگ/اسکریپت/مخزن لو رفته‌اند عوض کنید.
- اسکریپت‌های probe با رمز hardcode را روی سرور اجرا نکنید و رمزهای مشکوک را rotate کنید.

## ۵) بکاپ

- مسیر بکاپ روزانه (`HOST_BACKUP_DIR`) فقط‌خواندنی برای کانتینر باشد.
- بکاپ‌ها را خارج از سرور نگه دارید و رمزنگاری کنید.

## ۶) تأیید سریع پس از go-live

```bash
curl -sI https://YOUR_DOMAIN/anistito/ | tr -d '\r' | grep -iE 'strict-transport|x-frame|content-security|x-content-type'
curl -s -o /dev/null -w '%{http_code}\n' https://YOUR_DOMAIN/anistito/docs
# انتظار: 404 برای /docs وقتی DEBUG=false
```
