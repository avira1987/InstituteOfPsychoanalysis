"""Test supervisor_session_cancellation as جریان بزرگ (BUILD_TODO item ۲۳ — ه بخش ۲۰: کنسل جلسه توسط سوپروایزر)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestSupervisorSessionCancellationFlow:

    async def test_supervisor_session_cancellation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند کنسل جلسه توسط سوپروایزر لود و استارت می‌شود؛ state اول session_selection است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "supervisor_session_cancellation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervisor_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="supervisor",
        )
        await db_session.commit()

        assert instance.process_code == "supervisor_session_cancellation"
        assert instance.current_state_code == "session_selection"
        assert instance.is_completed is False

    async def test_supervisor_session_cancellation_flow_no_makeup(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان لغو بدون جبرانی: session_selection → makeup_choice → cancelled_no_makeup."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "supervisor_session_cancellation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervisor_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="supervisor",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="session_selected",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "makeup_choice"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="no_makeup_selected",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "cancelled_no_makeup"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "cancelled_no_makeup"
        assert instance.is_completed is True
