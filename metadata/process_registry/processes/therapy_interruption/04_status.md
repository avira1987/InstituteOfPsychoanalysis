# وضعیت: وقفه در درمان آموزشی توسط دانشجو

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-02-14 |
| **منبع ورودی** | فلوچارت + متن ۱۴ گامی |

## نواقص
- [ ] محاسبه `instance.interruption_days` از `interruption_start_date` و `interruption_end_date` هنگام تایید
- [ ] بررسی خودکار در تاریخ پایان وقفه (awaiting_return → returned_successfully یا no_return_resources_freed)
- [ ] اکشن‌ها: record_interruption_dates, retain_therapist_and_supervisor, release_supervisor_slots, release_therapist_slots, move_to_past_lists
- [ ] `run_if_intern` برای start_process patient_referral
- [ ] وابسته به violation_registration و patient_referral (هنوز پیاده‌سازی نشده‌اند)
