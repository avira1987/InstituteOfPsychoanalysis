"""Tests for film_observation_course_service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student
from app.services.film_observation_course_service import (
    collect_student_final_reports,
    enrich_roster_with_final_reports,
    course_code_from_context,
)


def test_course_code_from_context_prefers_course_code():
    assert course_code_from_context({"course_code": "film_obs_1"}) == "film_obs_1"
    assert course_code_from_context({"lesson_course_label": "x", "course_name": "y"}) == "x"


@pytest.mark.asyncio
class TestFilmObservationCourseService:
    async def test_collect_student_final_reports_by_course(
        self, db_session: AsyncSession, sample_student: Student, sample_user
    ):
        pdf_meta = {
            "file_name": "report.pdf",
            "mime": "application/pdf",
            "url": "/uploads/process_instances/x/report.pdf",
        }
        inst = ProcessInstance(
            process_code="film_observation_course_completion",
            student_id=sample_student.id,
            current_state_code="grades_entry",
            context_data={
                "course_code": "film_observation_1",
                "final_report_pdf": pdf_meta,
                "final_report_uploaded_at": "2026-06-01T12:00:00+00:00",
            },
            started_by=sample_user.id,
        )
        db_session.add(inst)
        await db_session.commit()

        reports = await collect_student_final_reports(db_session, "film_observation_1")
        sid = str(sample_student.id)
        assert sid in reports
        assert reports[sid]["final_report_pdf"] == pdf_meta

    async def test_enrich_roster_with_final_reports(
        self, db_session: AsyncSession, sample_student: Student
    ):
        extra = dict(sample_student.extra_data or {})
        extra["lms"] = {"enrolled_courses": ["film_observation_1"]}
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        roster = [{
            "student_id": str(sample_student.id),
            "name_fa": "تست",
            "role": "student",
        }]
        pdf_meta = {"file_name": "r.pdf", "url": "/uploads/r.pdf"}
        reports = {str(sample_student.id): {"final_report_pdf": pdf_meta}}
        enrich_roster_with_final_reports(roster, reports)
        assert roster[0]["final_report_pdf"] == pdf_meta
        assert roster[0]["report_file"] == pdf_meta
