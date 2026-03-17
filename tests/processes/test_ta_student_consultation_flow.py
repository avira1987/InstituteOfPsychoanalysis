"""Test ta_student_consultation flow (BUILD_TODO ه — بسته TA)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTaStudentConsultationFlow:

    async def test_ta_student_consultation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ta_student_consultation لود و استارت می‌شود؛ state اول session_5_10_15 است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_student_consultation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_student_consultation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "ta_student_consultation"
        assert instance.current_state_code == "session_5_10_15"
        assert instance.is_completed is False

    async def test_ta_student_consultation_flow_to_form_submitted(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی خوش‌بینانه: session_5_10_15 → ta_form_fill → form_submitted."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_student_consultation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_student_consultation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        # session_5_10_15 -> ta_form_fill
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="reminder_sent",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "ta_form_fill"

        # ta_form_fill -> form_submitted
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="form_submitted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "form_submitted"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "form_submitted"
        assert instance.is_completed is True

