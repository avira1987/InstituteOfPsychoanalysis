# وضعیت: فرایند ۴۹ — ارتقا به دستیار هیئت علمی

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata + UI wired + backend service |
| **آخرین به‌روزرسانی** | 2026-06-28 |
| **منبع ورودی** | SOP فرایند ۴۹ |

## UI
- [x] `taToAssistantFacultyDisplay.jsx` + `taToAssistantFacultyTriggerPayload.js`
- [x] `TaToAssistantFacultyReviewPanel` + اتصال CommitteePortal
- [x] `TaToAssistantFacultyTaPanel` + اتصال StaffPortal (instruction lane)
- [x] `isWaitingForReview` صریح برای `supervision_review`
- [x] `contextInstanceDisplay` + `processMetadataLabels` student hints

## Backend
- [x] `ta_to_assistant_faculty_service.py` — context, propagate_on_start, scan, flags
- [x] engine: start propagate + status context + after-transition chain
- [x] `process_form_prefill.py` — prefill فرم بررسی
- [x] `process_scheduler.py` — پایش پایان ترم + auto-start
- [x] `test_ta_to_assistant_faculty_flow.py`

## نواقص احتمالی
- [ ] اتصال `ta_course_completions` به فرایندهای واقعی ارزیابی TA (فعلاً از extra_data.lms)
- [ ] متن نهایی پیام رد (placeholder جعفریان)
