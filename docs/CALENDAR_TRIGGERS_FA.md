# تریگرهای زمان‌محور (حلقهٔ پس‌زمینه)

سرویس `app/services/calendar_triggers.py` در همان `lifespan` اپ با `calendar_trigger_monitor.start_loop` اجرا می‌شود (فاصله: `CALENDAR_TRIGGER_INTERVAL_SECONDS`).

## چه چیزهایی خودکار اجرا می‌شود؟

| تریگر | شرط | فرایند / وضعیت |
|--------|-----|----------------|
| `payment_timeout` | `session_payment` در `awaiting_payment` و گذشتن از مهلت `sla_hours` همان state (پیش‌فرض ۷۲ ساعت از `last_transition_at`) | → `payment_failed` |
| `send_return_reminder` | `educational_leave` در `on_leave` و `context_data.return_reminder_at` ≤ اکنون | → `return_reminder_sent` |
| `return_deadline_passed` | `return_reminder_sent` و `context_data.return_deadline_at` ≤ اکنون | → `violation_registered` (نیاز به لود فرایند `violation_registration` برای اکشن `start_process`) |
| `session_time_reached` | `attendance_tracking` در `session_scheduled` و `context_data.session_date` ≤ امروز | اولین شاخهٔ سازگار با قوانین |
| `session_time_reached` | `supervision_50h_completion` در `session_scheduled` و `session_date` یا `supervision_session_date` ≤ امروز | همان منطق شاخه‌های متادیتا |
| `installment_due_date_passed` | `intro_second_semester_registration` در `registration_complete`، `pending_installments_remaining` > 0 و `next_installment_due_at` ≤ امروز (تاریخ UTC) | → `installment_overdue` (قانون `installment_not_paid` با `calendar_today` در context موتور) |
| (خودکار) `therapist_did_not_record` | `attendance_tracking` در `therapist_recording` و گذشتن ۲۴ ساعت از نیمه‌شب روز `session_date` | → `site_manager_pending` |

خروجی `run_calendar_trigger_pass`: علاوه بر موارد قبلی، `installment_due_intro_second_semester` و `therapist_did_not_record_attendance` (لیست اجراهای موفق).

## تنظیمات محیط

- `CALENDAR_TRIGGERS_ENABLED=true|false` — غیرفعال کردن کل حلقه (مثلاً در تست واحد بدون پس‌زمینه).
- `CALENDAR_TRIGGER_INTERVAL_SECONDS` — پیش‌فرض ۳۰۰ (هم‌تراز با SLA).

## دادهٔ لازم در `context_data`

برای مرخصی، هنگام فعال‌سازی وقفه (ترنزیشن‌های منتهی به `on_leave`) باید تاریخ‌ها ست شوند؛ در غیر این صورت یادآور و ضرب‌الاج خودکار اجرا نمی‌شود:

- `return_reminder_at` — ISO datetime
- `return_deadline_at` — ISO datetime

برای حضور و غیاب، هنگام شروع نمونه یا قبل از تریگر، `session_date` را به صورت `YYYY-MM-DD` قرار دهید.

برای اقساط ترم دوم آشنایی، پس از پرداخت اول (`merge_instance_context` با حالت `initial_payment`) فیلدهای `pending_installments_remaining` و `next_installment_due_at` در `context_data` ست می‌شوند؛ پس از هر پرداخت قسط (`installment_paid`) سررسید بعدی به‌روز می‌شود. موتور در هر ارزیابی قانون، `instance.calendar_today` را به تاریخ امروز (UTC) تنظیم می‌کند.

## موتور فرایند

برای چند ترنزیشن با یک `trigger_event` (مثل `session_time_reached`)، موتور **به ترتیب priority** اولین شاخه‌ای را اجرا می‌کند که **همهٔ قوانینش** pass شود.

## تست

`tests/services/test_calendar_triggers.py`
