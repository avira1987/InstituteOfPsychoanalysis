"""Test lesson_start_per_term as جریان بزرگ (BUILD_TODO item ۱۵ — ه: آغاز هر درس در هر ترم)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestLessonStartPerTermFlow:

    async def test_lesson_start_per_term_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند آغاز هر درس در هر ترم لود و استارت می‌شود؛ state اول student_enrollment است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "lesson_start_per_term.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="lesson_start_per_term",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "lesson_start_per_term"
        assert instance.current_state_code == "student_enrollment"
        assert instance.is_completed is False

    async def test_lesson_start_per_term_full_flow_to_lesson_active(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان کامل: student_enrollment → links_created → attendance_list_ready → lesson_active."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "lesson_start_per_term.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="lesson_start_per_term",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="enrolled",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "links_created"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="links_placed",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "attendance_list_ready"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="ready",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "lesson_active"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "lesson_active"
        assert instance.is_completed is True
