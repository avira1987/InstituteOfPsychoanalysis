# وضعیت: complete

**آخرین به‌روزرسانی:** 2026-06-28

## خلاصه

فرایند ۶۶ (`live_therapy_observation_session_prep`) — مقدمات برگزاری جلسات مشاهده زنده درمان.

## UI

| بخش | وضعیت | مسیر |
|-----|--------|------|
| پنل راهنما (پذیرش + هماهنگی) | ✅ | `admin-ui/src/components/LiveSessionPrepPanel.jsx` |
| فرم‌های اپراتور | ✅ | `OperatorStepFormsSection` |
| payload ترنزیشن | ✅ | `admin-ui/src/utils/liveSessionPrepTriggerPayload.js` |
| deep link | ✅ | `operatorFollowupDeepLinks.js` |
| lane پذیرش / هماهنگی | ✅ | `portalStaffLanes.js` |

## متادیتا

- `therapist_id` و `required` روی فیلدهای ارجاع/زمان‌بندی
- actionهای `record_session_prep` + SMS (`live_therapy_observation_session_confirmed`)

## بک‌اند

- `session_time_registered` در engine و action_handler
- پیامک به instructor / teaching_assistant / class_students

## تست

- `tests/processes/test_live_therapy_observation_session_prep_flow.py`

## نواقص / وابستگی‌ها

- شروع فرایند همچنان به `student_id` وابسته است (StudentTracker یا پنل کارمند)
- SMS به `class_students` نیاز به `course_code` از تخصیص مدرس دارد
