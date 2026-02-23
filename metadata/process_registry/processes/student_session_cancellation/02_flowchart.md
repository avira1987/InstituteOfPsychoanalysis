# فلوچارت: کنسل کردن جلسات توسط دانشجو

## Swimlaneها
- **دانشجو:** انتخاب جلسات، تایید نهایی
- **LMS:** نمایش تقویم، اعتبارسنجی، ثبت، گزارش

## گره‌های تصمیم
1. **آیا با این انتخاب کنسلی به ۳ هفته متوالی ختم می‌شود؟** بله → پیام خطا، مسدود
2. **درصد کنسلی چند است؟** <۱۰٪ | ۱۰–۱۲٪ | >۱۲٪

## مسیرها
- **consecutive_blocked:** نمایش پیام، پایان
- **cancellation_applied (<۱۰٪):** فقط fee_determination
- **warning_and_applied (۱۰–۱۲٪):** violation_registration (هشدار) + fee_determination
- **violation_and_applied (>۱۲٪):** violation_registration (تخلف) + fee_determination
