# فرایند ۷۲ — ارجاع کلیه بیماران انترن

## وضعیت UI (2026-06-28)

- [x] متادیتا: ۴ فرم (نظارت + دانشجو + کمیته درمان + هماهنگی)
- [x] پنل کمیته نظارت: `InternBulkPatientReferralSupervisionPanel` + `OperatorStepFormsSection`
- [x] پنل دانشجو: `StudentInternBulkPatientReferralPanel` + `ProcessStepForms`
- [x] پنل کمیته درمان عموم: `InternBulkPatientReferralTherapyCommitteePanel`
- [x] پنل مسئول هماهنگی: `InternBulkPatientReferralCoordinationPanel` در StaffPortal (lane therapy-coord)
- [x] Backend: `intern_bulk_patient_referral_chaining.py` (انتشار خودکار `patient_list_published`)
- [x] اعتبارسنجی trigger در `app/api/process/routes.py`
- [x] prefill در `process_form_prefill.py`
- [x] تست flow: `tests/processes/test_intern_bulk_patient_referral_flow.py`

## منبع لیست بیماران

ثبت **دستی** توسط کمیته نظارت در جدول فرم `supervision_start`؛ ذخیره در `context_data.patient_referral_rows`.

## نقش‌ها و پورتال

| state | نقش | پورتال |
|-------|-----|--------|
| supervision_start | supervision_committee | CommitteePortal |
| student_patient_log | student | StudentPortal |
| general_therapy_committee_review | therapy_committee_executor | CommitteePortal (therapy) |
| coordination_followup | therapy_education_coordinator | StaffPortal (therapy-coord) |

## SLA

- `student_patient_log`: ۱۵ روز (metadata `sla_days`)
- `coordination_followup`: ۳ روز

## نواقص احتمالی بعدی

- [ ] SMS/اعلان SLA به کمیته نظارت و معاون مدیر داخلی در scheduler
- [ ] یکپارچه‌سازی با منبع واقعی بیماران (LMS/پرونده درمان) در صورت اضافه شدن مدل Patient
