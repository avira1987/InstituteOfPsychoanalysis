# فلوچارت: جلسه اضافی سوپرویژن

## Swimlaneها
- **دانشجو:** ثبت درخواست، پرداخت، پاسخ به پیشنهاد
- **سوپروایزر:** تایید / رد+پیشنهاد / عدم امکان، ثبت حضور
- **LMS:** اطلاع‌رسانی، درگاه پرداخت، ثبت، لینک، اتصال به supervision_50h_completion

## مسیرها
- extra_request → supervisor_review (SMS)
- supervisor_review → payment_required (تایید)
- supervisor_review → student_response (پیشنهاد جایگزین)
- supervisor_review → extra_request_rejected (رد کامل)
- student_response → payment_required OR supervisor_review (لوپ)
- payment_required → extra_session_confirmed
- extra_session_confirmed → extra_session_completed (مطابق SOP ۵۰ ساعته)
