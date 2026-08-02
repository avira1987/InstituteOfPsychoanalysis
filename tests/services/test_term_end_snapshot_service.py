"""Tests for term_end_snapshot_service."""

import pytest

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.services.term_end_snapshot_service import (
    apply_term_end_snapshot,
    build_term_end_snapshot,
)
from app.services.workflow.document_service import handle as document_handle
from pathlib import Path


@pytest.mark.asyncio
async def test_build_term_end_snapshot_from_lms(db_session, sample_student):
    extra = sample_student.extra_data or {}
    extra["lms"] = {
        "enrolled_courses": [
            {
                "code": "theory_1",
                "course_name": "تئوری ۱",
                "units": 3,
                "numeric_grade": 16,
                "letter_grade": "B",
                "pass_fail_status": "قبول",
            },
            {
                "code": "theory_2",
                "course_name": "تئوری ۲",
                "units": 3,
                "numeric_grade": 8,
                "letter_grade": "F",
                "pass_fail_status": "مردود",
            },
        ],
    }
    sample_student.extra_data = extra
    sample_student.current_term = 1
    await db_session.commit()

    processes_dir = Path(__file__).resolve().parents[2] / "metadata" / "processes"
    await load_process(db_session, processes_dir / "introductory_term_end.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="introductory_term_end",
        student_id=sample_student.id,
        actor_id=sample_student.user_id,
        actor_role="system",
    )
    await db_session.commit()

    snapshot = build_term_end_snapshot(sample_student, instance)
    assert len(snapshot["term_transcript_rows"]) == 2
    assert snapshot["failed_courses"] == ["تئوری ۲"]
    assert snapshot["term_gpa"] == 16.0
    failed_row = next(r for r in snapshot["term_transcript_rows"] if r["course_name"] == "تئوری ۲")
    assert failed_row["units"] == 0


@pytest.mark.asyncio
async def test_apply_snapshot_on_generate_transcript(db_session, sample_student, sample_user):
    extra = sample_student.extra_data or {}
    extra["lms"] = {
        "enrolled_courses": [
            {
                "code": "comp_1",
                "course_name": "درس جامع ۱",
                "units": 2,
                "numeric_grade": 17,
                "pass_fail_status": "قبول",
            },
        ],
    }
    sample_student.extra_data = extra
    sample_student.course_type = "comprehensive"
    await db_session.commit()

    processes_dir = Path(__file__).resolve().parents[2] / "metadata" / "processes"
    await load_process(db_session, processes_dir / "comprehensive_term_end.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="comprehensive_term_end",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="system",
    )
    await db_session.commit()

    result = await document_handle(
        db_session,
        instance,
        {"type": "generate_term_transcript"},
        {},
    )
    assert result and "document_created" in result
    await db_session.commit()
    await db_session.refresh(instance)
    await db_session.refresh(sample_student)
    assert instance.context_data.get("term_transcript_rows")
    docs = (sample_student.extra_data or {}).get("documents") or []
    term_doc = [d for d in docs if d.get("type") == "term_transcript"][-1]
    assert "درس جامع ۱" in term_doc.get("body_fa", "")
