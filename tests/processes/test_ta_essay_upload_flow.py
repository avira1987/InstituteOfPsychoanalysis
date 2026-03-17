"""Test ta_essay_upload flow (BUILD_TODO ه — بسته TA)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTaEssayUploadFlow:

    async def test_ta_essay_upload_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ta_essay_upload لود و استارت می‌شود؛ state اول session_ended است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_essay_upload.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_essay_upload",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "ta_essay_upload"
        assert instance.current_state_code == "session_ended"
        assert instance.is_completed is False

    async def test_ta_essay_upload_flow_to_approved_reference_center(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی خوش‌بینانه: session_ended → ta_upload → instructor_review → approved_reference_center."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_essay_upload.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_essay_upload",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        # session_ended -> ta_upload
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="process_started",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "ta_upload"

        # ta_upload -> instructor_review
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="uploaded",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "instructor_review"

        # instructor_review -> approved_reference_center
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="accepted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "approved_reference_center"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "approved_reference_center"
        assert instance.is_completed is True

