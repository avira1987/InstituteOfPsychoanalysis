"""Test ta_instructor_leave flow (BUILD_TODO ه — بسته TA)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTaInstructorLeaveFlow:

    async def test_ta_instructor_leave_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ta_instructor_leave لود و استارت می‌شود؛ state اول leave_request است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_instructor_leave.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_instructor_leave",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "ta_instructor_leave"
        assert instance.current_state_code == "leave_request"
        assert instance.is_completed is False

    async def test_ta_instructor_leave_flow_to_leave_approved_via_substitute(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریو: leave_request → course_committee_review → substitute_assigned → leave_approved."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_instructor_leave.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_instructor_leave",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        # leave_request -> course_committee_review
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="request_submitted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "course_committee_review"

        # course_committee_review -> substitute_assigned
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="substitute_chosen",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "substitute_assigned"

        # substitute_assigned -> leave_approved
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="substitute_confirmed",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "leave_approved"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "leave_approved"
        assert instance.is_completed is True

