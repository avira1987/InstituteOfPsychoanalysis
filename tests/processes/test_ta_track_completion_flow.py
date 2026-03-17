"""Test ta_track_completion as جریان بزرگ (BUILD_TODO item ۲۵ — ه بخش ۲۲: خاتمه کمک‌مدرس برای هر رسته)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTaTrackCompletionFlow:

    async def test_ta_track_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند خاتمه رسته کمک‌مدرس لود و استارت می‌شود؛ state اول end_of_track_check است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_track_completion.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_track_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "ta_track_completion"
        assert instance.current_state_code == "end_of_track_check"
        assert instance.is_completed is False

    async def test_ta_track_completion_flow_to_track_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان: end_of_track_check → track_completed با trigger conditions_met."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_track_completion.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_track_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="conditions_met",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "track_completed"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "track_completed"
        assert instance.is_completed is True
