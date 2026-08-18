"""تست سرویس پیش‌فرض‌های مالی برنامه."""

from app.services.financial_program_defaults_service import (
    extract_term_tuition_patch_from_context,
    normalize_financial_program_payload,
)


def test_normalize_merges_partial_dict():
    base = normalize_financial_program_payload({})
    assert base["registration_interview_fee_rial"] >= 1000
    assert base["registration_tuition_invoice_toman"] > 0
    out = normalize_financial_program_payload({"extra_session_fee_rial": 8_000_000})
    assert out["extra_session_fee_rial"] == 8_000_000
    assert out["registration_interview_fee_rial"] == base["registration_interview_fee_rial"]


def test_normalize_optional_class_course_zero():
    out = normalize_financial_program_payload(
        {"class_session_fee_toman": 0, "course_session_fee_toman": 125_000}
    )
    assert out["class_session_fee_toman"] == 0.0
    assert out["course_session_fee_toman"] == 125_000.0


def test_normalize_term_tuition_keys():
    out = normalize_financial_program_payload(
        {
            "per_unit_cost_introductory": 2_500_000,
            "interview_fee_introductory": 6_000_000,
        }
    )
    assert out["per_unit_cost_introductory"] == 2_500_000
    assert out["interview_fee_introductory"] == 6_000_000
    assert out["per_unit_cost_comprehensive"] == 0


def test_extract_term_tuition_patch_from_context():
    patch = extract_term_tuition_patch_from_context(
        {
            "per_unit_cost_introductory": "2500000",
            "interview_fee_introductory": 6_000_000,
            "interview_fee_comprehensive": 99,
            "registration_tuition_invoice_toman": 95_000_000,
            "start_therapy_first_session_fee_rial": 11_000_000,
            "extra_session_fee_rial": 8_000_000,
            "default_therapy_session_fee_toman": 550_000,
            "class_session_fee_toman": 0,
            "course_session_fee_toman": 120_000,
            "noise": 1,
        }
    )
    assert patch["per_unit_cost_introductory"] == 2_500_000
    assert patch["interview_fee_introductory"] == 6_000_000
    assert patch["registration_interview_fee_rial"] == 6_000_000
    assert "interview_fee_comprehensive" not in patch
    assert "registration_tuition_invoice_toman" not in patch
    assert patch["start_therapy_first_session_fee_rial"] == 11_000_000
    assert patch["extra_session_fee_rial"] == 8_000_000
    assert patch["default_therapy_session_fee_toman"] == 550_000.0
    assert "class_session_fee_toman" not in patch
    assert "course_session_fee_toman" not in patch
