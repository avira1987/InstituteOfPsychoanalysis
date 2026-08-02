# تست Flow-Through — مسیر ورود مرکز (Onboarding)

این ترک فقط فرایندهای **ورود اتوماسیون به مرکز** و نقش‌های دخیل را پوشش می‌دهد:

| # | فرایند | نقش‌ها |
|---|--------|--------|
| ۱ | `fall_semester_preparation` | کمیته دروس، معاون آموزش، پذیرش |
| ۲ | `introductory_course_registration` | متقاضی/دانشجو، مصاحبه‌گر، پذیرش |
| ۳ | `introductory_term_end` | پذیرش (پیگیری افت تحصیلی) |

هدف نهایی: دانشجو بتواند **ثبت‌نام کند، وارد سامانه آموزشی شود و ترم پاییز (دوره آشنایی) را تمام کند**.

## ساخت ماتریس

```bash
python -m scripts.flow_through.build_matrix --track onboarding
python -m scripts.flow_through.resolve_ui_surface --track onboarding
```

خروجی: `reports/flow_through/onboarding/matrix_enriched.json`

## تست API

```powershell
$env:FLOW_THROUGH_TRACK='onboarding'
python -m pytest tests/flow_through/test_onboarding_flow.py -q --tb=short
```

فیلتر یک فرایند:

```powershell
$env:FLOW_THROUGH_PROCESS='introductory_course_registration'
python -m pytest tests/flow_through/test_onboarding_flow.py -v
```

## پipeline کامل

```bash
python -m scripts.flow_through.run_pipeline --track onboarding
```

## تست UI (Playwright)

```bash
cd admin-ui
npm run test:onboarding
```

## مسیر UI دانشجو

1. `/login` — ورود OTP یا رمز
2. `/panel/complete-registration` — تکمیل پروفایل
3. `/panel/portal/student` — ثبت‌نام آشنایی، رزرو مصاحبه، مدارک، انتخاب درس
4. تب پروفایل — کارنامه پایان ترم آشنایی

راهنمای دستی: [institute_onboarding_test_guide_fa.md](institute_onboarding_test_guide_fa.md)
