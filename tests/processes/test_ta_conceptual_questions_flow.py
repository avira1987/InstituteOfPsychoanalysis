"""Test ta_conceptual_questions flow (BUILD_TODO ه — بسته TA)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.process_forms import get_process_forms
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestTaConceptualQuestionsFlow:

    async def test_ta_conceptual_questions_forms_for_states(self):
        """فرم‌های آپلود، بررسی مدرس و اصلاح برای stateهای مربوط لود می‌شوند."""
        upload_forms = get_process_forms("ta_conceptual_questions", state_code="ta_upload")
        assert len(upload_forms) == 1
        upload_names = {f["name"] for f in upload_forms[0]["fields"]}
        assert {"question_1", "question_2", "question_3"}.issubset(upload_names)
        assert {"course_name", "session_number", "session_date"}.issubset(upload_names)

        review_forms = get_process_forms("ta_conceptual_questions", state_code="instructor_review")
        assert len(review_forms) == 1
        review_names = {f["name"] for f in review_forms[0]["fields"]}
        assert "question_1_status" in review_names
        assert "question_1_rejection_note" in review_names

        revision_forms = get_process_forms("ta_conceptual_questions", state_code="question_rejected")
        assert len(revision_forms) == 1
        assert {f["name"] for f in revision_forms[0]["fields"]} == {"question_1", "question_2", "question_3"}

    async def test_ta_conceptual_questions_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ta_conceptual_questions لود و استارت می‌شود؛ state اول session_ended است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_conceptual_questions.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_conceptual_questions",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "ta_conceptual_questions"
        assert instance.current_state_code == "session_ended"
        assert instance.is_completed is False

    async def test_ta_conceptual_questions_flow_to_questions_approved(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی خوش‌بینانه: session_ended → ta_upload → instructor_review → questions_approved."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_conceptual_questions.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_conceptual_questions",
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
            trigger_event="uploaded_on_time",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "instructor_review"

        # instructor_review -> questions_approved
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="all_accepted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "questions_approved"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "questions_approved"
        assert instance.is_completed is True

    async def test_ta_conceptual_questions_rejection_and_correction_flow(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی رد: instructor_review → question_rejected → instructor_review → questions_approved."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_conceptual_questions.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_conceptual_questions",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        for trigger in ("process_started", "uploaded_on_time"):
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role="admin",
            )
            await db_session.commit()
            assert result.success is True

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="question_rejected",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "question_rejected"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="corrected_and_uploaded",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "instructor_review"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="all_accepted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "questions_approved"

