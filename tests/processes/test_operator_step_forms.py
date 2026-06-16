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
