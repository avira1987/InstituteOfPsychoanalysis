# وضعیت: قطع زودرس درمان آموزشی توسط درمانگر — بخش ۱

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-02-14 |
| **منبع ورودی** | فلوچارت + متن ۴ گامی |

## نواقص
- [ ] اکشن‌ها: log_termination_request, mark_therapy_relationship_terminated, release_therapist_slots, record_termination_in_student_portal
- [ ] اکشن set_student_status (pending_investigation)
- [ ] اکشن call_bpms_subprocess (زیرفرایند الف و ب)
- [ ] SLA ۵ روز برای awaiting_student_restart و trigger violation
- [ ] زیرفرایند الف: بررسی کمیسیون تخصصی (گزینه ۳)
- [ ] زیرفرایند ب: بررسی کمیته‌های نظارت و آموزش (گزینه ۴)

## قوانین اضافه‌شده
- termination_reason_1_or_2, termination_reason_3, termination_reason_4 ✓
