"""Test therapy_session_increase as جریان بزرگ (BUILD_TODO دسته ه — سایر جریان‌های بزرگ ۳)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTherapySessionIncreaseFlow:

    async def test_therapy_session_increase_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند افزایش جلسات درمان لود و استارت می‌شود؛ state اول request_submitted است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "therapy_session_increase.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_session_increase",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "therapy_session_increase"
        assert instance.current_state_code == "request_submitted"
        assert instance.is_completed is False

    async def test_therapy_session_increase_flow_to_session_added(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان: request_submitted → therapist_review → session_added (تایید درمانگر)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "therapy_session_increase.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_session_increase",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="day_time_entered",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "therapist_review"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="therapist_approved",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "session_added"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "session_added"
        assert instance.is_completed is True
