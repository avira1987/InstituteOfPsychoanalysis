# یادداشت فلوچارت

## Swimlaneها
1. متقاضی (applicant)
2. مصاحبه‌گر (interviewer)
3. مسئول پذیرش (admissions_officer)
4. سیستم / LMS (system)

## مسیر اصلی
application_submitted → (timeslot_selected) → interview_payment → (payment_success) → interview_payment_confirmed → (interview_time_reached) → interview_completed → نتیجه مصاحبه → documents_upload → documents_review → credentials_created → course_selection → payment → registration_complete

## نقاط تصمیم
- نتیجه مصاحبه؟ → مشروط به درمان (۱) / تک‌درس (۲) / پذیرش کامل (۳) / رد (۴ → terminal مسدود)
- پرداخت مصاحبه موفق؟ → خیر: بازگشت به interview_payment / بله: ادامه
- مدارک کامل؟ → خیر: documents_incomplete → بازآپلود / بله: credentials_created
- نوع پذیرش تک‌درس؟ → بله: فقط تئوری ۱ و فقط نقدی
- پرداخت شهریه موفق؟ → خیر: بازگشت به payment / بله: registration_complete
- قسط سر موعد پرداخت شد؟ → خیر: installment_overdue (مسدودی حضور) / بله: ادامه

## اکشن‌های کلیدی
- اعلان‌های پیامکی/درون‌پنلی مصاحبه (آنلاین/حضوری) به متقاضی و مصاحبه‌گر
- یادآوری زمان‌بندی‌شده ۲ ساعت قبل از مصاحبه
- پیامک‌های ۴ حالت نتیجه + مسدودسازی فرم آینده برای ردشدگان
- ارسال فهرست مدارک و فهرست نواقص
- ایجاد حساب کاربری LMS و ارسال اعتبارنامه
- ثبت دروس در پورتال + ایجاد لینک کلاس آنلاین
- زمان‌بندی یادآوری اقساط و مسدودی/رفع مسدودی حضور بر اساس تسویه
