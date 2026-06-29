# وضعیت: فرایند ۷۱ — ارتقا به درمانگر آموزشی

| فیلد | مقدار |
|------|-------|
| **وضعیت** | complete_in_metadata + UI wired |
| **آخرین به‌روزرسانی** | 2026-06-28 |
| **منبع ورودی** | SOP فرایند ۷۱ |

## UI
- [x] گسترش metadata به ~۲۰ state مطابق SOP
- [x] `upgradeToEducationalTherapistDisplay.jsx` + `educationalTherapistUpgradeTriggerPayload.js`
- [x] `StudentEducationalTherapistUpgradePanel` + اتصال StudentPortal / StudentQuestCard
- [x] پنل‌های کمیته: Monitoring / Interview / TherapistReview + CommitteePortal
- [x] `isWaitingForReview` و `portalCommitteeKinds` reviewKeywords
- [x] `educational_therapist_upgrade_service.py` + engine context merge
- [x] قوانین `et_*` در `all_rules.json`
- [x] `test_upgrade_to_educational_therapist_flow.py`

## نواقص بک‌اند (خارج از UI حداقلی)
- [ ] SLA خودکار ۱۰ روزه `therapy_frequency_escalation` در scheduler
- [ ] یکپارچگی کامل شیت وقت‌های آزاد با API اختصاصی (فعلاً فرم/متن)
