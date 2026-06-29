# فرایند ۶۸ — مقدمات برگزاری جلسات سوپرویژن زنده

## وضعیت UI (2026-06-28)

- [x] متادیتا: ۲ فرم (ارجاع بیمار + تعیین زمان)
- [x] پنل راهنما: `LiveSessionPrepPanel` + `liveSessionPrepDisplay.jsx` (مشترک با فرایند ۶۶)
- [x] StaffPortal: lane پذیرش (`patient_referral`) و lane هماهنگی (`coordination_pending`)
- [x] `liveSessionPrepTriggerPayload.js` — flag `session_time_registered` و اعتبارسنجی فرم
- [x] Backend: `engine.py` — set `session_time_registered` بر اساس trigger
- [x] Backend: `action_handler.py` — SMS به مدرس/کمک‌مدرس/دانشجویان + `record_session_prep`
- [x] تست flow: `tests/processes/test_live_session_prep_flow.py`

## نقش‌ها و پورتال

| state | نقش | پورتال |
|-------|-----|--------|
| patient_referral | admission_officer | StaffPortal (admissions) |
| coordination_pending | therapy_education_coordinator | StaffPortal (therapy-coord) |

## نواقص احتمالی بعدی

- [ ] دکمهٔ «شروع فرایند جدید» در پنل پذیرش
- [ ] SLA هماهنگی و هشدار تأخیر
- [ ] یکپارچه‌سازی عمیق‌تر LMS (فراتر از artifact)
