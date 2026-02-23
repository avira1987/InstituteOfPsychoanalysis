# وضعیت: تکمیل شدن ساعات درمان آموزشی

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-02-14 |
| **منبع ورودی** | فلوچارت + متن ۴ گامی |

## نواقص
- [ ] قانون ویرایش تا ۲۴:۰۰ همان روز (در سرویس)
- [ ] منطق سه فیلد ساعات (۱x، ۲x، مجموع) بر اساس جلسات هفتگی فعال
- [ ] trigger خودکار therapist_did_not_record و site_manager_sla_breach

## قوانین اضافه‌شده
- student_on_leave, session_cancelled, session_not_paid, session_paid ✓
- student_not_on_leave, session_not_cancelled ✓

## نقش جدید
- site_manager ✓
