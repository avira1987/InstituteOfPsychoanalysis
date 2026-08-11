# وضعیت: ثبت‌نام در دوره آشنایی

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-06-01 |
| **منبع ورودی** | SOP مرحلهٔ ۳۱ (متن ۴ فاز + فلوچارت) |
| **sop_order** | 31 |

## نقش‌ها
- applicant (متقاضی)
- interviewer (مصاحبه‌گر)
- admissions_officer (مسئول پذیرش)
- system

## نواقص
- [ ] اثر واقعی روی LMS (ایجاد کلاس/لینک زنده) وابسته به قرارداد API و وب‌هوک — تا آن زمان `integration_events` کافی است.
- [x] پس از نتیجهٔ قبولی، انتقال خودکار به `documents_upload` + SMS `required_documents_list`
- [x] متن کامل SMSهای فاز ۱–۳ در `notification_service.TEMPLATES`
- [x] امضای دیجیتال تعهدنامه با `sms_verification` + OTP
- [x] نمایش USERNAME/PASSWORD در پورتال پس از `credentials_created`
- [x] مسدودسازی ثبت‌نام مجدد با `future_applications_blocked` در ثبت عمومی
- [x] تریگر تقویمی اقساط (`installment_due_date_passed`) via `process_scheduler.dispatch_installment_overdue`

## وابستگی‌ها (sub_process_refs)
- `fall_semester_preparation` باید به state `published` برسد و تقویم آموزشی فعال شود تا کل فرایند `introductory_course_registration` (از مصاحبه تا پرداخت) باز شود — `app/services/registration_readiness_service.py`

## قالب‌های اعلان
- interview_scheduled_student_online / interview_scheduled_student_in_person ✓
- interview_scheduled_interviewer / interview_booking_confirmed_interviewer ✓
- interview_reminder_applicant_online / _inperson ✓
- interview_reminder_interviewer_online / _inperson ✓
- result_conditional_therapy / result_single_course / result_full_admission / result_rejected ✓
- required_documents_list / documents_deficiency_list ✓
- lms_credentials ✓

## فرم‌ها
- interview_result_form (محرمانه) ✓
- documents_upload_form (با تعهدنامه) ✓
- course_selection_form ✓
- payment_form (نقدی/اقساطی) ✓

## یادداشت
از 2026-05-07: پس از انتخاب زمان مصاحبه (`timeslot_selected`) ورود مستقیم به `interview_payment`. متادیتای `student_short_fa` / `student_task_fa` / `student_why_fa` روی stateها برای نوار «وضعیت فعلی / اقدام بعدی» در پنل دانشجو.

از 2026-08-03: راهنمای گام بعدی در `StudentQuestCard` و `StudentIntroductoryCourseRegistrationPanel`؛ گیت بسته روی نتیجهٔ پذیرش → `context_data.student_next_action_fa`؛ Sep برای `installment_overdue`.

همگام‌سازی SOP با DB:
`scripts/sync_sop_doc_from_registry_files.py --code introductory_course_registration`
