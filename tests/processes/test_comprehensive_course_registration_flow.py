"""Test comprehensive_course_registration as جریان بزرگ (BUILD_TODO item ۱۲ — ه: دوره جامع)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestComprehensiveCourseRegistrationFlow:

    async def test_comprehensive_course_registration_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ثبت‌نام در دوره جامع لود و استارت می‌شود؛ state اول application_submitted است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "comprehensive_course_registration.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "comprehensive_course_registration"
        assert instance.current_state_code == "application_submitted"
        assert instance.is_completed is False

    async def test_comprehensive_course_registration_has_transitions_from_application_submitted(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از application_submitted برای نقش student transition application_submitted (ارسال به کمیته) در دسترس است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "comprehensive_course_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            "student",
        )
        trigger_events = [t["trigger_event"] for t in transitions]
        assert "application_submitted" in trigger_events
