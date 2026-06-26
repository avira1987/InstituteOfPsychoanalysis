# وضعیت: قطع زودرس درمان آموزشی توسط درمانگر — بخش ۱

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-06-25 |
| **منبع ورودی** | فلوچارت + متن ۴ گامی |

## UI (بخش ۱ — آغاز و مسیریابی)
- [x] فرم مرحله `reason_selection` با فیلد رادیویی `termination_reason_code` در metadata/processes/therapy_early_termination.json
- [x] پنل راهنمای درمانگر `TherapistEarlyTerminationPanel.jsx` (۴ مسیر + مهلت ۵ روز)
- [x] شروع فرایند و اتصال در `TherapistPortal.jsx`

## نواقص
- [ ] اکشن‌ها: log_termination_request, mark_therapy_relationship_terminated, release_therapist_slots, record_termination_in_student_portal
- [ ] اکشن set_student_status (pending_investigation)
- [ ] اکشن call_bpms_subprocess (زیرفرایند الف و ب)
- [ ] SLA ۵ روز برای awaiting_student_restart و trigger violation
- [ ] زیرفرایند الف: بررسی کمیسیون تخصصی (گزینه ۳)
- [ ] زیرفرایند ب: بررسی کمیته‌های نظارت و آموزش (گزینه ۴)

## قوانین اضافه‌شده
- termination_reason_1_or_2, termination_reason_3, termination_reason_4 ✓
