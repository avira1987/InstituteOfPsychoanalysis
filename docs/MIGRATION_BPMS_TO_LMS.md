# مهاجرت از bpms.psychoanalysis.ir به lms.psychoanalysis.ir

این سند مراحل لازم برای تغییر دامنه آنیستیتو را شرح می‌دهد.

## تغییرات انجام‌شده در کد

- تمام ارجاعات به `bpms.psychoanalysis.ir` در اسکریپت‌های deploy و مستندات به `lms.psychoanalysis.ir` تغییر یافته است.
- متغیر `APP_BASE_URL` به config اضافه شده (پیش‌فرض: `https://lms.psychoanalysis.ir/anistito`).
- `.env.example` با آدرس callback پرداخت جدید به‌روزرسانی شده است.

## مراحل باقی‌مانده (روی سرور)

### ۱. DNS
رکورد A یا CNAME برای `lms.psychoanalysis.ir` به IP سرور (`80.191.11.129`) اضافه کنید.

### ۲. گواهی SSL
گواهی SSL برای `lms.psychoanalysis.ir` نصب کنید (مثلاً با certbot):
```bash
certbot --apache -d lms.psychoanalysis.ir
```

### ۳. Apache vhost
فایل vhost برای `lms.psychoanalysis.ir` ایجاد یا ویرایش کنید و بلوک ProxyPass زیر را اضافه کنید:

```apache
ProxyPreserveHost On
ProxyPass /anistito/api/ http://127.0.0.1:8000/api/
ProxyPassReverse /anistito/api/ http://127.0.0.1:8000/api/
ProxyPass /anistito/ http://127.0.0.1:8000/
ProxyPassReverse /anistito/ http://127.0.0.1:8000/
```

سپس Apache را reload کنید:
```bash
sudo systemctl reload apache2
```

### ۴. متغیر محیطی روی سرور
در `.env` یا environment کانتینر Docker:
```
PAYMENT_CALLBACK_URL=https://lms.psychoanalysis.ir/anistito/api/payment/callback
```

### ۵. درگاه پرداخت
اگر از سامان یا زیبال استفاده می‌کنید، آدرس callback را در پنل درگاه به آدرس جدید به‌روزرسانی کنید.

### ۶. تست
بعد از انجام مراحل بالا:
- https://lms.psychoanalysis.ir/anistito/
- https://lms.psychoanalysis.ir/anistito/debug/process-count
