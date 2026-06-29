"""Tests for student_instructor_evaluation service (process 57)."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import InstituteCalendar, ProcessInstance, Student
from app.services.student_instructor_evaluation_service import (
    aggregate_term_results,
    list_evaluable_courses,
    submit_course_evaluation,
)


def _enrolled_lms(courses: list[dict]) -> dict:
    return {"lms": {"enrolled_courses": courses}}


@pytest.mark.asyncio
class TestStudentInstructorEvaluationService:

    async def test_list_evaluable_courses_dedupes(self, sample_student: Student):
        sample_student.extra_data = _enrolled_lms([
            {"course_code": "theory_1", "course_name": "نظریه ۱", "instructor_name": "دکتر الف"},
            {"course_code": "theory_1", "course_name": "نظریه ۱", "instructor_name": "دکتر الف"},
            {"course_code": "skills_1", "course_name": "مهارت ۱", "instructor_name": "دکتر ب"},
        ])
        rows = list_evaluable_courses(sample_student, "fall-2026")
        assert len(rows) == 2
        codes = {r["course_code"] for r in rows}
        assert codes == {"theory_1", "skills_1"}

    async def test_submit_two_courses_keeps_instance_open(
        self, db_session: AsyncSession, sample_student: Student, sample_student_user,
    ):
        term_code = f"test-eval-{uuid.uuid4().hex[:8]}"
        cal = InstituteCalendar(
            id=uuid.uuid4(),
            term_code=term_code,
            is_active=True,
            evaluation_open_at=datetime.now(timezone.utc),
            evaluation_close_at=datetime.now(timezone.utc),
            extra_data={},
        )
        db_session.add(cal)

        sample_student.extra_data = _enrolled_lms([
            {"course_code": "c1", "course_name": "درس ۱", "instructor_name": "مدرس ۱"},
            {"course_code": "c2", "course_name": "درس ۲", "instructor_name": "مدرس ۲"},
        ])
        flag_modified(sample_student, "extra_data")

        inst = ProcessInstance(
            id=uuid.uuid4(),
            student_id=sample_student.id,
            process_code="student_instructor_evaluation",
            current_state_code="evaluation_open",
            context_data={"term_code": term_code},
            is_completed=False,
            is_cancelled=False,
        )
        db_session.add(inst)
        await db_session.commit()

        payload = {
            "overall_score": 4,
            "teaching_clarity": 5,
            "interaction_quality": 3,
            "comments": "خوب",
        }
        await submit_course_evaluation(db_session, inst, sample_student, "c1", payload)
        await db_session.commit()
        await db_session.refresh(inst)
        assert inst.current_state_code == "evaluation_open"
        assert inst.is_completed is False
        assert "c1" in (inst.context_data or {}).get("submitted_course_codes", [])

        await submit_course_evaluation(db_session, inst, sample_student, "c2", payload)
        await db_session.commit()
        await db_session.refresh(inst)
        assert inst.current_state_code == "evaluation_open"
        submitted = (inst.context_data or {}).get("submitted_course_codes", [])
        assert set(submitted) == {"c1", "c2"}

        await db_session.refresh(cal)
        subs = (cal.extra_data or {}).get("evaluation_submissions") or []
        assert len(subs) == 2
        assert all("student_id" not in s for s in subs)

    async def test_aggregate_term_results(
        self, db_session: AsyncSession, sample_student: Student,
    ):
        term_code = f"agg-{uuid.uuid4().hex[:8]}"
        cal = InstituteCalendar(
            id=uuid.uuid4(),
            term_code=term_code,
            is_active=True,
            extra_data={
                "evaluation_submissions": [
                    {
                        "term_code": term_code,
                        "course_code": "c1",
                        "course_name": "درس ۱",
                        "instructor_name": "مدرس ۱",
                        "overall_score": 4,
                        "teaching_clarity": 5,
                        "interaction_quality": 3,
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                    },
                    {
                        "term_code": term_code,
                        "course_code": "c1",
                        "course_name": "درس ۱",
                        "instructor_name": "مدرس ۱",
                        "overall_score": 2,
                        "teaching_clarity": 3,
                        "interaction_quality": 2,
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                    },
                ],
            },
        )
        db_session.add(cal)
        sample_student.extra_data = _enrolled_lms([
            {"course_code": "c1", "course_name": "درس ۱", "instructor_name": "مدرس ۱"},
        ])
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        agg = await aggregate_term_results(db_session, term_code)
        await db_session.commit()
        assert agg["term_code"] == term_code
        assert len(agg["courses"]) == 1
        row = agg["courses"][0]
        assert row["participation_count"] == 2
        assert row["average_score"] == 3.0
        assert row["chart_data"]["overall_score"]["distribution"]["4"] == 1
        assert row["chart_data"]["overall_score"]["distribution"]["2"] == 1
