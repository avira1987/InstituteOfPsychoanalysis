# وضعیت UI — فرایند ۷۰ (thesis_defense_request)

## پیاده‌سازی شده

- metadata: states کامل + forms غربالگری، کمیته‌ها، آپلود پایان‌نامه، مجوز نظارت
- بک‌اند: `thesis_defense_eligibility_service.py` + merge در `engine.py` + prefill در `process_form_prefill.py`
- UI: `thesisDefenseRequestDisplay.jsx`
- پنل دانشجو: `StudentThesisDefenseRequestPanel` + wiring در `StudentPortal.jsx`
- پنل کمیته‌ها: `ThesisDefenseProgressReviewPanel`, `ThesisDefenseSupervisionReviewPanel`, `ThesisDefenseEducationSchedulePanel` + `CommitteePortal.jsx`
- دسترسی شروع: `studentProcessAccess.js` (پیش‌نیاز فرایند ۶۹)
- برچسب‌ها: `processMetadataLabels.js`, `contextInstanceDisplay.jsx`, `operatorFollowupDeepLinks.js`
- پشتیبانی `user_select` در `UnifiedFormRenderer.jsx` (fallback)
- تست flow: `tests/processes/test_thesis_defense_request_flow.py`

## نواقص / بعداً

- فرم نمره داور (`defense_grade_form`) — UI اختصاصی داور / magic-link
- SLA breach `revision_sla_breach` → `violation_registration` (اتوماسیون زمان‌بندی)
- SMS templates برای زمان‌بندی دفاع و ابلاغ اصلاحات
- PDF راهنمای اپراتور (`scripts/generate_*_operator_guide_pdf.py`)
- نگاشت trigger فرم کمیته پیشرفت (`decision` → report_approved / revision_requested / report_rejected) در action_handler
