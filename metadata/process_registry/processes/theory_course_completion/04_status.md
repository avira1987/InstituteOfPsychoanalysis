# وضعیت فرایند ۶۱ — خاتمه دروس تئوری

**کد:** `theory_course_completion`  
**شماره SOP:** 61  
**آخرین به‌روزرسانی:** 2026-07-18

## وضعیت پیاده‌سازی

| لایه | وضعیت |
|------|--------|
| متادیتا (state machine) | کامل — ۱۰ state، transitions SOP |
| قوانین | `theory_*` در all_rules.json |
| Backend | `theory_course_completion_service.py` + action_handler |
| UI مدرس | `TheoryCourseCompletionPanel` |
| UI دانشجو | `StudentTheoryCourseCompletionPanel` |
| تست | `tests/processes/test_theory_course_completion_flow.py` |

## Stateهای فعال

- `awaiting_session_18` — منتظر جلسه ۱۸ (scheduler)
- `session_18_entry` — مشارکت + بسته آزمون (مدرس، SLA ۲۴h)
- `final_exam_open` / `retake_exam_open` — آزمون دانشجو
- `grades_computed` / `borderline_student_choice` — محاسبه و انتخاب مرزی
- `qualitative_eval_pending` — Q7/Q8 (۴ روز)
- `grades_locked` — خاتمه
- terminals تأخیر + violation sub-process

## نگاشت SOP

`metadata/process_registry/sop_step_mappings.json` → `theory_course_completion`
