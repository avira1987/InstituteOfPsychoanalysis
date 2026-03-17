"""Test therapy_early_termination as جریان بزرگ (BUILD_TODO دسته ه — سایر جریان‌های بزرگ ۵)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTherapyEarlyTerminationFlow:

    async def test_therapy_early_termination_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند قطع زودرس درمان لود و استارت می‌شود؛ state اول reason_selection است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "therapy_early_termination.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_early_termination",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="therapist",
        )
        await db_session.commit()

        assert instance.process_code == "therapy_early_termination"
        assert instance.current_state_code == "reason_selection"
        assert instance.is_completed is False

    async def test_therapy_early_termination_flow_to_restart_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان: reason_selection → awaiting_student_restart → restart_completed."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "therapy_early_termination.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_early_termination",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="therapist",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="reason_submitted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "awaiting_student_restart"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_restarted_therapy",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "restart_completed"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "restart_completed"
        assert instance.is_completed is True
