# وضعیت: پرداخت برای جلسات آتی درمان آموزشی

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-08-06 |
| **منبع ورودی** | فلوچارت + متن ۶ گامی |

## نواقص
- [ ] اکشن‌های سفارشی: zero_debt_if_paid, add_to_credit_balance, allocate_credit_to_sessions, unlock_session_links, unlock_attendance_registration
- [ ] معافیت جلسه اول (در start_therapy انجام می‌شود)

## قوانین اضافه‌شده
- has_debt ✓
- payment_selection_valid ✓

## اصلاح UX بدهی (۲۰۲۶-۰۸-۰۶)
- با وجود بدهی، `debt_settlement_included` خودکار True می‌شود
- بنر بدهی + مبلغ در پنل دانشجو
- مبلغ بدهی در `generate_payment_invoice` به فاکتور اضافه می‌شود
- `error_message_fa` برای payment_selection_valid

## تعریف بدهی (۲۰۲۶-۰۸-۱۰)
- `debt_sessions_count` فقط جلسات `pending` که `completed`اند یا `session_date` قبل از امروز تهران است
- جلسات آیندهٔ `scheduled`/`pending` بدهی نیستند (تقویم ترم پس از آغاز درمان)