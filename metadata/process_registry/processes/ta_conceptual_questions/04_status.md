# وضعیت فرایند: ta_conceptual_questions (شماره ۴۳)

## خلاصه

ثبت ۳ سوال تستی‌مفهومی پس از هر جلسه کلاس توسط کمک‌مدرس (دروس تئوری و تکنیک تمرین مهارت‌ها).

## متادیتا

- فایل: `metadata/processes/ta_conceptual_questions.json`
- وضعیت: `complete_in_metadata`
- فرم‌ها: آپلود TA (`ta_upload`)، بررسی مدرس (`instructor_review`)، اصلاح (`question_rejected`)

## UI

- پنل راهنما: `admin-ui/src/components/TaConceptualQuestionsPanel.jsx`
- utility نمایش: `admin-ui/src/utils/taConceptualQuestionsDisplay.jsx`
- پورتال: `StaffPortal` — lane `instruction` (مدرس / کمک‌مدرس)
- قالب‌ها (placeholder): `/templates/ta-conceptual-question/sample.pdf` و `template.pdf`

## بک‌اند / اتوماسیون (باقی‌مانده)

- trigger خودکار `class_session_ended` و پر کردن context جلسه
- SLA و `violation_registration` در تأخیر آپلود/بررسی
- آرشیو بانک سوال مرکز مرجع و محاسبه نمره (+۲، سقف ۳۴)

## آخرین به‌روزرسانی

- ۲۰۲۶-۰۶-۲۸: UI panel و فرم‌های instructor_review / question_rejected اضافه شد.
