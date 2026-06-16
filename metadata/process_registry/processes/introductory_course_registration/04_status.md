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
- [ ] تریگر تقویمی اقساط ترم اول (`installment_due_date_passed`) به context زمان‌دار واقعی دانشجو وابسته است

## وابستگی‌ها (sub_process_refs)
- ندارد (مستقل)

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
از 2026-05-07: پس از انتخاب زمان مصاحبه (`timeslot_selected`) ورود مستقیم به `interview_payment`. متادیتای `student_task_fa` روی stateها برای راهنمای پنل دانشجو.

همگام‌سازی SOP با DB:
`scripts/sync_sop_doc_from_registry_files.py --code introductory_course_registration`
