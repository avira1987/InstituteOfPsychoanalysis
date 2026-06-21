# تریگرهای زمان‌محور (حلقهٔ پس‌زمینه)

سرویس `app/services/calendar_triggers.py` در همان `lifespan` اپ با `calendar_trigger_monitor.start_loop` اجرا می‌شود (فاصله: `CALENDAR_TRIGGER_INTERVAL_SECONDS`).

در انتهای هر دور، `app/services/process_scheduler.py` (`run_process_scheduler_pass`) نیز فراخوانی می‌شود.

## تریگرهای calendar_triggers (موجود)

| تریگر | شرط | فرایند / وضعیت |
|--------|-----|----------------|
| `payment_timeout` | `session_payment` / `extra_session` — گذشت SLA | → `payment_failed` / … |
| `send_return_reminder` | `educational_leave` / `on_leave` + `return_reminder_at` | → `return_reminder_sent` |
| `return_deadline_passed` | `return_reminder_sent` + `return_deadline_at` | → تخلف / `violation_registration` |
| `session_time_reached` | `attendance_tracking` / `supervision_50h_completion` | شاخهٔ متادیتا |
| `therapist_did_not_record` | ۲۴س پس از `session_date` | → `site_manager_pending` |

## passهای process_scheduler (فرایندهای دسته ۳)

| pass | شرط | فرایندها |
|------|-----|----------|
| `scheduled_reminders` | `student.extra_data.scheduled_reminders[].due_at` ≤ اکنون | یادآوری اقساط، mentor، return_monitor |
| `installment_overdue` | `registration_complete` + `next_installment_due_at` ≤ امروز | `introductory_course_registration`, `comprehensive_course_registration`, `intro_second_semester_registration` |
| `generic_sla_triggers` | گذشت `sla_hours` state + trigger `sla_breach` / `deadline_passed` / `sla_expired` | خاتمه دروس، TA consultation، article_writing، آماده‌سازی ترم |
| `academic_term_batch` | `InstituteCalendar` فعال | `student_non_registration`, `student_instructor_evaluation`, `comprehensive_term_start/end`, `introductory_term_end`, `lesson_start_per_term` |
| `student_milestones` | `intern_start_date`, flags LMS | `intern_hours_increase`, `internship_12month_conditional_review`, `ta_to_instructor_auto` |
| `start_therapy_week9` | `current_week >= 9` در `eligibility_check` | `start_therapy` → `week9_blocked` |
| `lms_session_hooks` | `lms.course_sessions[]` | `ta_student_consultation`, `mentor_private_sessions`, `class_attendance` |
| `semester_prep_starts` | ۱۵–۲۰ فروردین (پاییز) یا پنجرهٔ ۳۰روزه قبل از `winter_start_date` | `fall_semester_preparation`, `winter_semester_preparation` (anchor `INST-OPS`) |

فهرست متادیتا: `metadata/scheduled_automation_index.json`

## آماده‌سازی ترم (زیرساخت ۲۰۲۶-۰۶)

| قابلیت | مسیر |
|--------|------|
| لنگر عملیاتی | `INST-OPS` — `app/services/institute_operational_anchor.py` |
| شروع دستی | `POST /api/admin/semester-prep/start` + UI `/panel/semester-prep` |
| شروع خودکار | `dispatch_semester_prep_starts` در `process_scheduler.py` |
| چک روزانه SLA | `daily_overdue_check_service` — kind `semester_prep_sla` / `prep_calendar_deadline` |
| نقش→کاربر | `app/services/process_role_user_resolver.py` |

## موتور چک روزانه کارهای عقب‌افتاده

سرویس `app/services/daily_overdue_check_service.py` در **انتهای هر دور** `run_calendar_trigger_pass` (پس از ساعت ۸ صبح Asia/Tehran) یک‌بار در روز اجرا می‌شود:

| مرحله | عمل |
|--------|-----|
| شناسایی | SLA گذشته، قسط معوق، مهلت context، حضور درمان ۲۴س، تکلیف بدون نمره |
| SMS | قالب `daily_overdue_reminder` (مکمل sla_monitor) |
| پنل | جدول `panel_task_reminders` + merge در `action-notifications` |
| گزارش | جدول `daily_overdue_run_logs` + تب «چک روزانه» در AutomationScheduler |

API:
- `POST /api/admin/scheduler/run-daily-overdue` — اجرای دستی (admin)
- `GET /api/admin/scheduler/daily-overdue-runs` — گزارش اجراها
- `POST /api/panel/task-reminders/{id}/dismiss` — بستن اعلان

## تقویم آموزشی

جدول `institute_calendars` — پر می‌شود از اکشن `publish_academic_calendar_to_profiles` یا API ادمین `PUT /api/admin/academic-calendar/active`.

## تنظیمات محیط

- `CALENDAR_TRIGGERS_ENABLED=true|false`
- `CALENDAR_TRIGGER_INTERVAL_SECONDS` — پیش‌فرض ۳۰۰
- `DAILY_OVERDUE_CHECK_ENABLED=true|false`
- `DAILY_OVERDUE_CHECK_LOCAL_HOUR` — پیش‌فرض ۸ (Asia/Tehran)
- `DAILY_OVERDUE_CHECK_TZ` — پیش‌فرض `Asia/Tehran`

## تست

- `tests/services/test_calendar_triggers.py`
- `tests/services/test_process_scheduler.py`
