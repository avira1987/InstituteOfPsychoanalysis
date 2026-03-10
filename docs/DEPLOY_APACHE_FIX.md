# رفع مشکل «خطای شبکه» و «فرایندی تعریف نشده» در دیپلوی آنلاین

## علت
۱. درخواست‌های HTTPS به `https://lms.psychoanalysis.ir/anistito/` ممکن است به vhost دیگری بروند که ProxyPass برای `/anistito/` ندارد.
۲. اگر سایت اصلی مسیر `/api/` را هندل کند، ممکن است `/anistito/api/` به اشتباه به آن هدایت شود.
۳. Mixed Content: اگر API به آدرس HTTP فراخوانی شود، مرورگر درخواست را مسدود می‌کند.

## راه‌حل: اضافه کردن ProxyPass به همه vhostها

### ۱. پیدا کردن فایل‌های vhost
```bash
ls -la /etc/apache2/sites-available/
# یا
ls -la /etc/httpd/conf.d/
```

### ۲. اضافه کردن به vhost مربوط به lms.psychoanalysis.ir

در **هر** فایل vhost که ممکن است ترافیک `lms.psychoanalysis.ir` را هندل کند، این بلوک را اضافه کنید (قبل از `</VirtualHost>`). **ترتیب مهم است** – قاعده `/anistito/api/` باید قبل از `/anistito/` باشد:

```apache
    # Anistito BPM - Proxy to FastAPI
    ProxyPreserveHost On
    # API first (more specific) - prevents main site /api/ from catching
    ProxyPass /anistito/api/ http://127.0.0.1:3000/api/
    ProxyPassReverse /anistito/api/ http://127.0.0.1:3000/api/
    # Then static and other paths
    ProxyPass /anistito/ http://127.0.0.1:3000/
    ProxyPassReverse /anistito/ http://127.0.0.1:3000/
```

### ۳. فایل‌های معمول
- `pro.conf` (اگر وجود دارد)
- `default-ssl.conf` یا `ssl.conf`
- `000-default-le-ssl.conf` (Let's Encrypt)

### ۴. فعال‌سازی ماژول‌ها
```bash
sudo a2enmod proxy proxy_http
sudo systemctl reload apache2
# یا
sudo systemctl reload httpd
```

### ۵. تست
بعد از reload، این آدرس را در مرورگر باز کنید:
```
https://lms.psychoanalysis.ir/anistito/debug/process-count
```
باید پاسخ `{"process_count": 7}` (یا عددی مشابه) برگردد.

اگر این endpoint کار کرد ولی لیست فرایندها هنوز خالی است، احتمالاً مشکل احراز هویت است (توکن یا نقش کاربر).
