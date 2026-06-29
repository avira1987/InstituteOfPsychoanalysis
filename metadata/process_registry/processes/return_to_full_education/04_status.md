# فرایند ۶۰ — بازگشت به کل آموزش پس از مرخصی

## وضعیت پیاده‌سازی

| لایه | وضعیت |
|------|--------|
| متادیتا | `metadata/processes/return_to_full_education.json` — state machine کامل مطابق SOP |
| بک‌اند | `app/services/return_to_full_education_service.py` + action handlers |
| UI دانشجو | `StudentReturnToFullEducationPanel` + `returnToFullEducationDisplay` |
| پورتال | `StudentPortal.jsx`, `StudentQuestCard.jsx`, `studentProcessAccess.js` |
| پرداخت SEP | `payment_routes.py` — therapy/supervision payment confirmed |
| تست | `tests/processes/test_return_to_full_education_flow.py` |

## جریان

1. دانشجو: `return_request` → `therapist_selection` → پرداخت درمان → (انترن: سوپروایزر + پرداخت) → بازگشایی ثبت‌نام → `return_complete`
2. پیش‌نیاز شروع: تکمیل/فعال بودن مرخصی کل آموزش (فرایند ۵۹)

## UI

- پنل اختصاصی با stepper سه‌فازی، راهنمای فارسی، و `SepPaymentPanel`
- CTA داشبورد: «شروع بازگشت به کل آموزش»

## نواقص احتمالی آینده

- اتصال لیست پویا سوپروایزرها (شیت وقت‌های آزاد) مشابه انترنی
- SMS templates: `return_therapy_scheduled`, `return_supervision_scheduled`, `return_to_education_complete`
