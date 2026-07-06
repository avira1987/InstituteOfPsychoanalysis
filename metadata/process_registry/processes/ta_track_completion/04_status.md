# وضعیت پیاده‌سازی — ta_track_completion (SOP 52)

## متادیتا و جریان
- [x] `metadata/processes/ta_track_completion.json` — فرایند خودکار، بدون فرم
- [x] تست جریان: `tests/processes/test_ta_track_completion_flow.py`
- [x] `ui_requirements.dashboard` در متادیتا

## Backend
- [x] `app/services/ta_track_portfolio_service.py` — تجمیع `extra_data.ta_portfolio`
- [x] `update_record` در `action_handler` برای ثبت `completed_tracks` هنگام transition
- [x] `GET /api/students/me/ta-portfolio`
- [x] `GET /api/students/{id}/ta-portfolio`
- [x] غنی‌سازی `GET /process/{id}/dashboard` با `ta_portfolio`
- [x] `tests/services/test_ta_track_portfolio_service.py`

## UI (admin-ui)
- [x] `taTrackCompletionDisplay.jsx`
- [x] `TaTrackPortfolioPanel.jsx`
- [x] `TaTrackCompletionInstancePanel.jsx`
- [x] `StudentTaTrackPortfolioSection.jsx` — پروفایل دانشجو
- [x] `InstructionTaPortfolioPanel.jsx` — instruction lane مدرس/کمک‌مدرس
- [x] سیم‌کشی: `StudentPortal`, `StaffPortal`, `CommitteePortal`, `StudentQuestCard`
- [x] `processMetadataLabels.js` — student/operator hints
- [x] `portalStaffLanes.js` — course-committee lane

## خارج از دامنه
- [ ] Trigger خودکار `ta_passed_all_courses_in_track_second_time` در scheduler
- [ ] پترن SMS ملی‌پیامک
