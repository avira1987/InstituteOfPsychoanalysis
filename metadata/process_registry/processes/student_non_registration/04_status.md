# فرایند ۴۲ — عدم ثبت‌نام دانشجو برای ترم بعد

**وضعیت:** UI + metadata تکمیل‌شده (فرم جلسه + نتیجه)

## UI

| نقش | پنل |
|-----|-----|
| کمیته نظارت | `StudentNonRegistrationReviewPanel` در `CommitteePortal` |
| دانشجو | `StudentNonRegistrationPanel` در `StudentPortal` |

## فرم‌ها

- `non_registration_meeting_schedule` — state `list_generated`
- `non_registration_meeting_result` — state `meeting_held`

## Backend حداقل

- `student_non_registration_chaining.py` — دعوت‌نامه خودکار، مهلت شاخه‌ها، زنجیرهٔ مرخصی/ثبت‌نام
- prefill `weeks_since_start` در `process_form_prefill.py`
- validation trigger در `routes.py`

## خارج از scope فعلی

- SMS templates (`non_registration_meeting_invite_sms`)
- تایمرهای `no_action_*` و انصراف خودکار ۵ روزه
- شروع خودکار `violation_registration`
