"""Test supervision_interruption flow (BUILD_TODO hande h - item 8)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestSupervisionInterruptionFlow:

    async def test_supervision_interruption_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "supervision_interruption.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_interruption",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert instance.process_code == "supervision_interruption"
        assert instance.current_state_code == "request_submitted"
        assert instance.is_completed is False

    async def test_supervision_interruption_flow_to_rejected(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "supervision_interruption.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_interruption",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="pause_dates_entered",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "committee_scheduling"
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="meeting_scheduled",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "meeting_held"
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="committee_rejected",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "rejected"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "rejected"
        assert instance.is_completed is True
