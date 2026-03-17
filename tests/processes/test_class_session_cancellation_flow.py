"""Test class_session_cancellation as جریان بزرگ (BUILD_TODO item ۲۴ — ه بخش ۲۱: کنسل جلسات کلاس درسی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestClassSessionCancellationFlow:

    async def test_class_session_cancellation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند کنسل جلسات کلاس درسی لود و استارت می‌شود؛ state اول cancellation_request است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "class_session_cancellation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="class_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        assert instance.process_code == "class_session_cancellation"
        assert instance.current_state_code == "cancellation_request"
        assert instance.is_completed is False

    async def test_class_session_cancellation_flow_to_makeup_scheduled(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان: cancellation_request → makeup_scheduled با trigger cancellation_confirmed."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "class_session_cancellation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="class_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="cancellation_confirmed",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "makeup_scheduled"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "makeup_scheduled"
        assert instance.is_completed is True
