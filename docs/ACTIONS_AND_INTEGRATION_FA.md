# اکشن‌های انتقال و یکپارچه‌سازی بیرونی

این سند **نحوهٔ استفادهٔ عملی** از لایهٔ `ActionHandler` و ماژول `external_integration` را برای تیم فنی و آموزش کاربران پیشرفته توضیح می‌دهد.

## دو لایهٔ رفتار

1. **اثر داخلی (پایگاه داده / دانشجو)**  
   اکشن‌هایی مثل `activate_therapy`، `create_session_link`، `delete_future_therapy_appointments`، `update_record` مستقیماً روی جداول `students`، `therapy_sessions`، `financial_records`، `attendance_records` یا روی `process_instances.context_data` اثر می‌گذارند.

2. **یکپارچه‌سازی اختیاری (LMS / سامانه بیرونی)**  
   اکشن‌هایی که در متادیتا نام «LMS» یا «ثبت در سامانه» دارند، از تابع `_handle_external_integration` عبور می‌کنند:
   - همیشه یک ردیف در `context_data.integration_events` (روی همان نمونه فرایند) ثبت می‌شود.
   - اگر متغیر محیطی `LMS_INTEGRATION_WEBHOOK_URL` تنظیم شده باشد، یک **POST JSON** با بدنهٔ استاندارد به آن URL فرستاده می‌شود.
   - اگر URL خالی باشد، هیچ درخواست شبکه‌ای زده نمی‌شود (مناسب توسعه و تست محلی).

## قرارداد وب‌هوک (پیشنهادی)

درخواست:

- متد: `POST`
- هدر اختیاری: `X-Integration-Secret` اگر `LMS_INTEGRATION_SECRET` در `.env` مقدار داشته باشد.
- بدنهٔ JSON نمونه:

```json
{
  "event": "integration_action",
  "action_type": "send_unlock_to_lms",
  "instance_id": "...",
  "student_id": "...",
  "process_code": "specialized_commission_review",
  "action": { }
}
```

سامانهٔ مقصد باید `2xx` برگرداند؛ خطا فقط در لاگ سمت سرور ثبت می‌شود و **موتور فرایند را متوقف نمی‌کند** (ترنزیشن قبلاً اعمال شده است).

## payload و context برای اکشن‌های حساس

| اکشن | ورودی مهم |
|------|-----------|
| `create_session_link` | ترجیحاً `meeting_url` در payload ترنزیشن یا `instance.context_data`؛ در غیر این صورت لینک پیش‌فرض از `APP_BASE_URL` ساخته می‌شود. |
| `record_attendance` | `therapy_session_id` / `session_id`، `record_date`، `attendance_status` در context یا payload. |
| `record_absence_auto` | ترجیحاً `therapy_session_id` در context. |
| `add_hour_by_course_and_weekly_sessions` | ضرایب از `weekly_sessions` دانشجو یا از اکشن؛ نتیجه در `context_data.accumulated_therapy_hours`. |
| `update_record` | فیلدهای امتیاز/نتیجه در context (مثلاً `total_score`, `result_status`)؛ در `students.extra_data.gradebook[process_code]` ذخیره می‌شود. |
| `deduct_credit_session` | ابتدا از `session_credit_balance` در context کم می‌کند؛ در نبود اعتبار، بدهی ثبت می‌کند. |
| `create_online_class_links` | اگر `ALOCOM_ENABLED=true` و نام کاربری/رمز الوکام و `agent_service_id` (از اکشن، `context_data` یا `ALOCOM_DEFAULT_AGENT_SERVICE_ID`) موجود باشد، رویداد در الوکام ساخته می‌شود و روی نزدیک‌ترین جلسهٔ `scheduled` (یا جلسهٔ `therapy_session_id` / `session_id`) فیلدهای `meeting_url`، `meeting_provider=alocom`، `links_unlocked`، `alocom_event_id` پر می‌شود. در غیر این صورت با `ALOCOM_FALLBACK_TO_UI_HINTS=true` همان رفتار قبلی (`ui_hints` + وب‌هوک) اجرا می‌شود. فیلدهای اختیاری: `title` / `title_fa`، `duration_minutes`، `start_by_admin`، `session_starts_at` (ISO)، `fetch_student_event_link`. |

## الوکام (کلاس آنلاین)

- متغیرهای محیطی: `ALOCOM_ENABLED`، `ALOCOM_API_BASE`، `ALOCOM_USERNAME`، `ALOCOM_PASSWORD`، `ALOCOM_DEFAULT_AGENT_SERVICE_ID`، مسیرهای اختیاری `ALOCOM_PATH_*` در [`app/config.py`](../app/config.py).
- اپراتور/درمانگر می‌تواند بدون ترنزیشن از `POST /api/integrations/alocom/therapy-sessions/{session_id}/provision` استفاده کند.
- ثبت حضور و نظر مدرس: `PATCH /api/therapy-sessions/{id}` با `attendance_status` و `instructor_comment` / `instructor_score` (نقش‌های `therapist`، `staff`، `admin` طبق دسترسی).

## تست خودکار

- `tests/services/test_action_handler.py` — رفتار اصلی فعال‌سازی درمان، مسدودسازی کلاس، پرداخت جلسه.
- برای اکشن‌های جدید، همان الگو را با `ProcessInstance` و `Student` فیکسچرها تکرار کنید.

## نکات آموزشی برای بهره‌برداری

- قبل از اتصال وب‌هوک به LMS واقعی، با **URL خالی** فقط `integration_events` را در API داشبورد نمونه (`GET .../dashboard`) بررسی کنید.
- برای هر اکشن «نمایشی» (مثل `display_mandatory_message`) فیلد `ui_hints` روی همان نمونه پر می‌شود تا فرانت بتواند پیام را بدون منطق سخت‌کد نشان دهد.
