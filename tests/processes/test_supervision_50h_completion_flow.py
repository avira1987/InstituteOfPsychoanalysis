"""Test supervision_50h_completion flow (BUILD_TODO hande h - item 6)."""

import pytest
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance


@pytest.mark.asyncio
class TestSupervision50hCompletionFlow:

    async def test_supervision_50h_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "supervision_50h_completion.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_50h_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert instance.process_code == "supervision_50h_completion"
        assert instance.current_state_code == "session_scheduled"
        assert instance.is_completed is False

    async def test_supervision_50h_completion_flow_to_evaluation_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "supervision_50h_completion.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_50h_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        inst = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))).scalars().first()
        inst.current_state_code = "evaluation_pending"
        await db_session.flush()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="supervisor_submitted_evaluation",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "evaluation_completed"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "evaluation_completed"
        assert instance.is_completed is True
