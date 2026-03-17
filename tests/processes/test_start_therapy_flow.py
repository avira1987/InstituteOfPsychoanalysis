"""Test start_therapy flow (BUILD_TODO hande h - item 1)."""

import pytest
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance


@pytest.mark.asyncio
class TestStartTherapyFlow:

    async def test_start_therapy_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "start_therapy.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="start_therapy",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert instance.process_code == "start_therapy"
        assert instance.current_state_code == "eligibility_check"
        assert instance.is_completed is False

    async def test_start_therapy_flow_to_therapy_active(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "start_therapy.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="start_therapy",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        inst = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))).scalars().first()
        inst.current_state_code = "payment_pending"
        await db_session.flush()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_confirmed",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "therapy_active"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "therapy_active"
        assert instance.is_completed is True
