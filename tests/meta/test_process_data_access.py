"""مجوز editable_by برای نقش پورتال معاون آموزش."""

from app.meta.process_data_access import editable_field_names
from app.meta.process_forms import get_process_forms


def test_deputy_education_can_edit_fall_tuition_form():
    forms = get_process_forms("fall_semester_preparation", state_code="tuition_entry")
    names = editable_field_names(forms, "deputy_education")
    assert "per_unit_cost_introductory" in names
    assert "interview_fee_comprehensive" in names
    assert "registration_interview_fee_rial" in names
    assert "start_therapy_first_session_fee_rial" in names
    assert "extra_session_fee_rial" in names
    assert "default_therapy_session_fee_toman" in names
    assert "registration_tuition_invoice_toman" not in names
    assert "class_session_fee_toman" not in names
    assert "course_session_fee_toman" not in names


def test_deputy_education_cannot_edit_fall_course_list_form():
    forms = get_process_forms("fall_semester_preparation", state_code="course_list_creation")
    names = editable_field_names(forms, "deputy_education")
    assert "courses_fall" not in names
    assert "courses_winter" not in names
    assert not names


def test_course_committee_can_edit_fall_course_list_form():
    forms = get_process_forms("fall_semester_preparation", state_code="course_list_creation")
    names = editable_field_names(forms, "course_committee")
    assert "courses_fall" in names
    assert "courses_winter" in names


def test_deputy_education_cannot_edit_fall_course_finalization_form():
    forms = get_process_forms("fall_semester_preparation", state_code="course_finalization")
    names = editable_field_names(forms, "deputy_education")
    assert not names


def test_deputy_education_cannot_edit_fall_calendar_form():
    forms = get_process_forms("fall_semester_preparation", state_code="calendar_entry")
    names = editable_field_names(forms, "deputy_education")
    assert "fall_start_date" not in names
    assert not names


def test_course_committee_can_edit_fall_calendar_form():
    forms = get_process_forms("fall_semester_preparation", state_code="calendar_entry")
    names = editable_field_names(forms, "course_committee")
    assert "fall_start_date" in names
    assert "registration_payment_window_start" in names


def test_course_committee_can_edit_fall_course_finalization_form():
    forms = get_process_forms("fall_semester_preparation", state_code="course_finalization")
    names = editable_field_names(forms, "course_committee")
    assert "courses_finalized_fall" in names
    assert "courses_finalized_winter" in names


def test_deputy_education_can_edit_winter_license_form():
    forms = get_process_forms("winter_semester_preparation", state_code="license_check")
    names = editable_field_names(forms, "deputy_education")
    assert "license_status" in names


def test_staff_can_edit_interviewer_assignment_form():
    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    names = editable_field_names(forms, "staff")
    assert "comprehensive_interviewers" in names
    assert "introductory_interviewers" in names
    assert editable_field_names(forms, "internal_manager") == names


def test_staff_can_see_interviewer_assignment_form_fields():
    from app.meta.process_data_access import visible_forms_for_role

    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    vis = visible_forms_for_role(forms, "staff")
    assert vis
    assert any(f.get("code") == "interviewer_assignment_form" for f in vis)


def test_deputy_education_cannot_edit_interviewer_assignment_form():
    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    names = editable_field_names(forms, "deputy_education")
    assert "comprehensive_interviewers" not in names
    assert not names


def test_deputy_education_cannot_edit_marketing_campaign_form():
    forms = get_process_forms("fall_semester_preparation", state_code="marketing_campaign")
    names = editable_field_names(forms, "deputy_education")
    assert "marketing_info_sent_to_manager" not in names
    assert "marketing_notes" not in names
    assert not names


def test_staff_can_edit_marketing_campaign_form():
    forms = get_process_forms("fall_semester_preparation", state_code="marketing_campaign")
    names = editable_field_names(forms, "staff")
    assert "marketing_info_sent_to_manager" in names


def test_portal_role_can_act_on_marketing_campaign_state():
    from app.meta.operator_state_catalog import portal_role_can_act_on_assigned_role
    from app.services.semester_prep_rbac import portal_role_can_act_on_prep_state

    assert portal_role_can_act_on_assigned_role("staff", "admissions_officer")
    assert portal_role_can_act_on_assigned_role("admissions_officer", "admissions_officer")
    assert not portal_role_can_act_on_assigned_role("deputy_education", "admissions_officer")
    assert portal_role_can_act_on_assigned_role("deputy_education", "deputy_education_director")
    assert portal_role_can_act_on_assigned_role("admin", "admissions_officer")
    assert portal_role_can_act_on_assigned_role("staff", "staff")
    assert portal_role_can_act_on_assigned_role("staff", "site_manager")
    # نگاشت سراسری هنوز staff→کمیته را دارد؛ RBAC آماده‌سازی جدا قفل می‌کند
    assert portal_role_can_act_on_assigned_role("staff", "scientific_officer_course_committee")
    assert portal_role_can_act_on_assigned_role("staff", "course_committee_executive")
    assert portal_role_can_act_on_prep_state("staff", "fall_semester_preparation", "course_list_creation") is False
    assert portal_role_can_act_on_prep_state("staff", "fall_semester_preparation", "calendar_entry") is False
    assert portal_role_can_act_on_prep_state("staff", "fall_semester_preparation", "marketing_campaign") is True
    assert portal_role_can_act_on_prep_state("staff", "fall_semester_preparation", "interviewer_assignment") is True
    assert portal_role_can_act_on_prep_state("deputy_education", "fall_semester_preparation", "interviewer_assignment") is False
    assert portal_role_can_act_on_assigned_role("internal_manager", "admissions_officer")
    assert portal_role_can_act_on_assigned_role("internal_manager", "site_manager")


def test_staff_can_edit_interview_scheduling_form():
    forms = get_process_forms("fall_semester_preparation", state_code="interview_scheduling")
    names = editable_field_names(forms, "staff")
    assert "interview_mode" in names
    assert "interview_location_fa" in names
    assert editable_field_names(forms, "internal_manager") == names


def test_site_manager_cannot_edit_interview_scheduling_form():
    forms = get_process_forms("fall_semester_preparation", state_code="interview_scheduling")
    names = editable_field_names(forms, "site_manager")
    assert "interview_mode" not in names
    assert "interview_location_fa" not in names


def test_faculty_1_can_see_and_edit_intro_interview_result_form():
    from app.meta.process_data_access import (
        role_matches_allowed_list,
        visible_forms_for_role,
    )

    assert role_matches_allowed_list("faculty_1", ["interviewer", "admissions_officer", "admin"])
    assert not role_matches_allowed_list("therapist", ["interviewer", "admissions_officer", "admin"])

    forms = get_process_forms("introductory_course_registration", state_code="interview_completed")
    vis = visible_forms_for_role(forms, "faculty_1")
    assert any(f.get("code") == "interview_result_form" for f in vis)
    names = editable_field_names(forms, "faculty_1")
    assert "interview_result" in names
    assert "interviewer_notes" in names
    assert "interview_result" not in editable_field_names(forms, "therapist")


def test_first_role_that_can_edit_forms_prefers_faculty_1_for_interview_result():
    from app.meta.process_data_access import first_role_that_can_edit_forms

    forms = get_process_forms("introductory_course_registration", state_code="interview_completed")
    picked = first_role_that_can_edit_forms(["faculty_1", "educational_instructor"], forms)
    assert picked == "faculty_1"


def test_staff_can_act_on_interview_scheduling_state():
    from app.meta.operator_state_catalog import portal_role_can_act_on_assigned_role

    assert portal_role_can_act_on_assigned_role("staff", "staff")
    assert not portal_role_can_act_on_assigned_role("site_manager", "staff")
    assert not portal_role_can_act_on_assigned_role("deputy_education", "staff")
