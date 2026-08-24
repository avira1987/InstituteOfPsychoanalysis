"""تست اعتبارسنجی انتخاب دروس ترم اول."""

import pytest

from app.meta.course_selection_validation import (
    normalize_course_codes,
    resolve_admission_kind,
    validate_intro_term1_selected_courses,
    validate_selected_courses_for_process,
)
from app.services.term_course_offering_service import (
    SINGLE_COURSE_MISSING_REASON_FA,
    _filter_by_admission_kind,
    _row_from_prep,
    single_course_allowed_code,
)

_SAMPLE_OPTIONS = [
    {"value": "theory_psychoanalysis_1", "label_fa": "تئوری روانکاوی ۱"},
    {"value": "theory_technique_1", "label_fa": "تئوری تکنیک‌ها ۱"},
    {"value": "skills_practice_1", "label_fa": "تکنیک (1): تمرین مهارت‌های اولیه"},
]

_REVERSE_TERM1 = [
    {"value": "theory_technique_1", "label_fa": "تئوری تکنیک‌ها ۱"},
    {"value": "skills_practice_1", "label_fa": "تکنیک (1): تمرین مهارت‌های اولیه"},
    {"value": "theory_psychoanalysis_1", "label_fa": "تئوری روانکاوی ۱"},
]

_TERM2_OPTIONS = [
    {"value": "theory_technique_2", "label_fa": "تئوری تکنیک‌ها ۲"},
    {"value": "theory_psychoanalysis_2", "label_fa": "تئوری روانکاوی ۲"},
    {"value": "skills_practice_2", "label_fa": "تکنیک (2)"},
]


def test_normalize_course_codes_from_list():
    assert normalize_course_codes(["theory_psychoanalysis_1", "theory_psychoanalysis_2"]) == [
        "theory_psychoanalysis_1",
        "theory_psychoanalysis_2",
    ]


def test_normalize_course_codes_csv_json_and_dict_items():
    assert normalize_course_codes("theory_1,theory_technique_1") == [
        "theory_psychoanalysis_1",
        "theory_technique_1",
    ]
    assert normalize_course_codes('["theory_psychoanalysis_1"]') == ["theory_psychoanalysis_1"]
    assert normalize_course_codes([{"value": "theory_psychoanalysis_1"}]) == [
        "theory_psychoanalysis_1",
    ]


def test_resolve_admission_kind_from_result_alias():
    assert resolve_admission_kind({"result": "full_admission"}) == "full_admission"
    assert resolve_admission_kind({"result": "single_course"}) == "single_course"
    assert resolve_admission_kind({"result": "conditional_therapy"}) == "conditional_therapy"
    assert resolve_admission_kind({"interview_result": "result_single_course"}) == "single_course"
    assert resolve_admission_kind({"admission_type": "تک‌درس"}) == "single_course"


def test_student_extra_single_course_overrides_stale_full_admission():
    from types import SimpleNamespace

    from app.services.admission_type_service import overlay_admission_on_context

    student = SimpleNamespace(extra_data={"admission_type": "single_course"})
    ctx = overlay_admission_on_context(
        {"interview_result": "full_admission", "available_course_options": _REVERSE_TERM1},
        student,
    )
    filtered, max_select, hint = _filter_by_admission_kind(
        _REVERSE_TERM1, ctx, term_number=1
    )
    assert hint is None
    assert [o["value"] for o in filtered] == ["theory_psychoanalysis_1"]
    assert max_select == 1


def test_instance_single_course_overrides_stale_student_full_admission():
    from types import SimpleNamespace

    from app.services.admission_type_service import overlay_admission_on_context

    student = SimpleNamespace(extra_data={"admission_type": "full_admission"})
    ctx = overlay_admission_on_context(
        {
            "interview_result": "single_course",
            "student": {"admission_type": "full_admission"},
        },
        student,
        state_codes=["result_full_admission", "result_single_course", "course_selection"],
    )
    assert ctx["admission_type"] == "single_course"
    assert ctx["student"]["admission_type"] == "single_course"
    filtered, max_select, hint = _filter_by_admission_kind(
        _REVERSE_TERM1, ctx, term_number=1
    )
    assert hint is None
    assert [o["value"] for o in filtered] == ["theory_psychoanalysis_1"]
    assert max_select == 1


def test_filter_by_admission_kind_uses_result_when_interview_result_missing():
    filtered, max_select, hint = _filter_by_admission_kind(
        _SAMPLE_OPTIONS,
        {"result": "full_admission", "allowed_course_count": 2},
        term_number=1,
    )
    assert hint is None
    assert len(filtered) == 3
    assert max_select == 2


def test_single_course_ignores_list_order():
    ctx = {
        "admission_type": "single_course",
        "available_course_options": _REVERSE_TERM1,
        "available_courses": [o["value"] for o in _REVERSE_TERM1],
    }
    ok, err = validate_intro_term1_selected_courses(ctx, ["theory_psychoanalysis_1"])
    assert ok is True
    assert err is None
    ok2, err2 = validate_intro_term1_selected_courses(ctx, ["theory_technique_1"])
    assert ok2 is False
    assert err2


def test_normalize_legacy_maps_persian_technique_alias():
    from app.services.term_course_offering_service import normalize_legacy_course_code

    assert normalize_legacy_course_code("تئوری تکنیک یک") == "theory_technique_1"
    assert normalize_legacy_course_code("تئوری روانکاوی یک") == "theory_psychoanalysis_1"


def test_single_course_filter_picks_catalog_code_not_index():
    filtered, max_select, hint = _filter_by_admission_kind(
        _REVERSE_TERM1,
        {"admission_type": "single_course"},
        term_number=1,
    )
    assert hint is None
    assert [o["value"] for o in filtered] == ["theory_psychoanalysis_1"]
    assert max_select == 1


def test_single_course_normalizes_persian_option_values():
    filtered, max_select, hint = _filter_by_admission_kind(
        [
            {"value": "تئوری تکنیک یک", "label_fa": "تئوری تکنیک یک"},
            {"value": "تئوری روانکاوی یک", "label_fa": "تئوری روانکاوی یک"},
        ],
        {"admission_type": "single_course"},
        term_number=1,
    )
    assert hint is None
    assert [o["value"] for o in filtered] == ["theory_psychoanalysis_1"]
    assert max_select == 1


def test_single_course_term2_only_psychoanalysis_2():
    filtered, max_select, hint = _filter_by_admission_kind(
        _TERM2_OPTIONS,
        {"admission_type": "single_course"},
        term_number=2,
    )
    assert hint is None
    assert [o["value"] for o in filtered] == ["theory_psychoanalysis_2"]
    assert max_select == 1


def test_single_course_missing_allowed_course_has_hint():
    filtered, max_select, hint = _filter_by_admission_kind(
        [{"value": "theory_technique_1", "label_fa": "تئوری تکنیک‌ها ۱"}],
        {"admission_type": "single_course"},
        term_number=1,
    )
    assert filtered == []
    assert max_select == 1
    assert hint == SINGLE_COURSE_MISSING_REASON_FA
    assert single_course_allowed_code(1) == "theory_psychoanalysis_1"
    assert single_course_allowed_code(2) == "theory_psychoanalysis_2"


def test_row_from_prep_uses_catalog_prereqs_not_all_prior_term():
    row = _row_from_prep(
        {"course_name": "تئوری روانکاوی ۲"},
        program_kind="introductory",
        term_number=2,
        term_code="t-test",
        per_unit_cost_rial=1000,
    )
    assert row is not None
    assert row["course_code"] == "theory_psychoanalysis_2"
    assert row["prerequisite_codes"] == ["theory_psychoanalysis_1"]


def test_row_from_prep_explicit_prereqs_win():
    row = _row_from_prep(
        {
            "course_name": "تئوری روانکاوی ۲",
            "prerequisite_codes": ["skills_practice_1"],
        },
        program_kind="introductory",
        term_number=2,
        term_code="t-test",
        per_unit_cost_rial=1000,
    )
    assert row["prerequisite_codes"] == ["skills_practice_1"]


@pytest.mark.asyncio
async def test_single_course_process_rejects_technique(db_session):
    ctx = {
        "admission_type": "single_course",
        "available_course_options": _REVERSE_TERM1,
        "available_courses": [o["value"] for o in _REVERSE_TERM1],
    }
    ok, err = await validate_selected_courses_for_process(
        db_session,
        "introductory_course_registration",
        ctx,
        ["theory_technique_1"],
    )
    assert ok is False
    assert err
    ok2, err2 = await validate_selected_courses_for_process(
        db_session,
        "introductory_course_registration",
        ctx,
        ["theory_psychoanalysis_1"],
    )
    assert ok2 is True
    assert err2 is None


@pytest.mark.asyncio
async def test_term2_rejects_technique_without_pass(db_session):
    options = [
        {
            "value": "theory_technique_2",
            "label_fa": "تئوری تکنیک‌ها ۲",
            "prerequisite_codes": ["theory_technique_1"],
        },
        {
            "value": "theory_psychoanalysis_2",
            "label_fa": "تئوری روانکاوی ۲",
            "prerequisite_codes": ["theory_psychoanalysis_1"],
        },
    ]
    ctx = {
        "admission_type": "full_admission",
        "available_course_options": options,
        "lms": {"enrolled_courses": ["theory_technique_1"]},
    }
    ok, err = await validate_selected_courses_for_process(
        db_session,
        "intro_second_semester_registration",
        ctx,
        ["theory_technique_2"],
    )
    assert ok is False
    assert err


@pytest.mark.asyncio
async def test_term2_allows_corequisite_when_failed(db_session):
    options = [
        {
            "value": "theory_psychoanalysis_2",
            "label_fa": "تئوری روانکاوی ۲",
            "prerequisite_codes": ["theory_psychoanalysis_1"],
        }
    ]
    ctx = {
        "admission_type": "full_admission",
        "available_course_options": options,
        "lms": {
            "enrolled_courses": [
                {"code": "theory_psychoanalysis_1", "pass_fail_status": "مردود"}
            ]
        },
    }
    ok, err = await validate_selected_courses_for_process(
        db_session,
        "intro_second_semester_registration",
        ctx,
        ["theory_psychoanalysis_2", "theory_psychoanalysis_1"],
    )
    assert ok is True
    assert err is None


def test_conditional_respects_allowed_count():
    ctx = {
        "admission_type": "conditional_therapy",
        "allowed_course_count": 2,
        "available_course_options": _SAMPLE_OPTIONS,
        "available_courses": [o["value"] for o in _SAMPLE_OPTIONS],
    }
    ok, _ = validate_intro_term1_selected_courses(
        ctx, ["theory_psychoanalysis_1", "theory_technique_1"]
    )
    assert ok is True
    ok2, err2 = validate_intro_term1_selected_courses(
        ctx,
        ["theory_psychoanalysis_1", "theory_technique_1", "skills_practice_1"],
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
        ["theory_psychoanalysis_1", "theory_technique_1"],
    )
    assert ok is True
