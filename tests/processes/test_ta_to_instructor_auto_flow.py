"""Test ta_to_instructor_auto flow (BUILD_TODO ه — بسته TA)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTaToInstructorAutoFlow:

    async def test_ta_to_instructor_auto_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ta_to_instructor_auto لود و استارت می‌شود؛ state اول end_of_term_check است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_to_instructor_auto.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_instructor_auto",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "ta_to_instructor_auto"
        assert instance.current_state_code == "end_of_term_check"
        assert instance.is_completed is False

    async def test_ta_to_instructor_auto_flow_to_upgrade_applied(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریو: end_of_term_check → upgrade_applied با conditions_met."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_to_instructor_auto.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_instructor_auto",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="conditions_met",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "upgrade_applied"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "upgrade_applied"
        assert instance.is_completed is True

