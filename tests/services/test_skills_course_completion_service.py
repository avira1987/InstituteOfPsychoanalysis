"""Unit tests for skills_course_completion_service."""

import pytest

from app.services.skills_course_completion_service import (
    VARIANT_SKILLS_4,
    compute_attendance_score,
    compute_total_score,
    enrich_grade_row,
    is_incomplete_row,
    is_skills_4_course,
    label_pass_fail,
    practical_max,
    max_test_score,
)


class TestSkillsCourseCompletionService:

    def test_is_skills_4_course(self):
        assert is_skills_4_course("technique_skills_4", "") is True
        assert is_skills_4_course("technique_skills_1", "") is False
        assert is_skills_4_course("", "مهارت‌های ۴") is True

    def test_practical_and_test_max(self):
        assert practical_max("normal") == 60
        assert practical_max(VARIANT_SKILLS_4) == 42
        assert max_test_score("normal") == 22
        assert max_test_score(VARIANT_SKILLS_4) == 40

    def test_compute_attendance_score(self):
        assert compute_attendance_score(0) == 8
        assert compute_attendance_score(1) == 6
        assert compute_attendance_score(4) == 0
        assert compute_attendance_score(10) == 0

    def test_compute_total_normal(self):
        total = compute_total_score(8, 50, 18, 8)
        assert total == 84
        assert label_pass_fail(total) == "PASS"

    def test_compute_total_fail(self):
        total = compute_total_score(5, 30, 10, 6)
        assert total == 51
        assert label_pass_fail(total) == "FAIL"

    def test_incomplete_row(self):
        row = {"session_17_absent": True, "participation_score": 8}
        assert is_incomplete_row(row) is True
        enriched = enrich_grade_row(row, "normal")
        assert enriched["pass_fail"] == "I"
        assert enriched["total_score"] is None

    def test_enrich_grade_row_pass(self):
        row = {
            "participation_score": 9,
            "practical_score": 55,
            "test_score": 20,
            "absence_count": 0,
        }
        enriched = enrich_grade_row(row, "normal", absence_count=0)
        assert enriched["total_score"] == 92
        assert enriched["pass_fail"] == "PASS"
