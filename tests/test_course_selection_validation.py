"""تست اعتبارسنجی انتخاب دروس ترم اول."""

from app.meta.course_selection_validation import (
    normalize_course_codes,
    validate_intro_term1_selected_courses,
    validate_selected_courses_for_process,
)


def test_normalize_course_codes_from_list():
    assert normalize_course_codes(["theory_1", "theory_2"]) == ["theory_1", "theory_2"]


def test_single_course_only_theory_1():
    ctx = {"admission_type": "single_course"}
    ok, err = validate_intro_term1_selected_courses(ctx, ["theory_1"])
    assert ok is True
    assert err is None
    ok2, err2 = validate_intro_term1_selected_courses(ctx, ["theory_2"])
    assert ok2 is False
    assert err2


def test_conditional_respects_allowed_count():
    ctx = {"admission_type": "conditional_therapy", "allowed_course_count": 2}
    ok, _ = validate_intro_term1_selected_courses(ctx, ["theory_1", "theory_2"])
    assert ok is True
    ok2, err2 = validate_intro_term1_selected_courses(
        ctx, ["theory_1", "theory_2", "theory_3"]
    )
    assert ok2 is False
    assert "حداکثر" in (err2 or "")


def test_intro_reg_process_wrapper():
    ctx = {"interview_result": "full_admission", "allowed_course_count": 3}
    ok, _ = validate_selected_courses_for_process(
        "introductory_course_registration",
        ctx,
        ["theory_1", "theory_2"],
    )
    assert ok is True
