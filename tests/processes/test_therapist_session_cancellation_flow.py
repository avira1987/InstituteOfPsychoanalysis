"""Test therapist_session_cancellation as جریان بزرگ (BUILD_TODO item ۲۲ — ه بخش ۱۹: کنسل جلسه توسط درمانگر)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTherapistSessionCancellationFlow:

    async def test_therapist_session_cancellation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند کنسل جلسه توسط درمانگر لود و استارت می‌شود؛ state اول session_selection است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "therapist_session_cancellation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapist_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="therapist",
        )
        await db_session.commit()

        assert instance.process_code == "therapist_session_cancellation"
        assert instance.current_state_code == "session_selection"
        assert instance.is_completed is False

    async def test_therapist_session_cancellation_flow_no_make_up(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان لغو بدون جبرانی: session_selection → make_up_choice → cancelled_no_make_up."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "therapist_session_cancellation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapist_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="therapist",
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
        assert result.to_state == "make_up_choice"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="no_make_up",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "cancelled_no_make_up"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "cancelled_no_make_up"
        assert instance.is_completed is True
