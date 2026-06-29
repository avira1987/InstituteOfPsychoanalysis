"""Unit tests for group_supervision_course_completion_service."""

import pytest

from app.services.group_supervision_course_completion_service import (
    HOURS_PER_PASS,
    GROUP_SUPERVISION_HOURS_CAP,
    TA_PASS_THRESHOLD,
    compute_attendance_score,
    compute_ta_total,
    enrich_pass_fail_row,
    fmt_hours_display,
    label_ta_pass_fail,
    normalize_pass_fail,
)


class TestGroupSupervisionServiceHelpers:

    def test_normalize_pass_fail(self):
        assert normalize_pass_fail("pass") == "PASS"
        assert normalize_pass_fail("FAIL") == "FAIL"
        assert normalize_pass_fail("قبول") == "PASS"

    def test_enrich_pass_fail_row_pass_adds_hours(self):
        row = enrich_pass_fail_row({"pass_fail": "PASS"}, current_hours=30.0)
        assert row["hours_added"] == HOURS_PER_PASS
        assert row["hours_after"] == pytest.approx(30.0 + HOURS_PER_PASS, rel=1e-4)

    def test_enrich_pass_fail_row_fail_no_hours(self):
        row = enrich_pass_fail_row({"pass_fail": "FAIL"}, current_hours=30.0)
        assert row["hours_added"] == 0.0
        assert row["hours_after"] == 30.0

    def test_hours_cap_at_100(self):
        row = enrich_pass_fail_row({"pass_fail": "PASS"}, current_hours=90.0)
        assert row["hours_after"] == GROUP_SUPERVISION_HOURS_CAP

    def test_compute_attendance_score(self):
        assert compute_attendance_score(0) == 8
        assert compute_attendance_score(1) == 6
        assert compute_attendance_score(5) == 0

    def test_ta_pass_fail_threshold(self):
        assert label_ta_pass_fail(TA_PASS_THRESHOLD) == "PASS"
        assert label_ta_pass_fail(TA_PASS_THRESHOLD - 1) == "FAIL"
        assert compute_ta_total(8, 66) == 74

    def test_fmt_hours_display(self):
        assert fmt_hours_display(33.3333) == "33.3"
