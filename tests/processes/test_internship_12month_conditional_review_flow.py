"""Test internship_12month_conditional_review flow (BUILD_TODO ه — بسته انترنشیپ)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestInternship12MonthConditionalReviewFlow:

    async def test_internship_12month_conditional_review_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند internship_12month_conditional_review لود و استارت می‌شود؛ state اول month_12_trigger است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "internship_12month_conditional_review.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="internship_12month_conditional_review",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "internship_12month_conditional_review"
        assert instance.current_state_code == "month_12_trigger"
        assert instance.is_completed is False

    async def test_internship_12month_conditional_review_flow_to_result_unrestricted(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریو: month_12_trigger → supervision_review → interview_scheduling → interview_held → result_unrestricted."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "internship_12month_conditional_review.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="internship_12month_conditional_review",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        # month_12_trigger -> supervision_review
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="alert_sent",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "supervision_review"

        # supervision_review -> interview_scheduling
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="permit_issued",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "interview_scheduling"

        # interview_scheduling -> interview_held
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="interview_scheduled",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "interview_held"

        # interview_held -> result_unrestricted
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="result_unrestricted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "result_unrestricted"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "result_unrestricted"
        assert instance.is_completed is True

