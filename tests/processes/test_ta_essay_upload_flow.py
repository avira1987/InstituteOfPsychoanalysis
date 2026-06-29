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

    async def test_ta_essay_upload_flow_to_content_published(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی خوش‌بینانه: session_ended → … → content_published."""
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

        steps = [
            ("process_started", "ta_upload"),
            ("uploaded", "instructor_review"),
            ("accepted", "reference_center_editing"),
            ("sent_to_marketing", "marketing_publication"),
            ("publication_recorded", "content_published"),
        ]
        for trigger, expected_state in steps:
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role="admin",
            )
            await db_session.commit()
            assert result.success is True, f"trigger {trigger} failed: {result.error}"
            assert result.to_state == expected_state

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "content_published"
        assert instance.is_completed is True
