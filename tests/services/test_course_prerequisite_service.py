"""پیش‌نیاز/هم‌نیاز و پاس/مردود LMS."""

from app.services.course_prerequisite_service import (
    COREQUISITE_NOTE_FA,
    UNMET_PREREQ_PREFIX_FA,
    classify_student_course_progress,
    partition_options_by_prerequisites,
)

_TERM2 = [
    {
        "value": "theory_psychoanalysis_2",
        "label_fa": "تئوری روانکاوی ۲",
        "prerequisite_codes": ["theory_psychoanalysis_1"],
    },
    {
        "value": "theory_technique_2",
        "label_fa": "تئوری تکنیک‌ها ۲",
        "prerequisite_codes": ["theory_technique_1"],
    },
]


def test_enrolled_without_grade_is_not_passed():
    passed, failed = classify_student_course_progress(
        {"lms": {"enrolled_courses": ["theory_technique_1"]}}
    )
    assert "theory_technique_1" not in passed
    assert "theory_technique_1" not in failed


def test_completed_courses_strings_count_as_passed():
    passed, failed = classify_student_course_progress(
        {"completed_courses": ["theory_technique_1"]}
    )
    assert "theory_technique_1" in passed
    assert not failed


def test_failed_entry_from_lms():
    passed, failed = classify_student_course_progress(
        {
            "lms": {
                "enrolled_courses": [
                    {
                        "code": "theory_psychoanalysis_1",
                        "pass_fail_status": "مردود",
                    }
                ]
            }
        }
    )
    assert "theory_psychoanalysis_1" in failed
    assert "theory_psychoanalysis_1" not in passed


def test_passed_entry_from_letter_grade():
    passed, failed = classify_student_course_progress(
        {
            "lms": {
                "enrolled_courses": [
                    {"course_code": "theory_1", "letter_grade": "B", "passed": True}
                ]
            }
        }
    )
    assert "theory_psychoanalysis_1" in passed
    assert not failed


def test_technique_2_blocked_without_pass():
    allowed, blocked = partition_options_by_prerequisites(_TERM2, set(), set())
    values = {o["value"] for o in allowed}
    assert "theory_technique_2" not in values
    lock = next(o for o in blocked if o["value"] == "theory_technique_2")
    assert UNMET_PREREQ_PREFIX_FA in lock["lock_reason_fa"]


def test_technique_2_allowed_when_technique_1_passed():
    allowed, blocked = partition_options_by_prerequisites(
        _TERM2, {"theory_technique_1"}, set()
    )
    values = {o["value"] for o in allowed}
    assert "theory_technique_2" in values
    assert all(o["value"] != "theory_technique_2" for o in blocked)


def test_failed_prereq_becomes_corequisite():
    allowed, blocked = partition_options_by_prerequisites(
        _TERM2, set(), {"theory_psychoanalysis_1"}
    )
    by_code = {o["value"]: o for o in allowed}
    assert "theory_psychoanalysis_2" in by_code
    assert "theory_psychoanalysis_1" in by_code
    assert by_code["theory_psychoanalysis_2"]["corequisite_codes"] == [
        "theory_psychoanalysis_1"
    ]
    assert by_code["theory_psychoanalysis_1"]["is_corequisite"] is True
    assert COREQUISITE_NOTE_FA in by_code["theory_psychoanalysis_1"]["corequisite_note_fa"]


def test_missing_prereq_codes_filled_from_catalog():
    allowed, blocked = partition_options_by_prerequisites(
        [{"value": "theory_technique_2", "label_fa": "تئوری تکنیک‌ها ۲"}],
        set(),
        set(),
    )
    assert allowed == []
    assert blocked
    assert UNMET_PREREQ_PREFIX_FA in blocked[0]["lock_reason_fa"]
    assert all(o["value"] != "theory_psychoanalysis_2" for o in blocked)


def test_system_prerequisite_codes_do_not_block():
    allowed, blocked = partition_options_by_prerequisites(
        [
            {
                "value": "case_report_writing",
                "label_fa": "مقاله‌نویسی",
                "prerequisite_codes": [],
                "system_prerequisite_codes": ["clinical_hours_500"],
            }
        ],
        set(),
        set(),
    )
    assert [o["value"] for o in allowed] == ["case_report_writing"]
    assert blocked == []


def test_unenforced_system_code_in_course_prereqs_is_ignored():
    allowed, blocked = partition_options_by_prerequisites(
        [
            {
                "value": "case_report_writing",
                "label_fa": "مقاله‌نویسی",
                "prerequisite_codes": ["internship_started", "clinical_hours_500"],
            }
        ],
        set(),
        set(),
    )
    assert [o["value"] for o in allowed] == ["case_report_writing"]
    assert blocked == []
