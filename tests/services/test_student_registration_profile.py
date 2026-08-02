"""Tests for extended student registration profile validation."""

from app.api.public_routes import StudentRegistrationRequest, _validate_registration_data
from app.api.student.routes import CompleteStudentRegistrationBody
from app.services.student_registration_profile import validate_registration_profile_fields


def _complete_body_with_university_degree_yes() -> CompleteStudentRegistrationBody:
    return CompleteStudentRegistrationBody(
        full_name_fa="علی احمدی",
        national_code="0013542419",
        email="ali@example.com",
        course_type="introductory",
        first_name_fa="علی",
        last_name_fa="احمدی",
        age=30,
        birth_certificate_number="123",
        birth_date="1370/01/15",
        residence_city="تهران",
        home_address="آدرس منزل",
        work_address="آدرس کار",
        home_phone="02112345678",
        work_phone="02187654321",
        had_psychotherapy="yes",
        psychotherapy_approach="analytical",
        psychotherapy_therapist_name="دکتر نمونه",
        used_psychiatric_meds="no",
        psychiatric_hospitalization_history="no",
        has_work_permit="yes",
        work_permit_issuer="سازمان",
        has_university_degree="yes",
        education_level="bachelor",
        field_of_study="روان‌شناسی",
        university="تهران",
        graduation_year="1395",
        course_participation_mode="online",
        referral_source="website",
    )


def test_complete_registration_synth_accepts_conditional_university_fields():
    """Regression: has_university_degree=yes must not duplicate education_level kwargs."""
    body = _complete_body_with_university_degree_yes()
    profile_fields = validate_registration_profile_fields(body)
    synth = StudentRegistrationRequest(
        full_name_fa=body.full_name_fa,
        phone="09123456789",
        national_code=body.national_code,
        email=body.email,
        course_type=body.course_type,
        motivation=body.motivation,
        **profile_fields,
    )
    _validate_registration_data(synth)
    assert synth.education_level == "bachelor"
    assert synth.field_of_study == "روان‌شناسی"
    assert synth.university == "تهران"
