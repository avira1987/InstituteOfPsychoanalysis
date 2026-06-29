"""Unit tests for theory_course_completion_service."""

from app.services.theory_course_completion_service import (
    compute_attendance_score,
    compute_total_score,
    enrich_grade_row,
    is_borderline_total,
    is_theory_course,
    label_pass_fail,
)


class TestTheoryCourseCompletionService:

    def test_attendance_penalty(self):
        assert compute_attendance_score(0) == 8
        assert compute_attendance_score(1) == 6
        assert compute_attendance_score(4) == 0

    def test_total_score_pass(self):
        total = compute_total_score(10, 70, 8)
        assert total == 88
        assert label_pass_fail(total) == "PASS"

    def test_borderline(self):
        total = compute_total_score(8, 50, 8)
        assert total == 66
        assert is_borderline_total(total) is True
        assert label_pass_fail(total) == "مرزی"

    def test_incomplete(self):
        row = enrich_grade_row({
            "participation_score": 8,
            "test_score": 70,
            "absence_count": 0,
            "exam_absent": True,
        })
        assert row["pass_fail"] == "I"
        assert row["total_score"] is None

    def test_is_theory_course(self):
        assert is_theory_course("theory_psychoanalysis_2") is True
        assert is_theory_course("technique_skills_1") is False
