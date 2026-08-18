"""Tests for class_attendance_service — فرایند ۵۴."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import Student
from app.services.class_attendance_service import (
    apply_session_attendance,
    infer_course_type,
    is_absent_status,
)


def test_infer_course_type():
    assert infer_course_type("live_supervision_1", None) == "live_supervision"
    assert infer_course_type("article_writing", None) == "article_writing"
    assert infer_course_type("مقاله‌نویسی", None) == "article_writing"
    assert infer_course_type("theory_1", None) == "standard"


def test_is_absent_status():
    assert is_absent_status("absent") is True
    assert is_absent_status("غایب") is True
    assert is_absent_status("present") is False


@pytest.mark.asyncio
class TestClassAttendanceService:
    async def test_apply_session_increments_per_course_absence(
        self, db_session: AsyncSession, sample_student: Student
    ):
        sid = str(sample_student.id)
        extra = dict(sample_student.extra_data or {})
        extra["lms"] = {
            "enrolled_courses": [{"code": "theory_1", "course_name": "theory_1"}],
            "lesson_attendance": {
                "theory_1": {
                    "course_code": "theory_1",
                    "sessions": [],
                    "absence_count": 4,
                }
            },
        }
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        summary = await apply_session_attendance(
            db_session,
            "theory_1",
            "2026-03-01",
            [{"student_id": sid, "status": "absent", "person_name": "تست"}],
        )
        await db_session.commit()
        await db_session.refresh(sample_student)

        assert summary["updated"] == 1
        assert summary["absent"] == 1
        assert sid in summary["incomplete_triggered"]

        lms = (sample_student.extra_data or {}).get("lms") or {}
        entry = lms["lesson_attendance"]["theory_1"]
        assert entry["absence_count"] == 5
        assert len(entry["sessions"]) == 1
        assert entry["sessions"][0]["status"] == "absent"

        enrolled = lms.get("enrolled_courses") or []
        assert enrolled[0].get("incomplete") is True

    async def test_apply_session_present_no_increment(
        self, db_session: AsyncSession, sample_student: Student
    ):
        sid = str(sample_student.id)
        extra = dict(sample_student.extra_data or {})
        extra["lms"] = {
            "enrolled_courses": ["theory_1"],
            "lesson_attendance": {"theory_1": {"absence_count": 2, "sessions": []}},
        }
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        summary = await apply_session_attendance(
            db_session,
            "theory_1",
            "2026-03-02",
            [{"student_id": sid, "status": "present"}],
        )
        await db_session.commit()
        await db_session.refresh(sample_student)

        assert summary["present"] == 1
        entry = (sample_student.extra_data or {})["lms"]["lesson_attendance"]["theory_1"]
        assert entry["absence_count"] == 2
        assert entry["sessions"][0]["status"] == "present"

    async def test_article_writing_no_incomplete(
        self, db_session: AsyncSession, sample_student: Student
    ):
        sid = str(sample_student.id)
        extra = dict(sample_student.extra_data or {})
        extra["lms"] = {
            "enrolled_courses": [{"code": "article_writing"}],
            "lesson_attendance": {"article_writing": {"absence_count": 4, "sessions": []}},
        }
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        summary = await apply_session_attendance(
            db_session,
            "article_writing",
            "2026-03-03",
            [{"student_id": sid, "status": "absent"}],
            course_type="article_writing",
        )
        await db_session.commit()
        await db_session.refresh(sample_student)

        assert sid in summary["article_violation_triggered"]
        assert sid not in summary["incomplete_triggered"]
        entry = (sample_student.extra_data or {})["lms"]["lesson_attendance"]["article_writing"]
        assert entry.get("article_violation_pending") is True
        enrolled = (sample_student.extra_data or {})["lms"]["enrolled_courses"][0]
        assert enrolled.get("incomplete") is not True

    async def test_present_forced_absent_when_tuition_blocked(
        self, db_session: AsyncSession, sample_student: Student
    ):
        sid = str(sample_student.id)
        extra = dict(sample_student.extra_data or {})
        extra["class_present_blocked"] = {
            "active": True,
            "reason_fa": "هشدار: امکان ثبت حضور برای این دانشجو به دلیل عدم تسویه بدهی شهریه وجود ندارد. لطفاً گزینه غیبت را ثبت نمایید.",
        }
        extra["lms"] = {
            "enrolled_courses": ["theory_1"],
            "lesson_attendance": {"theory_1": {"absence_count": 0, "sessions": []}},
        }
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        summary = await apply_session_attendance(
            db_session,
            "theory_1",
            "2026-03-04",
            [{"student_id": sid, "status": "present"}],
        )
        await db_session.commit()
        await db_session.refresh(sample_student)

        assert summary["absent"] == 1
        assert summary["present"] == 0
        assert sid in summary["forced_absent_tuition_block"]
        entry = (sample_student.extra_data or {})["lms"]["lesson_attendance"]["theory_1"]
        assert entry["sessions"][0]["status"] == "absent"
        assert entry["absence_count"] == 1
        assert entry["sessions"][0].get("tuition_present_blocked") is True


@pytest.mark.asyncio
class TestTuitionPresentBlockActions:
    async def test_block_and_unblock_class_present(
        self, db_session: AsyncSession, sample_student: Student
    ):
        import uuid

        from app.models.operational_models import ProcessInstance
        from app.services.action_handler import ActionHandler
        from app.services.class_attendance_service import student_class_present_blocked

        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="intro_second_semester_registration",
            student_id=sample_student.id,
            current_state_code="installment_overdue",
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        results = await handler.handle_actions(
            [{"type": "block_attendance_registration"}],
            instance,
            {},
        )
        await db_session.commit()
        await db_session.refresh(sample_student)

        assert results[0]["success"] is True
        assert student_class_present_blocked(sample_student) is True

        results2 = await handler.handle_actions(
            [{"type": "unblock_attendance_registration"}],
            instance,
            {},
        )
        await db_session.commit()
        await db_session.refresh(sample_student)

        assert results2[0]["success"] is True
        assert student_class_present_blocked(sample_student) is False
        assert sample_student.extra_data.get("attendance_registration_unlocked") is True
