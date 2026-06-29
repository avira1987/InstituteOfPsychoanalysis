# وضعیت UI — فرایند ۴۵ (ta_essay_upload)

## پیاده‌سازی شده

- metadata: states کامل تا `content_published`، forms آپلود TA / مرکز مرجع / مارکتینگ
- UI: `TaEssayUploadPanel` + `taEssayUploadDisplay.jsx`
- پورتال: lane `instruction` (TA + مدرس)، lane `content-ops` (مرکز مرجع + مارکتینگ)
- deep links در `operatorFollowupDeepLinks.js`
- prefill جلسه در `process_form_prefill.py`
- تست flow: `tests/processes/test_ta_essay_upload_flow.py`

## نواقص / بعداً

- SLA breach → `violation_registration` (action در metadata هنوز stub)
- امتیازدهی TA پس از تأیید مدرس (۱/۲ نمره بر اساس رسته)
- قالب Word واقعی در `admin-ui/public/templates/ta_essay_minutes_template.docx`
- نقش‌های کاربری `reference_center` و `marketing` در seed کاربران
