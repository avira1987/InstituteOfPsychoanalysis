# وضعیت: زیرفرایند ب — کمیته‌های نظارت و آموزش

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-06-25 |
| **منبع ورودی** | فلوچارت + متن بخش ۳ |

## پیاده‌سازی UI
- [x] فرم‌های `supervision_recommendation` و `education_verdict` در `metadata/processes/committees_review.json`
- [x] پنل راهنما `CommitteesReviewPanel.jsx` در `CommitteePortal`
- [x] اعتبارسنجی trigger: `committeesReviewTriggerPayload.js`
- [x] prefill والد در `process_form_prefill.py`
- [x] پنل دانشجو `StudentCommitteesRestartPanel.jsx` (مهلت ۵ روز + CTA `therapy_changes`)
- [x] زنجیره با فرایند ۱۱ (`TherapistEarlyTerminationPanel`) و ۱۲ (`SpecializedCommissionReviewPanel`)

## نواقص بک‌اند (غیر UI)
- [ ] SLA خودکار ۳ و ۶ روز (scheduler)
- [ ] قالب نامه رسمی کامل در production document service
- [ ] patient_referral در صورت انترن بودن — اکشن موجود، تست یکپارچه E2E
