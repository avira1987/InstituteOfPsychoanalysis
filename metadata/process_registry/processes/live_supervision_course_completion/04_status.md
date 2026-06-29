# وضعیت فرایند ۶۷ — خاتمه درس سوپرویژن زنده

**کد:** `live_supervision_course_completion`  
**شماره SOP:** 67  
**آخرین به‌روزرسانی:** 2026-06-28

## وضعیت پیاده‌سازی

| لایه | وضعیت |
|------|--------|
| متادیتا (state machine) | کامل — ۸ state، transitions SOP |
| قوانین | `live_supervision_*` در all_rules.json |
| Backend | `live_supervision_course_service.py` + action_handler |
| UI مدرس | LiveSupervisionCourseCompletionPanel، DualAttendancePanel، MirrorEval، FinalEval |
| UI دانشجو | StudentLiveSupervisionCoursePanel، MirrorWritePanel |
| تست | `tests/processes/test_live_supervision_course_completion_flow.py` |

## Stateهای فعال

- `sessions_in_progress` — کلاس فعال
- `mirror_implementation_pending` — پیاده‌سازی پشت‌آینه (دانشجو، SLA ۵ روز)
- `mirror_eval_pending` — ارزیابی ۳ جلسه پشت‌آینه (مدرس)
- `final_eval_pending` — ارزیابی نهایی Q7/Q8 (مدرس، SLA ۱ روز)
- `completed` — خاتمه
- violation terminals + sub_process violation_registration

## وابستگی‌ها

- فرایند ۵۴ `class_attendance` با `course_type=live_supervision` — حضور دوگانه
- فرایند ۶۸ `live_supervision_session_prep` — زمان‌بندی پشت‌آینه (لینک از داشبورد)
- فرایند ۷۳ `live_supervision_ta_evaluation` — ارزیابی کمک‌مدرس پس از ۱۸ جلسه

## داده LMS

`extra_data.lms.live_supervision[course_code]` — normal_count، mirror_count، compensation_pending، ...
