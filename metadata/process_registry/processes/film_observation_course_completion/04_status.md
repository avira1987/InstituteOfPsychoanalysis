# وضعیت فرایند ۶۴ — خاتمه درس عملی کاربردی / مشاهده فیلم

**کد:** `film_observation_course_completion`  
**شماره SOP:** 64  
**آخرین به‌روزرسانی:** 2026-07-18

## وضعیت پیاده‌سازی

| لایه | وضعیت |
|------|--------|
| متادیتا | کامل — ۳ state |
| Backend | `film_observation_course_service.py` (گزارش PDF) |
| UI مدرس | `FilmObservationCourseCompletionPanel` |
| UI دانشجو | `StudentFilmObservationCourseCompletionPanel` + آپلود PDF |
| تست | `tests/processes/test_film_observation_course_completion_flow.py` |

## Stateهای فعال

- `grades_entry` — آپلود گزارش دانشجو + ثبت نمره مدرس (SLA ۷ روز)
- `grades_locked` — خاتمه
- `delay_reported` — terminal

## وابستگی

- `film_observation_ta_attendance_completion` (#75) — مشارکت و حضور

## نگاشت SOP

`metadata/process_registry/sop_step_mappings.json` → `film_observation_course_completion`
