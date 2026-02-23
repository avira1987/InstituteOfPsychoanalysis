# فلوچارت: کاهش جلسات هفتگی سوپرویژن

## Swimlaneها
- **دانشجو:** کلیک فرایند، انتخاب جلسات (مسیر الف)، تعیین توالی+روز/ساعت (مسیر ب)، پاسخ به رد سوپروایزر
- **سوپروایزر:** تایید یا رد پیشنهاد کاهش توالی
- **LMS:** بررسی تعداد جلسات، چک صلاحیت، نمایش فرم، ثبت، آزادسازی وقت، ارسال SMS

## تصمیم اول: تعداد جلسات هفتگی؟
- **۲ جلسه یا بیشتر:** initiated → session_selection → multi_reduction_completed
- **کمتر از ۲ جلسه:** به تصمیم دوم

## تصمیم دوم (۱ جلسه): ساعات ۱۵۰/۲۵۰/۷۵۰؟
- **خیر:** initiated → eligibility_blocked
- **بله:** initiated → structure_selection

## مسیر کاهش توالی
- structure_selection → supervisor_review (ورود توالی و روز/ساعت)
- supervisor_review → frequency_reduction_completed (تایید)
- supervisor_review → structure_selection (رد + لوپ)

## مسیر کاهش جلسات متعدد
- session_selection → multi_reduction_completed (انتخاب با حداقل ۱ باقی)
