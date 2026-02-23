# وضعیت: تعیین تکلیف هزینه جلسه درمان آموزشی/سوپرویژن فردی

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-02-14 |
| **منبع ورودی** | فلوچارت + متن ۵ گامی |

## نواقص
- [ ] اکشن add_to_credit_balance
- [ ] اکشن forfeit_session_payment
- [ ] اکشن create_debt_or_deduct_credit
- [ ] اکشن increment_absence_counter
- [ ] trigger دانشجو کنسل کرد (student_cancelled_session)
- [ ] محاسبه پویای سهمیه با تغییر برنامه

## قوانین اضافه‌شده
- session_cancelled_by_provider ✓
- absence_quota, absence_quota_not_exceeded, absence_quota_exceeded ✓
