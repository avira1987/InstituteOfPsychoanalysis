"""Test extra_session as جریان بزرگ (BUILD_TODO item ۲۱ — ه بخش ۱۸: جلسه اضافی درمان آموزشی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestExtraSessionFlow:

    async def test_extra_session_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند جلسه اضافی درمان آموزشی لود و استارت می‌شود؛ state اول extra_request است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "extra_session.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="extra_session",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "extra_session"
        assert instance.current_state_code == "extra_request"
        assert instance.is_completed is False

    async def test_extra_session_full_flow_to_extra_session_completed(
        self, db_session: AsyncSession, sample_student, sample_user, sample_student_user
    ):
        """جریان کامل: extra_request → therapist_review → payment_required → extra_session_confirmed → extra_session_completed."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "extra_session.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="extra_session",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        # extra_requested → therapist_review (required_role: student)
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="extra_requested",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "therapist_review"

        # therapist_approved → payment_required (required_role: therapist; admin can do)
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="therapist_approved",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "payment_required"

        # payment_completed → extra_session_confirmed
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_completed",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "extra_session_confirmed"

        # session_held → extra_session_completed (required_role: therapist; admin can do)
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="session_held",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "extra_session_completed"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "extra_session_completed"
        assert instance.is_completed is True
