"""تست سبک برای گزارش ممیزی operator/student visibility."""

from __future__ import annotations

from app.meta.operator_student_visibility_audit import build_operator_student_visibility_report


def test_build_report_structure_and_followup_has_student_text():
    rep = build_operator_student_visibility_report()
    assert rep.get("schema_version") == 1
    assert "generated_at" in rep
    assert isinstance(rep.get("summary"), dict)
    assert isinstance(rep.get("rows"), list)
    assert isinstance(rep.get("prioritized_gaps"), list)

    s = rep["summary"]
    assert "total_operator_states" in s
    assert "needs_review_count" in s
    assert s["total_operator_states"] >= 1

    row = next(
        (
            r
            for r in rep["rows"]
            if r.get("process_code") == "introductory_term_end"
            and r.get("state_code") == "followup_in_progress"
        ),
        None,
    )
    assert row is not None
    assert row.get("has_student_task_text") is True
    assert row.get("needs_review") is False
