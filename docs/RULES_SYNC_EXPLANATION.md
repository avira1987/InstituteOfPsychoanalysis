# چرا تعداد قوانین بعد از اپلود فرایندهای جدید افزایش نیافت؟

## علت

قوانین **فقط** از فایل `metadata/rules/all_rules.json` لود می‌شوند. فرایندها از فایل‌های `metadata/processes/*.json` لود می‌شوند.

وقتی فرایندهای جدید (مثلاً از PDF ۳۳–۵۲) ساخته می‌شوند:
1. فایل JSON فرایند با transitionها و فیلد `conditions` (کدهای قانون) ایجاد می‌شود
2. این کدها در `transition_definitions.condition_rules` ذخیره می‌شوند
3. **اما** قوانین فقط از `all_rules.json` خوانده می‌شوند — هیچ قانونی از خود فرایند استخراج نمی‌شود

بنابراین اگر فرایند جدید به قوانینی مثل `no_active_therapist_registered` یا `within_4_weeks_of_term_start` ارجاع دهد که در `all_rules.json` نباشند، آن قوانین هرگز به `rule_definitions` اضافه نمی‌شوند.

## راه‌حل اعمال‌شده

۱۷ کد قانون که در فرایندها استفاده شده‌اند ولی در `all_rules.json` نبودند، به این فایل اضافه شدند:

- `no_active_therapist_registered`, `active_therapist_registered`
- `admission_type == 'conditional_therapy'`
- `all_comprehensive_subjects_passed`
- `pause_less_than_21_days`, `pause_21_days_or_more`
- `eligible_for_registration`, `has_remaining_comprehensive_courses`
- `installment_not_paid`
- `result == 'conditional_therapy'`, `result == 'full_admission'`, `result == 'rejected'`, `result == 'single_course'`
- `sla_approaching_168h`, `therapy_condition_met_or_not_conditional`
- `within_4_weeks_of_term_start`

بعد از sync، تعداد قوانین از ۸۲ به ۹۸ افزایش می‌یابد.

## توصیه برای آینده

هنگام ساخت فرایندهای جدید از PDF یا منبع دیگر، کدهای قانون استفاده‌شده در `conditions` را هم به `all_rules.json` اضافه کنید تا بعد از sync در دیتابیس ثبت شوند.
