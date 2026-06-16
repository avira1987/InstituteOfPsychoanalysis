"""تست سرویس پیش‌فرض‌های مالی برنامه."""

from app.services.financial_program_defaults_service import normalize_financial_program_payload


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
