"""مجوز editable_by برای نقش پورتال معاون آموزش."""

from app.meta.process_data_access import editable_field_names
from app.meta.process_forms import get_process_forms


def test_deputy_education_can_edit_fall_tuition_form():
    forms = get_process_forms("fall_semester_preparation", state_code="tuition_entry")
    names = editable_field_names(forms, "deputy_education")
    assert "per_unit_cost_introductory" in names
    assert "interview_fee_comprehensive" in names


def test_deputy_education_can_edit_fall_calendar_form():
    forms = get_process_forms("fall_semester_preparation", state_code="calendar_entry")
    names = editable_field_names(forms, "deputy_education")
    assert "fall_start_date" in names
    assert "registration_payment_window_start" in names


def test_deputy_education_can_edit_winter_license_form():
    forms = get_process_forms("winter_semester_preparation", state_code="license_check")
    names = editable_field_names(forms, "deputy_education")
    assert "license_status" in names


def test_staff_cannot_edit_interviewer_assignment_form():
    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    names = editable_field_names(forms, "staff")
    assert "comprehensive_interviewers" not in names
    assert not names


def test_staff_cannot_see_interviewer_assignment_form_fields():
    from app.meta.process_data_access import visible_forms_for_role

    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    vis = visible_forms_for_role(forms, "staff")
    assert vis == []


def test_deputy_education_can_edit_interviewer_assignment_form():
    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    names = editable_field_names(forms, "deputy_education")
    assert "comprehensive_interviewers" in names
    assert "introductory_interviewers" in names
