"""Test live_supervision_ta_evaluation flow (BUILD_TODO ه — بسته completion/evaluation)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestLiveSupervisionTaEvaluationFlow:

    async def test_live_supervision_ta_evaluation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند live_supervision_ta_evaluation لود و استارت می‌شود؛ state اول session_18_completed است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "live_supervision_ta_evaluation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="live_supervision_ta_evaluation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "live_supervision_ta_evaluation"
        assert instance.current_state_code == "session_18_completed"
        assert instance.is_completed is False

    async def test_live_supervision_ta_evaluation_flow_to_passed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی قبولی: session_18_completed → evaluation_computed → passed."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "live_supervision_ta_evaluation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="live_supervision_ta_evaluation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        # session_18_completed -> evaluation_computed
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="grades_aggregated",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "evaluation_computed"

        # evaluation_computed -> passed
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="result_pass",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "passed"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "passed"
        assert instance.is_completed is True

