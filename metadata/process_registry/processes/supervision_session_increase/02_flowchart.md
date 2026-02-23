# فلوچارت: افزایش جلسات هفتگی سوپرویژن

## Swimlaneها
- **دانشجو:** ثبت درخواست، پاسخ به پیشنهاد جایگزین
- **سوپروایزر:** تایید / رد+پیشنهاد / رد کامل
- **LMS:** اطلاع‌رسانی، اضافه کردن جلسه، اتصال به supervision_50h_completion

## مسیرها
- request_submitted → supervisor_review (SMS)
- supervisor_review → session_added (تایید)
- supervisor_review → student_response (پیشنهاد جایگزین)
- supervisor_review → request_rejected (رد کامل)
- student_response → session_added (تایید پیشنهاد)
- student_response → supervisor_review (ورود زمان جدید — لوپ)
