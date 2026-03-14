# راهنمای گام‌به‌گام اتصال به هاست و آپلود پروژه آنیستیتو

این راهنما دو روش را پوشش می‌دهد:
1. **روش خودکار**: اجرای یک اسکریپت که همه مراحل را انجام می‌دهد (پیشنهادی).
2. **روش دستی**: انجام مرحله‌به‌مرحله برای اتصال و آپلود.

---

## پیش‌نیازها

- **Node.js** و **npm** (برای بیلد فرانت‌اند)
- دسترسی به اینترنت برای آپلود به سرور
- یکی از این‌ها برای اتصال به سرور:
  - **PuTTY** (شامل `pscp.exe` و `plink.exe`) — [دانلود PuTTY](https://www.putty.org/)
  - یا **Posh-SSH** در PowerShell (اسکریپت در صورت نبود PuTTY آن را نصب می‌کند)

اطلاعات اتصال سرور (برای روش دستی):

| مورد | مقدار |
|------|--------|
| آدرس (IP) | `80.191.11.129` |
| پورت SSH | `2022` |
| کاربر | `root` |
| رمز | (در اسکریپت یا فایل‌های deploy موجود است) |
| مسیر روی سرور | `/opt/anistito` |
| آدرس نهایی سایت | https://bpms.psychoanalysis.ir/anistito/ |

---

## روش ۱: دیپلوی خودکار (یک دستور)

در محیطی که هم به **کد پروژه** و هم به **اینترنت** (برای اتصال به هاست) دسترسی دارید:

1. پوشه پروژه را باز کنید (مثلاً `C:\Users\Administrator\Desktop\anistito`).
2. در **PowerShell** از ریشه پروژه اجرا کنید:

```powershell
cd C:\Users\Administrator\Desktop\anistito
.\deploy-to-host.ps1
```

این اسکریپت به ترتیب انجام می‌دهد:
- بیلد فرانت‌اند (`admin-ui` با Vite)
- ساخت بستهٔ دیپلوی (zip) از کد بک‌اند، فرانت بیلدشده، metadata، Dockerfile و ...
- آپلود zip به سرور با **pscp** یا **Posh-SSH**
- اجرای دستورات روی سرور: unzip، حذف کانتینر قبلی، `docker build`، `docker run`، مایگریشن و چک سلامت

در پایان آدرس و ورود نمایش داده می‌شود:
- **URL:** https://bpms.psychoanalysis.ir/anistito/
- **ورود:** admin / admin123

---

## روش ۲: گام‌به‌گام دستی

### گام ۱ — بیلد فرانت‌اند (محلی)

```powershell
cd C:\Users\Administrator\Desktop\anistito\admin-ui
npm install
npm run build
```

خروجی بیلد در `admin-ui\dist` قرار می‌گیرد.

---

### گام ۲ — ساخت بستهٔ دیپلوی (zip)

محتویاتی که باید در zip باشند (مشابه اسکریپت):

- `app/` (کد بک‌اند)
- `metadata/`
- `alembic/`
- `scripts/` (در صورت وجود)
- `admin-ui/dist` ، `admin-ui/src` ، `admin-ui/index.html` ، `admin-ui/package.json` ، `admin-ui/vite.config.js` (و در صورت وجود `admin-ui/public`)
- فایل‌های ریشه: `requirements.txt` ، `Dockerfile` ، `alembic.ini` و در صورت وجود `.dockerignore`

می‌توانید از اسکریپت فقط برای ساخت zip استفاده کنید یا همین محتویات را دستی در یک پوشه بریزید و zip کنید. نام پیشنهادی بسته: `deploy-anistito.zip`.

---

### گام ۳ — اتصال به هاست و آپلود بسته

#### با PuTTY (pscp)

در CMD یا PowerShell (مسیر zip را با مسیر واقعی عوض کنید):

```cmd
pscp -P 2022 -pw <رمز-سرور> deploy-anistito.zip root@80.191.11.129:/opt/anistito/
```

یا اگر `pscp` در PATH نیست:

```cmd
"C:\Program Files\PuTTY\pscp.exe" -P 2022 -pw <رمز-سرور> deploy-anistito.zip root@80.191.11.129:/opt/anistito/
```

#### با WinSCP

1. WinSCP را باز کنید.
2. **میزبان:** `80.191.11.129`  
   **پورت:** `2022`  
   **کاربر:** `root`  
   **رمز:** (رمز سرور)
3. اتصال و سپس آپلود فایل `deploy-anistito.zip` به مسیر `/opt/anistito/`.

---

### گام ۴ — اجرای دستورات روی سرور

بعد از آپلود zip، باید روی سرور این کارها انجام شود: باز کردن zip، ساخت تصویر Docker و اجرای کانتینر.

#### با PuTTY (اتصال SSH و اجرای دستور)

1. با **PuTTY** به سرور وصل شوید:
   - Host: `80.191.11.129`
   - Port: `2022`
   - کاربر: `root`
2. بعد از لاگین، این دستورات را اجرا کنید:

```bash
cd /opt/anistito
unzip -o deploy-anistito.zip -d .
rm -f deploy-anistito.zip
docker rm -f anistito-api 2>/dev/null || true
docker build -t anistito-api .
docker run -d --name anistito-api --network anistito-net -p 3000:3000 \
  -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito \
  -e DATABASE_URL_SYNC=postgresql://anistito:anistito@anistito-db:5432/anistito \
  -e REDIS_URL=redis://anistito-redis:6379/0 \
  -e DEBUG=false \
  -e SECRET_KEY=anistito-prod-secret \
  anistito-api:latest sh -c "python -m alembic upgrade head 2>/dev/null || true && python -m uvicorn app.main:app --host 0.0.0.0 --port 3000"
sleep 15
curl -s http://localhost:3000/health
```

اگر خروجی `curl` وضعیت سرویس را نشان داد، دیپلوی موفق است.

#### با plink (بدون باز کردن پنجره PuTTY)

اگر `plink` در دسترس است، می‌توان همان دستورات را یک‌جا فرستاد (در یک خط، با `&&` بین دستورات). نمونه در اسکریپت‌های `deploy-to-host.ps1` و `do-deploy.ps1` وجود دارد.

---

## اگر فقط به سرور دسترسی دارید (zip از قبل آپلود شده)

اگر فایل `deploy-anistito.zip` از قبل در `/opt/anistito/` روی سرور قرار گرفته (مثلاً توسط شخص دیگر یا از مسیر دیگر کپی شده)، کافی است **روی خود سرور** اسکریپت دیپلوی را اجرا کنید:

```bash
cd /opt/anistito
bash server-deploy-now.sh
```

یا محتوای همان اسکریپت را دستی اجرا کنید (unzip، `docker rm`، `docker build`، `docker run`، و در پایان `curl .../health`).

---

## عیب‌یابی کوتاه

| مشکل | اقدام پیشنهادی |
|------|-----------------|
| خطای بیلد فرانت | در `admin-ui` اجرا کنید: `npm install` و دوباره `npm run build`. |
| خطای آپلود (pscp) | پورت `2022` و فایروال/دسترسی شبکه را چک کنید؛ از WinSCP هم امتحان کنید. |
| خطای SSH | با PuTTY مستقیم وصل شوید و ببینید رمز و کاربر درست است یا نه. |
| کانتینر بالا نمی‌آید | روی سرور: `docker logs anistito-api --tail 50` و وضعیت شبکه/دیتابیس را بررسی کنید. |
| ۵۰۳ یا سایت باز نمی‌شود | مطمئن شوید سرویس روی پورت ۳۰۰۰ در حال اجرا است و پروکسی (مثلاً Apache/Nginx) به همان پورت اشاره می‌کند. |

مستندات بیشتر: `docs/TROUBLESHOOT_503.md` و `docs/DEPLOY_APACHE_FIX.md`.

---

## خلاصه

- **یک دستور برای دیپلوی کامل (از ویندوز):** از ریشه پروژه اجرا کنید: `.\deploy-to-host.ps1`
- **فقط روی سرور (وقتی zip آماده است):** در `/opt/anistito` اجرا کنید: `bash server-deploy-now.sh`
- **دستی:** بیلد فرانت → ساخت zip → آپلود با pscp/WinSCP → اجرای دستورات بالا روی سرور با SSH.

بعد از دیپلوی، آخرین نسخهٔ وب‌سایت روی هاست در آدرس https://bpms.psychoanalysis.ir/anistito/ در دسترس است.
