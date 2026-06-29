# وضعیت فرایند ۶۲ — خاتمه هر درس سوپرویژن گروهی

**کد:** `group_supervision_course_completion`  
**شماره SOP:** 62  
**آخرین به‌روزرسانی:** 2026-06-29

## وضعیت پیاده‌سازی

| لایه | وضعیت |
|------|--------|
| متادیتا (state machine) | کامل — ۸ state، transitions SOP |
| قوانین | `group_supervision_*` در all_rules.json |
| Backend | `group_supervision_course_completion_service.py` + action_handler |
| UI مدرس | GroupSupervisionCourseCompletionPanel |
| UI دانشجو | StudentGroupSupervisionCourseCompletionPanel |
| تست | `tests/processes/test_group_supervision_course_completion_flow.py` |

## Stateهای فعال

- `awaiting_session_18` — منتظر جلسه ۱۸
- `session_18_pass_fail_entry` — Pass/Fail (مدرس، SLA ۲۴h)
- `pass_fail_applied` — اعمال ساعات (+۳۳.۳۳۳۳)
- `ta_evaluation_entry` — ارزیابی TA (در صورت وجود)
- `qualitative_eval_pending` — Q7/Q8 (۴ روز)
- `grades_locked` — خاتمه
- `session_18_delay` / `qualitative_eval_delay` — terminals + violation sub-process

## داده LMS

`extra_data.lms.group_supervision_hours` — جمع ساعات (سقف ۱۰۰)  
`extra_data.lms.group_supervision[course_code]` — وضعیت هر درس
