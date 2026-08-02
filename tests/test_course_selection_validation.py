"""تست اعتبارسنجی انتخاب دروس ترم اول."""

import pytest

from app.meta.course_selection_validation import (
    normalize_course_codes,
    validate_intro_term1_selected_courses,
    validate_selected_courses_for_process,
)

_SAMPLE_OPTIONS = [
    {"value": "theory_psychoanalysis_1", "label_fa": "تئوری روانکاوی ۱"},
    {"value": "theory_psychoanalysis_2", "label_fa": "تئوری روانکاوی ۲"},
    {"value": "theory_psychoanalysis_3", "label_fa": "تئوری روانکاوی ۳"},
]


def test_normalize_course_codes_from_list():
    assert normalize_course_codes(["theory_psychoanalysis_1", "theory_psychoanalysis_2"]) == [
        "theory_psychoanalysis_1",
        "theory_psychoanalysis_2",
    ]


def test_single_course_only_first_offered():
    ctx = {
        "admission_type": "single_course",
        "available_course_options": _SAMPLE_OPTIONS,
        "available_courses": [o["value"] for o in _SAMPLE_OPTIONS],
    }
    ok, err = validate_intro_term1_selected_courses(ctx, ["theory_psychoanalysis_1"])
    assert ok is True
    assert err is None
    ok2, err2 = validate_intro_term1_selected_courses(ctx, ["theory_psychoanalysis_2"])
    assert ok2 is False
    assert err2


def test_conditional_respects_allowed_count():
    ctx = {
        "admission_type": "conditional_therapy",
        "allowed_course_count": 2,
        "available_course_options": _SAMPLE_OPTIONS,
        "available_courses": [o["value"] for o in _SAMPLE_OPTIONS],
    }
    ok, _ = validate_intro_term1_selected_courses(
        ctx, ["theory_psychoanalysis_1", "theory_psychoanalysis_2"]
    )
    assert ok is True
    ok2, err2 = validate_intro_term1_selected_courses(
        ctx,
        ["theory_psychoanalysis_1", "theory_psychoanalysis_2", "theory_psychoanalysis_3"],
    )
    assert ok2 is False
    assert "حداکثر" in (err2 or "")


@pytest.mark.asyncio
async def test_intro_reg_process_wrapper(db_session):
    ctx = {
        "interview_result": "full_admission",
        "allowed_course_count": 3,
        "available_course_options": _SAMPLE_OPTIONS,
        "available_courses": [o["value"] for o in _SAMPLE_OPTIONS],
    }
    ok, _ = await validate_selected_courses_for_process(
        db_session,
        "introductory_course_registration",
        ctx,
        ["theory_psychoanalysis_1", "theory_psychoanalysis_2"],
    )
    assert ok is True
