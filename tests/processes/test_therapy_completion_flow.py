"""Test therapy_completion flow (BUILD_TODO hande h - item 2)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTherapyCompletionFlow:

    async def test_therapy_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "therapy_completion.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert instance.process_code == "therapy_completion"
        assert instance.current_state_code == "initiated"
        assert instance.is_completed is False

    async def test_therapy_completion_flow_to_therapy_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "therapy_completion.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="process_link_clicked",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "therapy_completed"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "therapy_completed"
        assert instance.is_completed is True
