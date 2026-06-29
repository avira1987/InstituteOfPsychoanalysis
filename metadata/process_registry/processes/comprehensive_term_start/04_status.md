# وضعیت: آغاز ترم‌های دوره جامع

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-06-28 |
| **منبع ورودی** | SOP مرحلهٔ ۴۰ (متن ۵ فاز + فلوچارت) |
| **sop_order** | 40 |

## نقش‌ها
- student (دانشجو)
- instructor (مدرس — کنترل حضور در صورت بدهی)
- course_committee_executive
- system

## UI دانشجو
- [x] `StudentComprehensiveTermStartPanel` — stepper، راهنمای وضعیت، کاشی شهریه/پرداخت/اقساط، جدول دروس ثابت/جبرانی
- [x] `comprehensiveTermStartDisplay.jsx` — برچسب‌ها، پیام blocked، resolver context، eligibility pending
- [x] اتصال در `StudentPortal.jsx` (تب فرایندها)
- [x] اتصال compact در `StudentQuestCard.jsx` (داشبورد)
- [x] پرداخت سپ در وضعیت `payment_processing` (داخل پنل — بدون تکرار در QuestCard)
- [x] callback پرداخت سپ → `payment_confirmed` در `payment_routes.py`

## فرم‌ها
- `comprehensive_term_courses` (readonly_table دروس) — `course_display`
- `comprehensive_term_payment` (radio/select پرداخت) — `payment_choice`

## نواقص
- [ ] محاسبه/پیش‌پر خودکار دروس جبرانی (حداکثر ۳) بر اساس معدل و لیست اولویت
- [ ] پایش خودکار سررسید اقساط و بلاک حضور (فاز ۵ SOP)
- [ ] اتصال LMS برای فعال‌سازی لینک کلاس‌ها پس از `registration_complete`
- [ ] SMS `tuition_payment_to_accounting` به واحد حسابداری

## یادداشت
فرایند batch_start از `InstituteCalendar.term_registration_window` راه‌اندازی می‌شود.
همگام‌سازی SOP: `scripts/sync_sop_doc_from_registry_files.py --code comprehensive_term_start`
راهنمای تست UI: `python scripts/generate_comprehensive_term_start_operator_guide_pdf.py`
