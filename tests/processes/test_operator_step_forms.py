"""تست واحد برای ثبت فرم مرحلهٔ اپراتور (فرایند ۲۹/۳۰ — آماده‌سازی ترم)."""

from app.meta.process_forms import get_process_forms
from app.meta.student_step_forms import (
    sanitize_operator_form_values,
    validate_operator_step_forms,
)


def test_fall_calendar_form_requires_dates():
    """فرم تقویم پاییز فیلدهای الزامی تاریخ دارد؛ مقادیر خالی باید رد شود."""
    forms = get_process_forms("fall_semester_preparation", state_code="calendar_entry")
    assert forms, "academic_calendar_form باید برای calendar_entry تعریف شده باشد"

    ok, missing = validate_operator_step_forms(forms, {}, {})
    assert ok is False
    assert missing, "باید فیلدهای الزامی گزارش شود"


def test_fall_calendar_form_passes_with_required_values():
    forms = get_process_forms("fall_semester_preparation", state_code="calendar_entry")
    values = {
        "fall_start_date": "2026-09-23",
        "fall_end_date": "2026-12-21",
        "winter_start_date": "2026-12-22",
        "winter_end_date": "2027-03-20",
        "registration_payment_window_start": "2026-08-01",
        "registration_payment_window_end": "2026-09-01",
        "intern_interview_deadline": "2026-08-15",
        "teaching_assistant_interview_deadline": "2026-08-20",
        "nowruz_holiday_start": "2027-03-21",
        "nowruz_holiday_end": "2027-04-02",
        # فیلدهای اختیاری بازه‌ای
        "fall_break_periods": [{"start": "2026-10-01", "end": "2026-10-03"}],
    }
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is True, f"باید معتبر باشد ولی نواقص: {missing}"


def test_interviewer_assignment_multi_select_required():
    """multi_select الزامی (مصاحبه‌کنندگان) باید لیست غیرخالی بخواهد."""
    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    assert forms
    ok, missing = validate_operator_step_forms(forms, {"comprehensive_interviewers": []}, {})
    assert ok is False
    assert missing


def test_sanitize_drops_unknown_keys():
    forms = get_process_forms("fall_semester_preparation", state_code="tuition_entry")
    raw = {
        "per_unit_cost_introductory": 1000,
        "per_unit_cost_comprehensive": 2000,
        "interview_fee_introductory": 500,
        "interview_fee_comprehensive": 600,
        "__internal": "secret",
        "not_a_field": "x",
    }
    cleaned = sanitize_operator_form_values(forms, raw)
    assert "__internal" not in cleaned
    assert "not_a_field" not in cleaned
    assert cleaned["per_unit_cost_introductory"] == 1000
    assert cleaned["interview_fee_introductory"] == 500


def test_marketing_campaign_requires_confirmation():
    forms = get_process_forms("fall_semester_preparation", state_code="marketing_campaign")
    assert forms, "marketing_campaign_form باید تعریف شده باشد"
    ok, missing = validate_operator_step_forms(forms, {}, {})
    assert ok is False
    assert missing
    ok2, _ = validate_operator_step_forms(
        forms,
        {"marketing_confirmed": True, "marketing_channels": ["سایت"]},
        {},
    )
    assert ok2 is True


def test_fall_license_visible_if_new_number_when_changed():
    forms = get_process_forms("fall_semester_preparation", state_code="license_check")
    ok, _ = validate_operator_step_forms(forms, {"license_status": "بدون تغییر"}, {})
    assert ok is True
    from app.services.forms.condition import field_visible

    hidden = {"license_status": "بدون تغییر"}
    assert field_visible({"visible_if": {"license_status": "تغییر کرده"}}, hidden) is False
    shown = {"license_status": "تغییر کرده"}
    assert field_visible({"visible_if": {"license_status": "تغییر کرده"}}, shown) is True


def test_winter_license_visible_if_field_not_required_when_hidden():
    """new_license_number فقط وقتی license_status=تغییر کرده الزامی است (visible_if)."""
    forms = get_process_forms("winter_semester_preparation", state_code="license_check")
    assert forms
    # وضعیت «بدون تغییر» → فیلد شماره جدید لازم نیست.
    ok, _ = validate_operator_step_forms(forms, {"license_status": "بدون تغییر"}, {})
    assert ok is True


def test_winter_marketing_campaign_form_exists():
    forms = get_process_forms("winter_semester_preparation", state_code="marketing_campaign")
    codes = {f.get("code") for f in forms}
    assert "winter_marketing_campaign_form" in codes
    marketing_form = next(f for f in forms if f.get("code") == "winter_marketing_campaign_form")
    field_names = {fld.get("name") for fld in marketing_form.get("fields") or []}
    assert "marketing_confirmed" in field_names


def test_winter_course_list_pre_filled_from_metadata():
    forms = get_process_forms("winter_semester_preparation", state_code="course_list_review")
    review_form = next(f for f in forms if f.get("code") == "winter_course_list_review_form")
    courses_field = next(
        fld for fld in review_form.get("fields") or [] if fld.get("name") == "courses"
    )
    assert courses_field.get("pre_filled_from") == "fall_semester_preparation.course_list_form"


def test_interviewer_assignment_options_source_metadata():
    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    assignment_form = next(f for f in forms if f.get("code") == "interviewer_assignment_form")
    for name in ("comprehensive_interviewers", "introductory_interviewers"):
        field = next(fld for fld in assignment_form.get("fields") or [] if fld.get("name") == name)
        src = field.get("options_source") or {}
        assert src.get("type") == "users"
        assert src.get("role") == "interviewer"
        assert src.get("is_active") is True


def test_educational_leave_committee_meeting_form_requires_datetime_and_mode():
    forms = get_process_forms("educational_leave", state_code="committee_review")
    assert forms, "leave_committee_meeting باید برای committee_review تعریف شده باشد"
    ok, missing = validate_operator_step_forms(forms, {}, {})
    assert ok is False
    assert missing
    ok2, missing2 = validate_operator_step_forms(
        forms,
        {
            "committee_meeting_at": "2026-09-15T10:30:00+00:00",
            "committee_meeting_mode": "in_person",
            "committee_meeting_location_fa": "سالن جلسات",
        },
        {},
    )
    assert ok2 is True, missing2
    ok3, _ = validate_operator_step_forms(
        forms,
        {
            "committee_meeting_at": "2026-09-15T10:30:00+00:00",
            "committee_meeting_mode": "online",
        },
        {},
    )
    assert ok3 is False


def test_educational_leave_deputy_alerted_uses_committee_review_form():
    forms = get_process_forms("educational_leave", state_code="deputy_alerted")
    codes = {f.get("code") for f in forms}
    assert "leave_committee_meeting" in codes


def test_educational_leave_return_confirmation_form():
    from app.meta.student_step_forms import validate_student_step_forms

    forms = get_process_forms("educational_leave", state_code="return_reminder_sent")
    assert forms
    ok, _ = validate_student_step_forms(forms, {}, {})
    assert ok is False
    ok2, missing2 = validate_student_step_forms(
        forms,
        {"return_registration_confirmed": True},
        {},
    )
    assert ok2 is True, missing2
