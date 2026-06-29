# وضعیت: زیرفرایند الف — کمیسیون تخصصی

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata |
| **آخرین به‌روزرسانی** | 2026-06-25 |
| **منبع ورودی** | متن بخش ۲ قطع زودرس |

## UI (بخش ۲ — زیرفرایند الف)
- [x] فرم `commission_decision` در metadata/processes/specialized_commission_review.json
- [x] پنل راهنما `SpecializedCommissionReviewPanel.jsx` + اتصال در `CommitteePortal.jsx`
- [x] اعتبارسنجی تصمیم `commissionReviewTriggerPayload.js`
- [x] UI دانشجو `StudentCommitteesRestartPanel` برای مهلت ۵ روز پس از تأیید
- [x] SLA timestamp (`awaiting_restart_entered_at`) در engine

## نواقص بک‌اند (خارج از UI)
- [ ] تداخل کامل با `committees_review` (زیرفرایند ب) در همه سناریوها
