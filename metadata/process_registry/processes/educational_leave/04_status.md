# وضعیت: مرخصی آموزشی موقت

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-02-14 |
| **منبع ورودی** | فلوچارت + متن ۸ گامی |

## نواقص
- [x] فرم‌های UI کمیته (تعیین جلسه + ثبت تصمیم) و فرم بازگشت دانشجو
- [ ] فرایند `violation_registration` — UI زیرفرایند جدا
- [ ] فرایند `patient_referral` — UI زیرفرایند جدا

## وابستگی‌ها
- قوانین: is_intern, is_not_intern, leave_terms_eq_1, leave_terms_eq_2 ✓
- نقش‌ها: deputy_education, monitoring_committee_officer ✓
- قالب‌های اعلان: committee_sla_breach, meeting_scheduled, ... ✓
