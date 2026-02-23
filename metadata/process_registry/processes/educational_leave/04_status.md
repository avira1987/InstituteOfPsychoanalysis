# وضعیت: مرخصی آموزشی موقت

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-02-14 |
| **منبع ورودی** | فلوچارت + متن ۸ گامی |

## نواقص
- [ ] فرایند `violation_registration` تعریف نشده
- [ ] فرایند `patient_referral` تعریف نشده
- [ ] اکشن‌های transition اجرا نمی‌شوند (نیاز به handler)
- [ ] SLA Monitor به deputy_education نمی‌فرستد
- [ ] انتقال sla_breach_7days خودکار trigger نمی‌شود

## وابستگی‌ها
- قوانین: is_intern, is_not_intern, leave_terms_eq_1, leave_terms_eq_2 ✓
- نقش‌ها: deputy_education, monitoring_committee_officer ✓
- قالب‌های اعلان: committee_sla_breach, meeting_scheduled, ... ✓
