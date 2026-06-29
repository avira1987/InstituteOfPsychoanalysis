"""Tests for instructor_course_roster_service."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import Student, User
from app.services.instructor_course_roster_service import (
    assigned_course_codes_for_user,
    get_course_roster,
    user_may_access_course,
)


@pytest.mark.asyncio
class TestInstructorCourseRosterService:
    async def test_get_course_roster_from_lesson_attendance(
        self, db_session: AsyncSession, sample_student: Student
    ):
        extra = dict(sample_student.extra_data or {})
        extra["lms"] = {
            "enrolled_courses": ["theory_psychoanalysis_2"],
            "lesson_attendance": {
                "theory_psychoanalysis_2": {
                    "course_code": "theory_psychoanalysis_2",
                    "students": [
                        {
                            "student_id": str(sample_student.id),
                            "student_code": sample_student.student_code,
                            "name_fa": "دانشجوی تست",
                        }
                    ],
                    "sessions": [],
                }
            },
        }
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        roster = await get_course_roster(db_session, "theory_psychoanalysis_2")
        assert len(roster) == 1
        assert roster[0]["student_id"] == str(sample_student.id)
        assert roster[0]["name_fa"] == "دانشجوی تست"

    async def test_get_course_roster_from_enrolled_fallback(
        self, db_session: AsyncSession, sample_student: Student
    ):
        extra = dict(sample_student.extra_data or {})
        extra["lms"] = {"enrolled_courses": ["intro_term1_course1"]}
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        roster = await get_course_roster(db_session, "intro_term1_course1")
        assert len(roster) == 1
        assert roster[0]["student_id"] == str(sample_student.id)


def test_user_may_access_assigned_course():
    user = User(
        username="inst1",
        role="instructor",
        profile_meta={
            "semester_course_assignments": [
                {"course_code": "theory_1", "role_kind": "instructor"},
            ]
        },
    )
    assert user_may_access_course(user, "theory_1") is True
    assert user_may_access_course(user, "theory_2") is False
    assert assigned_course_codes_for_user(user) == {"theory_1"}
