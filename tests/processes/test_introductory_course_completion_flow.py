"""Test introductory_course_completion as جریان بزرگ (BUILD_TODO item ۱۱ — ه: خاتمه دوره آشنایی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestIntroductoryCourseCompletionFlow:

    async def test_introductory_course_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند خاتمه دوره آشنایی لود و استارت می‌شود؛ state اول all_courses_passed است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "introductory_course_completion.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "introductory_course_completion"
        assert instance.current_state_code == "all_courses_passed"
        assert instance.is_completed is False

    async def test_introductory_course_completion_transition_to_invitation_sent(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از all_courses_passed با trigger all_10_courses_passed به invitation_sent می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "introductory_course_completion.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="all_10_courses_passed",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "all_courses_passed"
        assert result.to_state == "invitation_sent"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "invitation_sent"
