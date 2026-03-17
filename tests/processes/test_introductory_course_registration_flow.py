"""Test introductory_course_registration as جریان بزرگ (BUILD_TODO item ۸ — ه: سایر جریان‌های بزرگ)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestIntroductoryCourseRegistrationFlow:

    async def test_introductory_course_registration_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ثبت‌نام دوره آشنایی لود و استارت می‌شود؛ state اول application_submitted است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "introductory_course_registration.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        assert instance.process_code == "introductory_course_registration"
        assert instance.current_state_code == "application_submitted"
        assert instance.is_completed is False

    async def test_introductory_course_registration_has_transition_to_interview_scheduled(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از application_submitted با trigger timeslot_selected به interview_scheduled می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "introductory_course_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            "applicant",
        )
        trigger_events = [t["trigger_event"] for t in transitions]
        assert "timeslot_selected" in trigger_events

    async def test_introductory_course_registration_transition_timeslot_selected(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """اجرای timeslot_selected باعث رفتن به interview_scheduled می‌شود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "introductory_course_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="timeslot_selected",
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "application_submitted"
        assert result.to_state == "interview_scheduled"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "interview_scheduled"
