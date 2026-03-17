# لیست یکپارچهٔ ادامهٔ ساخت اتوماسیون فرایندها

**منابع:** `metadata/process_registry/GAPS.json` + تحلیل کد (موتور، ActionHandler، قوانین، SLA، فرایندهای JSON)  
**آخرین به‌روزرسانی:** 2026-03-12

---

## الف) فرایندهای فرعی بدون تعریف (اولویت بالا)

| # | کد فرایند | هدف | زمان تریگر | ارجاع‌دهنده‌ها |
|---|-----------|-----|------------|-----------------|
| 1 | **violation_registration** | ثبت تخلف | رد وقفه، عدم بازگشت از مرخصی، کاهش به ۱ جلسه بدون تکمیل، غیبت بدون اطلاع، کنسلی >۱۲٪، ... | educational_leave, therapy_session_reduction, therapy_early_termination, unannounced_absence_reaction, therapy_interruption, student_session_cancellation, supervision_50h_completion, internship_*, student_non_registration, ta_conceptual_questions, mentor_private_sessions |
| 2 | **patient_referral** | ارجاع بیماران انترن | وقفه ≥۴۲ روز، تایید وقفه ۲ ترمی انترن، قطع در committees_review، عدم بازگشت در پایان وقفه کوتاه | educational_leave, committees_review, therapy_interruption, supervision_interruption |

**کارهای لازم:** تعریف states/transitions در `metadata/processes/violation_registration.json` و `patient_referral.json`؛ اضافه به seed؛ پیاده‌سازی اکشن‌های مرتبط.

---

## ب) اکشن‌ها: بدون هندلر یا فقط استاب

### ب-۱) اکشن‌های بدون ثبت در ActionHandler._registry

- `block_class_access`, `activate_therapy` (start_therapy)
- `generate_payment_invoice`, `zero_debt_if_paid`, `allocate_credit_to_sessions`, `unlock_session_links`, `unlock_attendance_registration`, `suspend_sessions` (session_payment)
- `record_absence_auto`, `record_attendance`, `add_hour_by_course_and_weekly_sessions`, `notify_committee` (attendance_tracking)
- `redirect_to_process`, `display_available_supervisor_slots`, `display_mandatory_message`, `apply_24h_rule_for_start_date`, `display_calculated_start_date` (supervision_block_transition)
- `register_new_supervision_block_in_lms`, `enable_attendance_for_new_supervisor`, `create_online_link_50th`, `enable_attendance_for_current_supervisor_50th`
- `cancel_supervision_session`, `add_supervision_credit_if_paid`, `register_supervision_makeup_session`, `enable_attendance_registration` (supervisor_session_cancellation)
- `move_therapist_to_past`, `record_result_in_student_portal`, `ensure_therapist_slots_freed` (unannounced_absence_reaction)
- `move_ta_to_instructor`, `upgrade_rank_to_assistant_faculty`, `unlock_next_course_in_track` (ta_to_assistant_faculty)
- `publish_courses_to_website`, `publish_academic_calendar_to_profiles` (fall_semester_preparation)
- `show_popup`, `load_available_courses`, `register_courses_in_portal`, `create_online_class_links`, `schedule_installment_reminders`, `block_attendance_registration`, `notify_instructor`, `unblock_attendance_registration` (intro_second_semester_registration)

### ب-۲) اکشن‌های با هندلر استاب (باید با منطق واقعی پر شوند)

| فرایند | اکشن‌ها |
|--------|---------|
| start_therapy | resolve_access_restrictions, create_session_link |
| session_payment | zero_debt_if_paid, add_to_credit_balance, allocate_credit_to_sessions, unlock_session_links, unlock_attendance_registration |
| fee_determination | add_to_credit_balance, forfeit_session_payment, create_debt_or_deduct_credit, increment_absence_counter |
| attendance_tracking | add_hour_by_course_and_weekly_sessions |
| therapy_completion | delete_future_therapy_appointments, release_therapist_slots_to_available_sheet, update_therapy_status |
| therapy_session_increase | add_recurring_therapy_session |
| therapy_session_reduction | remove_selected_therapy_sessions, release_therapist_slots_to_available_sheet, record_therapy_change_history |
| therapy_early_termination | log_termination_request, mark_therapy_relationship_terminated, release_therapist_slots, set_student_status, call_bpms_subprocess |
| specialized_commission_review | send_unlock_to_lms, unlock_student_therapist_selection, record_commission_result |
| committees_review | store_nezarat_recommendation, deactivate_student_account, generate_termination_letter, patient_referral |
| therapist_session_cancellation | cancel_session, add_credit_if_paid, deduct_credit_session, register_makeup_session, enable_online_session_link |
| unannounced_absence_reaction | release_therapist_slots, move_therapist_to_past |
| supervisor_session_cancellation | cancel_supervision_session, add_supervision_credit_if_paid, register_supervision_makeup_session, enable_attendance_registration, activate_online_session_link |
| supervision_interruption | release_supervisor_slot, move_supervisor_to_past_list, record_interruption_dates, monitor_return_at_end_date, run_patient_referral |
| supervision_block_transition | remove_slot_from_available, unlock_payment_for_50th_session, display_supervision_history |
| supervision_50h_completion | send_45_48_reminder_if_applicable, unlock_payment_for_50th_session |
| student_session_cancellation | mark_sessions_cancelled_by_student, block_attendance_for_cancelled_sessions |

---

## ج) تریگرهای زمان‌محور و SLA

### ج-۱) تریگرهای خودکار (نیاز به cron/job)

- `session_time_reached` (attendance_tracking, supervision_50h_completion)
- `therapist_did_not_record`, `site_manager_sla_breach` (attendance_tracking)
- `sla_breach_7days` (educational_leave)
- `sla_5days_breach` (specialized_commission_review)
- `payment_timeout` (session_payment)
- `conditional_intern_enters_month_12` / `alert_sent` (internship_12month_conditional_review)
- `leave_activated`, `return_deadline_passed`, `send_return_reminder` (educational_leave)
- `upload_after_24h`, `class_session_ended` (ta_conceptual_questions)
- `evaluation_sla_breach`, `supervisor_did_not_record` (supervision_50h_completion)
- `installment_due_date_passed` (intro_second_semester_registration)

### ج-۲) یکپارچه‌سازی SLA با موتور

- SLA breach: ارسال به deputy_education با قالب committee_sla_breach (نه همیشه admin).
- پس از breach: در صورت وجود `on_sla_breach_event` در state، فراخوانی `engine.execute_transition(..., trigger_event=on_sla_breach_event)`.
- استارت `sla_monitor.start_monitoring_loop` در startup اپ یا worker.

---

## د) Context و قوانین (Rule Engine)

فیلدهای مورد نیاز در context برای ارزیابی قوانین:

| فیلد | کاربرد |
|------|--------|
| instance.current_week | week_9_deadline و مشابه |
| instance.absences_this_year | absence_quota_not_exceeded / exceeded |
| instance.absence_quota | همان (formula: ceil(weekly_sessions*3)، سال شمسی) |
| instance.completed_hours, instance.required_hours | therapy_hours_completed و تکمیل درمان/سوپرویژن |
| instance.hours_until_first_slot | 24_hour_rule |

**کار:** گسترش `engine._build_context` (یا سرویس context enricher) برای پر کردن این فیلدها. در rule_engine مقدار `value` در مقایسه‌ها در صورت مسیر فیلد (مثل `instance.absence_quota`) از context حل می‌شود.

---

## ه) جریان‌های فرایندی و ماژول‌های بزرگ

- جریان‌های ترمی و ثبت‌نام (fall_semester_preparation، winter_semester_preparation، introductory_*، comprehensive_*، intro_second_semester_registration)
- جریان‌های درمان آموزشی (start_therapy، extra_session، therapy_completion، therapy_session_increase، therapy_session_reduction، therapy_early_termination، return_to_full_education)
- جریان‌های سوپرویژن و کمیته‌ها (supervision_50h_completion، supervision_block_transition، supervision_interruption، committees_review، specialized_commission_review)
- جریان‌های TA (upgrade_to_ta، ta_track_completion، ta_conceptual_questions، ta_essay_upload، ta_blog_content، ta_student_consultation، ta_instructor_leave، ta_track_change، ta_to_instructor_auto)
- سایر جریان‌های مکمل (student_session_cancellation، unannounced_absence_reaction، fee_determination، attendance_tracking، class_attendance، extra_supervision_session، internship_*، completion_* و evaluation_*)

---

## و) زیرساخت و یکپارچه‌سازی

- درگاه پرداخت → تایید به session_payment (trigger_event payment_successful/unsuccessful) — انجام‌شده؛ تست‌های callback (موفق و ناموفق) در `tests/test_payment_callback_session_payment.py`.
- تمپلیت‌ها و resolve contact: تمپلیت‌ها در notification_service؛ `_resolve_contact` در action_handler برای نقش‌ها؛ در صورت نیاز برای همه نقش‌ها گسترش داده شود.
- اکشن‌ها فعلاً مستقیم در موتور (ActionHandler.handle_actions) اجرا می‌شوند؛ event_bus برای publish transition/action (نوتیفیکیشن و یکپارچه‌سازی) استفاده می‌شود. در صورت انتقال اجرای اکشن به event_bus، subscriber برای اجرای واقعی اضافه شود.

---

## ز) UI / API

- رندر فرم‌های متادیتا و ارسال با payload به trigger — انجام‌شده: GET definitions/{code}/forms، GET {id}/dashboard، POST {id}/trigger با payload؛ تست‌های واحد و API در `tests/test_process_ui_api.py`.
- دکمه‌های transition بر اساس get_available_transitions و نقش — API: GET {id}/transitions و داشبورد شامل transitions.
- شروع فرایند با context اولیه؛ نمایش state و تاریخچه در داشبوردها — API: POST /start با initial_context؛ GET {id}/status و GET {id}/dashboard برای state و تاریخچه.

---

## ط) ترتیب پیشنهادی برای ادامه ساخت

1. فرایندهای فرعی (violation_registration، patient_referral)
2. اکشن‌ها (بدون هندلر سپس پر کردن استاب‌ها)
3. Context و قوانین
4. SLA و تریگرهای زمان‌محور
5. جریان‌های بزرگ
6. درگاه و اعلان
7. UI/API

---

## وضعیت پیاده‌سازی (برای تیک زدن)

- [x] الف-۱: violation_registration (JSON با transitions + لود توسط seed + تست)
- [x] الف-۲: patient_referral (JSON + لود توسط seed + تست)
- [x] ب (بخشی): اکشن‌های activate_therapy، block_class_access، resolve_access_restrictions (واقعی)؛ اکشن‌های session_payment (generate_payment_invoice، zero_debt_if_paid، allocate_credit_to_sessions، unlock_session_links، unlock_attendance_registration، suspend_sessions) با استاب در ActionHandler + تست
- [x] ج (بخشی): SLA breach → deputy_education + committee_sla_breach؛ اجرای transition با on_sla_breach_event + تست (شامل تست فراخوانی execute_transition هنگام breach_event)
- [x] ج (بخش ۴): استارت sla_monitor.start_monitoring_loop در lifespan اپ؛ توقف در shutdown + تست
- [x] د: غنی‌سازی context در engine (absence_quota، absences_this_year، completed_hours، required_hours، current_week، hours_until_first_slot) + تست — بخش ۳
- [x] ه (بخش ۵): جریان آماده‌سازی ترم پاییز (fall_semester_preparation) — لود، استارت، transition تا tuition_entry + تست
- [x] ه (بخش ۸): جریان ثبت‌نام دوره آشنایی (introductory_course_registration) — لود، استارت، transition تا interview_scheduled + تست
- [x] ه (بخش ۹): جریان پایان ترم آشنایی (introductory_term_end) — لود، استارت، transition تا transcript_generated + تست
- [x] ه (بخش ۱۰): جریان ثبت‌نام ترم دوم آشنایی (intro_second_semester_registration) — لود، استارت، transitions از eligibility_check + تست
- [x] ه (بخش ۱۱): جریان خاتمه دوره آشنایی (introductory_course_completion) — لود، استارت، transition تا invitation_sent + تست
- [x] ه (بخش ۱۲): جریان ثبت‌نام در دوره جامع (comprehensive_course_registration) — لود، استارت، transitions از application_submitted + تست
- [x] ه (بخش ۱۳): جریان پایان ترم جامع (comprehensive_term_end) — لود، استارت، transitions تا graduation_check و دو شاخه completed_all_courses / registration_notification_sent + تست
- [x] ه (بخش ۱۴): جریان آغاز ترم دوره جامع (comprehensive_term_start) — لود، استارت، transitions تا registration_complete + تست
- [x] ه (بخش ۱۵): جریان آغاز هر درس در هر ترم (lesson_start_per_term) — لود، استارت، transitions تا lesson_active + تست
- [x] ه (بخش ۱۶): جریان آماده‌سازی ترم زمستان (winter_semester_preparation) — لود، استارت، transitions تا published + تست
- [x] ه (بخش ۱۷): جریان ارتقا به کمک‌مدرس (upgrade_to_ta) — لود، استارت، transitions تا ta_registered + تست
- [x] ه (بخش ۱۸): جریان جلسه اضافی درمان آموزشی (extra_session) — لود، استارت، transitions تا extra_session_completed + تست
- [x] ه (بخش ۱۹): جریان کنسل جلسه توسط درمانگر (therapist_session_cancellation) — لود، استارت، transitions تا cancelled_no_make_up + تست
- [x] ه (بخش ۲۰): جریان کنسل جلسه توسط سوپروایزر (supervisor_session_cancellation) — لود، استارت، transitions تا cancelled_no_makeup + تست
- [x] ه (بخش ۲۱): جریان کنسل جلسات کلاس درسی (class_session_cancellation) — لود، استارت، transition تا makeup_scheduled + تست
- [x] ه (بخش ۲۲): جریان خاتمه رسته کمک‌مدرس (ta_track_completion) — لود، استارت، transition تا track_completed + تست
- [x] ه (بخش ۲۳): جریان بازگشت به کل آموزش پس از مرخصی (return_to_full_education) — لود، استارت، transitions تا return_approved + تست
- [x] ه (بخش ۲۴): جریان مرخصی آموزشی (educational_leave) — لود، استارت، transitions تا rejected + تست
- [x] ه (بخش ۲۵): جریان آغاز درمان (start_therapy) — لود، استارت، transition تا therapy_active + تست
- [x] ه (بخش ۲۶): جریان تکمیل درمان (therapy_completion) — لود، استارت، transition تا therapy_completed + تست
- [x] ه (بخش ۲۷): جریان افزایش جلسات درمان (therapy_session_increase) — لود، استارت، transitions تا session_added + تست
- [x] ه (بخش ۲۸): جریان کاهش جلسات درمان (therapy_session_reduction) — لود، استارت، transition تا reduction_completed + تست
- [x] ه (بخش ۲۹): جریان قطع زودرس درمان (therapy_early_termination) — لود، استارت، transitions تا restart_completed + تست
- [x] ه (بخش ۳۰): جریان تکمیل ۵۰ ساعت سوپرویژن (supervision_50h_completion) — لود، استارت، transition تا evaluation_completed + تست
- [x] ه (بخش ۳۱): جریان انتقال بلوک سوپرویژن (supervision_block_transition) — لود، استارت، transition تا both_paid_completed + تست
- [x] ه (بخش ۳۲): جریان وقفه سوپرویژن (supervision_interruption) — لود، استارت، transitions تا rejected + تست
- [x] ه (بخش ۳۳): جریان بررسی کمیته‌ها (committees_review) — لود، استارت، transitions تا education_terminated + تست
- [x] ه (بخش ۳۴): جریان بررسی کمیسیون تخصصی (specialized_commission_review) — لود، استارت، transition تا referred_to_committees + تست
- [x] ه (بخش ۳۵): جریان سوالات مفهومی TA (ta_conceptual_questions) — لود، استارت، transitions تا questions_approved + تست
- [x] ه (بخش ۳۶): جریان جستار و دقایق فیلم TA (ta_essay_upload) — لود، استارت، transitions تا approved_reference_center + تست
- [x] ه (بخش ۳۷): جریان محتوای وبلاگ TA (ta_blog_content) — لود، استارت، transitions تا approved_marketing_draft + تست
- [x] ه (بخش ۳۸): جریان شناسایی و مشاوره دانشجویی TA (ta_student_consultation) — لود، استارت، transitions تا form_submitted + تست
- [x] ه (بخش ۳۹): جریان مرخصی کمک‌مدرس/مدرس (ta_instructor_leave) — لود، استارت، transitions تا leave_approved + تست
- [x] ه (بخش ۴۰): جریان تغییر/افزودن رسته کمک‌مدرس (ta_track_change) — لود، استارت، transitions تا track_applied + تست
- [x] ه (بخش ۴۱): جریان ارتقای خودکار کمک‌مدرس به مدرس (ta_to_instructor_auto) — لود، استارت، transition تا upgrade_applied + تست
- [x] ه (بسته انترنشیپ ۱): جریان مشاوره آمادگی انترنی (internship_readiness_consultation) — لود، استارت، transitions تا internship_started + تست
- [x] ه (بسته انترنشیپ ۲): جریان بازبینی ۱۲ ماهه انترنی مشروط (internship_12month_conditional_review) — لود، استارت، transitions تا result_unrestricted + تست
- [x] ه (بسته انترنشیپ ۳): جریان افزایش ساعات انترن (intern_hours_increase) — لود، استارت، transitions تا hours_increased + تست
- [x] ه (بسته completion ۱): خاتمه درس تکنیک تمرین مهارت‌ها (skills_course_completion) — لود، استارت، transition تا grades_locked + تست
- [x] ه (بسته completion ۲): خاتمه دروس تئوری (theory_course_completion) — لود، استارت، transition تا grades_locked + تست
- [x] ه (بسته completion ۳): خاتمه درس مشاهده فیلم و عملی کاربردی (film_observation_course_completion) — لود، استارت، transition تا grades_locked + تست
- [x] ه (بسته completion ۴): خاتمه درس سوپرویژن گروهی (group_supervision_course_completion) — لود، استارت، transition تا grades_locked + تست
- [x] ه (بسته completion ۵): خاتمه درس مشاهده زنده درمان (live_therapy_observation_course_completion) — لود، استارت، transition تا grades_locked + تست
- [x] ه (بسته evaluation ۱): ارزیابی نهایی کمک‌مدرس در سوپرویژن زنده (live_supervision_ta_evaluation) — لود، استارت، transitions تا passed + تست
- [x] ه (بسته evaluation ۲): ارزیابی دانشجو از مدرسین (student_instructor_evaluation) — لود، استارت، transition تا evaluation_closed + تست
- [x] و (بخش ۶): درگاه پرداخت → callback و session_payment (payment_successful/unsuccessful)، PaymentPending، تست
- [x] ز (بخش ۷): UI/API — فرم‌های متادیتا (GET definitions/{code}/forms)، داشبورد instance (GET {id}/dashboard: status+transitions+forms)، تست
