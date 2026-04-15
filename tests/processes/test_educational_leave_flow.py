"""Test educational_leave as جریان بزرگ (BUILD_TODO دسته ه — بخش ۲۴: مرخصی آموزشی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestEducationalLeaveFlow:

    async def test_educational_leave_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند مرخصی آموزشی لود و استارت می‌شود؛ state اول request_form است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "educational_leave.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="educational_leave",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "educational_leave"
        assert instance.current_state_code == "request_form"
        assert instance.is_completed is False

    async def test_educational_leave_flow_to_rejected(
        self, db_session: AsyncSession, sample_student, sample_user, sample_student_user
    ):
        """جریان تا رد درخواست: request_form → committee_review → session_scheduled → committee_decision → rejected."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "educational_leave.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="educational_leave",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={"leave_terms": 1},
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "committee_review"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="committee_set_meeting",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "session_scheduled"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="meeting_held",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "committee_decision"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="committee_rejected",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "rejected"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "rejected"
        assert instance.is_completed is True
