"""Test introductory_term_end as جریان بزرگ (BUILD_TODO item ۹ — ه: پایان ترم آشنایی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestIntroductoryTermEndFlow:

    async def test_introductory_term_end_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند پایان ترم دوره آشنایی لود و استارت می‌شود؛ state اول grades_submitted است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "introductory_term_end.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "introductory_term_end"
        assert instance.current_state_code == "grades_submitted"
        assert instance.is_completed is False

    async def test_introductory_term_end_transition_to_transcript_generated(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از grades_submitted با trigger auto_generate_transcripts به transcript_generated می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "introductory_term_end.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="auto_generate_transcripts",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "grades_submitted"
        assert result.to_state == "transcript_generated"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "transcript_generated"
