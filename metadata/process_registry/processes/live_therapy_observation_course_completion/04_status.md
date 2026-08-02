# وضعیت فرایند ۶۵ — خاتمه درس مشاهده زنده درمان

**کد:** `live_therapy_observation_course_completion`  
**شماره SOP:** 65  
**آخرین به‌روزرسانی:** 2026-07-18

## وضعیت پیاده‌سازی

| لایه | وضعیت |
|------|--------|
| متادیتا | کامل — فرم آپلود گزارش دانشجو + فرم نمره مدرس |
| Backend | `live_therapy_observation_course_service.py` |
| UI مدرس | `LiveTherapyObservationCourseCompletionPanel` |
| UI دانشجو | `StudentLiveTherapyObservationCourseCompletionPanel` |
| تست | `tests/processes/test_live_therapy_observation_course_completion_flow.py` |

## Stateهای فعال

- `grades_entry` — آپلود PDF + ثبت نمره (SLA ۷ روز)
- `grades_locked` — خاتمه
- `delay_reported` — terminal

## وابستگی

- `live_therapy_observation_ta_attendance_completion` (#74) — مشارکت و حضور

## نگاشت SOP

`metadata/process_registry/sop_step_mappings.json` → `live_therapy_observation_course_completion`
