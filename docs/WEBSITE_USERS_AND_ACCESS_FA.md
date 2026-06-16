# مستند کامل کاربران وب‌سایت، سطوح دسترسی و اطلاعات ورود (anistito)

> این مستند شامل تمام نقش‌های کاربری سامانه، سطح دسترسی هر نقش، مسیر پورتال اختصاصی و نام کاربری/رمز عبور (دمو و پیش‌فرض) است.
>
> ⚠️ **هشدار امنیتی:** رمزهای عبور فهرست‌شده در این سند صرفاً برای محیط دمو/توسعه هستند. در محیط واقعی (Production) باید همگی تغییر کنند و این فایل نباید در مخزن عمومی منتشر شود.

---

## ۱. مدل کاربر (`User`)

جدول `users` در `app/models/operational_models.py` حساب‌های پنل/سایت را نگه می‌دارد. سطح دسترسی از روی فیلد رشته‌ای `role` به‌علاوه‌ی بررسی‌های RBAC تعیین می‌شود.

| فیلد | توضیح |
|------|-------|
| `username` | نام کاربری یکتا برای ورود با مسیر «ورود پرسنل» |
| `hashed_password` | رمز عبور هش‌شده |
| `portal_password_plain` | رمز ساده (فقط برای دانشجو، جهت نمایش به ادمین/کارمند) |
| `role` | نقش کاربر (مبنای سطح دسترسی) |
| `is_active` | فعال/غیرفعال بودن حساب |

---

## ۲. فهرست کامل نقش‌ها و سطح دسترسی

| کد نقش | عنوان فارسی | مسیر پورتال | خلاصه سطح دسترسی |
|--------|-------------|-------------|------------------|
| `admin` | مدیر سیستم | `/panel` (همه‌جا) | دسترسی کامل (Superuser). از تمام بررسی‌های `require_role` عبور می‌کند. مدیریت فرایندها، قواعد، کاربران، نقش‌ها، گزارش‌ها، مالی |
| `staff` | کارمند دفتر | `/panel/portal/staff` | پذیرش، بررسی مدارک، اسلات/رزرو مصاحبه، تخصیص، مدیریت پرداخت‌ها، لیست دانشجو |
| `finance` | اپراتور مالی | `/panel/finance` | داشبورد مالی، تأیید و مدیریت پرداخت‌ها |
| `student` | دانشجو | `/panel/portal/student` | نقشه‌راه فرایند، فرم‌ها، پرداخت‌ها، جلسات درمان، تکالیف |
| `therapist` | درمانگر | `/panel/portal/therapist` | دانشجویان تخصیص‌یافته، جلسات درمان، بررسی‌های در انتظار |
| `supervisor` | سوپروایزر | `/panel/portal/supervisor` | بررسی‌های سوپروایزری، لیست دانشجو، اقدامات فرایندی |
| `site_manager` | مسئول سایت | `/panel/portal/site-manager` | هشدارهای حضور و غیاب، زمان‌بندی مصاحبه، بررسی مدارک |
| `interviewer` | مصاحبه‌گر | `/panel/portal/interviewer` | اسلات‌ها، رزروها، قواعد تکرارشونده، پیگیری اپراتوری |
| `progress_committee` | کمیته پیشرفت | `/panel/portal/committee` | پنل کمیته‌ای مخصوص نقش |
| `education_committee` | کمیته آموزش | `/panel/portal/committee` | پنل کمیته‌ای مخصوص نقش |
| `supervision_committee` | کمیته نظارت | `/panel/portal/committee` | پنل کمیته‌ای مخصوص نقش |
| `specialized_commission` | کمیسیون تخصصی | `/panel/portal/committee` | پنل کمیته‌ای مخصوص نقش |
| `therapy_committee_chair` | مسئول کمیته درمان | `/panel/portal/committee` | پنل کمیته‌ای مخصوص نقش |
| `therapy_committee_executor` | مجری کمیته درمان | `/panel/portal/committee` | پنل کمیته‌ای مخصوص نقش |
| `deputy_education` | معاون آموزش | `/panel/portal/committee` | پنل کمیته‌ای + دسترسی گزارش‌ها و مدیریت اسلات |
| `monitoring_committee_officer` | مسئول کمیته پایش | `/panel/portal/committee` | پنل کمیته‌ای + دسترسی گزارش‌ها |

**نکات مهم سطح دسترسی:**
- نقش `admin` از تمام بررسی‌های `require_role(...)` عبور می‌کند (ابرکاربر).
- «مدیر سایت اصلی» = حساب با `role=admin` و `username=admin` (`PRIMARY_SITE_ADMIN_USERNAME`).
- `finance` و `interviewer` در `metadata/roles.json` فهرست مجوزها ندارند (شکاف مستندشده).

---

## ۳. مسیرهای ورود (Authentication)

| مسیر | کاربر | روش |
|------|-------|-----|
| OTP (`/api/auth/otp/*`) | دانشجویان (تب پیش‌فرض ورود عمومی) | کد ۶ رقمی پیامکی → JWT |
| رمز عبور (`/api/auth/login-json`) | کارمند/ادمین («ورود پرسنل») | نام کاربری + رمز + **کپچای ریاضی** |
| فرم OAuth2 (`/api/auth/login`) | API/تست‌ها | نام کاربری + رمز، بدون کپچا |

**صدور رمز دانشجو:**
- ورود اول با OTP → رمز عددی ۶ رقمی (در `portal_password_plain` ذخیره می‌شود).
- ثبت‌نام عمومی → رمز تصادفی ۱۴ کاراکتری (یک‌بار در پاسخ API برگردانده می‌شود).

---

## ۴. نام کاربری و رمز عبور (محیط دمو/پیش‌فرض)

### الف) حساب پیش‌فرض همیشگی (در زمان راه‌اندازی ساخته می‌شود)

| نام کاربری | رمز عبور | نقش |
|------------|----------|------|
| `admin` | `admin123` | مدیر سیستم |

### ب) کاربران دموی هر نقش (الگوی `{role}1`، رمز `demo123`)

| نام کاربری | نقش | رمز عبور |
|------------|------|----------|
| `student1` | دانشجو | `demo123` |
| `therapist1` | درمانگر | `demo123` |
| `supervisor1` | سوپروایزر | `demo123` |
| `staff1` … `staff10` | کارمند دفتر | `demo123` |
| `finance1` | اپراتور مالی | `demo123` |
| `site_manager1` | مسئول سایت | `demo123` |
| `progress_committee1` | کمیته پیشرفت | `demo123` |
| `education_committee1` | کمیته آموزش | `demo123` |
| `supervision_committee1` | کمیته نظارت | `demo123` |
| `specialized_commission1` | کمیسیون تخصصی | `demo123` |
| `therapy_committee_chair1` | مسئول کمیته درمان | `demo123` |
| `therapy_committee_executor1` | مجری کمیته درمان | `demo123` |
| `deputy_education1` | معاون آموزش | `demo123` |
| `monitoring_committee_officer1` | مسئول کمیته پایش | `demo123` |

### ج) بازیگران سناریو (با `role=staff` ذخیره می‌شوند)

| نام کاربری | رمز عبور | توضیح |
|------------|----------|-------|
| `demo_interviewer` | `demo123` | مصاحبه‌گر در سناریوها (نقش واقعی: staff) |
| `demo_admissions` | `demo123` | کارشناس پذیرش |
| `demo_applicant` | `demo123` | متقاضی |

### د) دانشجویان دموی فرایند

| الگوی نام کاربری | رمز عبور پیش‌فرض | متغیر محیطی |
|-------------------|------------------|--------------|
| `AUTO-DEMO-*`, `DEMO-SCEN-*`, `DEMO-OP-*` | `demo_student_123` | `DEMO_MATRIX_STUDENT_PASSWORD` |
| `demo_op_intv`, `demo_op_adm`, `demo_op_site`, `demo_op_asgn`, `demo_op_extra` | `demo_student_123` | `DEMO_MATRIX_STUDENT_PASSWORD` |
| `regdemo_*` (مثل `regdemo_intro_app`) | `demo123` | `DEMO_REG_PASSWORD` |

### ه) کاربران تست (`tests/conftest.py`)

| الگوی نام کاربری | رمز عبور |
|-------------------|----------|
| `admin_test_{hex}` | `testpass` |
| `student_test_{hex}` | `testpass` |

---

## ۵. اسکریپت‌های Seed (محل ساخت کاربران)

| فایل | کاربرد |
|------|--------|
| `app/main.py` (`_ensure_admin_user`) | ساخت `admin/admin123` در راه‌اندازی |
| `app/demo_role_users.py` | منطق اصلی کاربران دمو |
| `app/seed_all_roles.py` / `scripts/seed_all_roles.py` | یک کاربر برای هر نقش |
| `scripts/seed_demo_users.py` | دموی گسترده (۳ دانشجو، ۱۰ کارمند) |
| `app/website_staff_seed.py` | `staff1`–`staff10` |
| `app/seed_operator_pending_demo.py` | دانشجویان `DEMO-OP-*` |
| `scripts/seed_registration_portal_demo.py` | کاربران `regdemo_*` |
| `app/create_admin.py` / `scripts/create_admin.py` | بازنشانی ادمین به `admin123` |

---

## ۶. جدول خلاصه (Cheat Sheet)

```
admin                          / admin123        (مدیر سیستم - دسترسی کامل)
student1, therapist1, …        / demo123         (الگو: {role}1)
staff1 … staff10               / demo123
finance1, deputy_education1, … / demo123
demo_interviewer               / demo123         (role=staff)
demo_admissions                / demo123         (role=staff)
demo_applicant                 / demo123         (role=staff)
AUTO-DEMO-*, DEMO-OP-*         / demo_student_123 (env: DEMO_MATRIX_STUDENT_PASSWORD)
regdemo_*                      / demo123          (env: DEMO_REG_PASSWORD)
```

---

## ۷. شکاف‌ها و نکات

1. نقش `interviewer` پورتال و API کامل دارد اما در `SUPPORTED_ROLES` و `roles.json` نیست.
2. `finance` به‌صورت `finance1` ساخته می‌شود اما در کاتالوگ مجوزهای `roles.json` نیست.
3. `admin` همیشه از `require_role` عبور می‌کند (ابرکاربر API).
4. رمز دانشجو در Production معمولاً پویا است (OTP ۶ رقمی یا ثبت‌نام ۱۴ کاراکتری).
5. ورود پرسنل نیاز به کپچای ریاضی دارد؛ مسیر فرم خام `POST /api/auth/login` آن را رد می‌کند (در تست‌ها).
6. اعتبارنامه‌ی دیتابیس (نه کاربر پنل): پیش‌فرض `postgresql+asyncpg://anistito:anistito@localhost:5432/anistito`.
