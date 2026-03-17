"""Test ta_track_change flow (BUILD_TODO ه — بسته TA)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTaTrackChangeFlow:

    async def test_ta_track_change_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ta_track_change لود و استارت می‌شود؛ state اول ta_click است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_track_change.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_track_change",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "ta_track_change"
        assert instance.current_state_code == "ta_click"
        assert instance.is_completed is False

    async def test_ta_track_change_flow_to_track_applied(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریو: ta_click → path_selected → course_committee_review → meeting_scheduled → track_applied."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_track_change.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_track_change",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        # ta_click -> path_selected
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="path_chosen",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "path_selected"

        # path_selected -> course_committee_review
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="request_sent",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "course_committee_review"

        # course_committee_review -> meeting_scheduled
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="meeting_registered",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "meeting_scheduled"

        # meeting_scheduled -> track_applied
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="approved",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "track_applied"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "track_applied"
        assert instance.is_completed is True

