"""Test therapy_session_reduction as جریان بزرگ (BUILD_TODO دسته ه — سایر جریان‌های بزرگ ۴)."""

import pytest
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance


@pytest.mark.asyncio
class TestTherapySessionReductionFlow:

    async def test_therapy_session_reduction_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند کاهش جلسات درمان لود و استارت می‌شود؛ state اول initiated است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "therapy_session_reduction.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_session_reduction",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "therapy_session_reduction"
        assert instance.current_state_code == "initiated"
        assert instance.is_completed is False

    async def test_therapy_session_reduction_flow_to_reduction_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان از session_selection با sessions_selected به reduction_completed."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "therapy_session_reduction.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_session_reduction",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        inst = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))).scalars().first()
        inst.current_state_code = "session_selection"
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="sessions_selected",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "reduction_completed"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "reduction_completed"
        assert instance.is_completed is True
