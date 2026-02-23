# مقایسه نسخه قبلی و نسخه جدید فرایند مرخصی آموزشی

## خلاصه تصمیم

**نسخه جدید (ادغام‌شده) کامل‌تر است و در metadata ذخیره شد.**

---

## جدول مقایسه تفصیلی

| مورد | نسخه قبلی (موجود) | نسخه جدید (از فلوچارت + متن) |
|------|-------------------|------------------------------|
| **تعداد وضعیت‌ها** | ۱۲ | ۱۳ (اضافه: deputy_alerted) |
| **توضیح فرایند** | کوتاه | مفصل با فلسفه و هدف |
| **توضیح انتقال‌ها** (description_fa) | ندارد | برای همه انتقال‌ها |
| **هشدار SLA → معاون مدیر آموزش** | ندارد | دارد (deputy_alerted + on_sla_breach_event) |
| **متن هشدار انترن+۲ترم** | خلاصه | متن مصوب کامل |
| **اطلاع کمیته نظارت در رد** | ندارد | دارد (SMS به monitoring_committee_officer) |
| **اطلاع کمیته در ارجاع بیماران** | ندارد | دارد |
| **ایمیل + پیامک جلسه** | ندارد | دارد (meeting_scheduled) |
| **قالب‌های اعلان جدید** | - | committee_sla_breach, meeting_scheduled, leave_rejected_committee_alert, intern_2term_referral_started |
| **نقش‌های جدید** | - | deputy_education, monitoring_committee_officer |

---

## موارد اضافه‌شده در نسخه جدید

1. **وضعیت deputy_alerted**: وقتی کمیته ظرف ۷ روز جلسه را تنظیم نکند، هشدار به معاون مدیر آموزش.
2. **on_sla_breach_event** در committee_review: برای یکپارچگی با SLA Monitor.
3. **انتقال committee_review → deputy_alerted** با trigger: sla_breach_7days.
4. **توضیحات (description_fa)** برای هر انتقال.
5. **قالب‌های اعلان** جدید در notification_service.
6. **نقش‌های** deputy_education و monitoring_committee_officer در roles.json.

---

## فایل‌های تغییر یافته

- `metadata/processes/educational_leave.json` — به‌روزرسانی شد
- `metadata/roles.json` — دو نقش جدید اضافه شد
- `app/services/notification_service.py` — چهار قالب جدید اضافه شد

---

## بارگذاری در دیتابیس

بارگذاری انجام شد با دستور:
```bash
python -c "import asyncio; from app.meta.seed import clear_and_reseed; asyncio.run(clear_and_reseed())"
```

**هشدار**: `clear_and_reseed` تمام جداول (شامل کاربران، دانشجویان، نمونه‌های فرایند و ...) را حذف و از نو ایجاد می‌کند. فقط در محیط توسعه یا هنگام راه‌اندازی اولیه استفاده کنید.
