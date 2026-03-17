"""Test intro_second_semester_registration as جریان بزرگ (BUILD_TODO item ۱۰ — ه: ثبت‌نام ترم دوم آشنایی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestIntroSecondSemesterRegistrationFlow:

    async def test_intro_second_semester_registration_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ثبت‌نام ترم دوم دوره آشنایی لود و استارت می‌شود؛ state اول eligibility_check است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "intro_second_semester_registration.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="intro_second_semester_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "intro_second_semester_registration"
        assert instance.current_state_code == "eligibility_check"
        assert instance.is_completed is False

    async def test_intro_second_semester_registration_has_transitions_from_eligibility(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از eligibility_check برای نقش system/admin transitionهای eligibility_check_result در دسترس است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "intro_second_semester_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="intro_second_semester_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            sample_user.role,
        )
        trigger_events = [t["trigger_event"] for t in transitions]
        assert "eligibility_check_result" in trigger_events
