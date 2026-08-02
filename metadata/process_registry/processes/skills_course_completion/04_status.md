# وضعیت فرایند ۶۳ — خاتمه دروس تکنیک: تمرین مهارت‌ها

**کد:** `skills_course_completion`  
**شماره SOP:** 63  
**آخرین به‌روزرسانی:** 2026-07-18

## وضعیت پیاده‌سازی

| لایه | وضعیت |
|------|--------|
| متادیتا (state machine) | کامل — ۱۰ state |
| Backend | `skills_course_completion_service.py` |
| UI مدرس | `SkillsCourseCompletionPanel` |
| UI دانشجو | `StudentSkillsCourseCompletionPanel` |
| تست | `tests/processes/test_skills_course_completion_flow.py` |

## Stateهای فعال

- `awaiting_session_17` / `session_17_grades_entry` — جلسه ۱۷
- `awaiting_session_18` / `session_18_grades_entry` — جلسه ۱۸
- `ta_evaluation_entry` — ارزیابی TA (در صورت وجود)
- `qualitative_eval_pending` — Q7/Q8
- `grades_locked` — خاتمه

## نگاشت SOP

`metadata/process_registry/sop_step_mappings.json` → `skills_course_completion`
