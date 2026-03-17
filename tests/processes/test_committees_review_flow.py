"""Test committees_review flow (BUILD_TODO hande h - item 9)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestCommitteesReviewFlow:

    async def test_committees_review_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "committees_review.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="committees_review",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert instance.process_code == "committees_review"
        assert instance.current_state_code == "supervision_review"
        assert instance.is_completed is False

    async def test_committees_review_flow_to_education_terminated(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "committees_review.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="committees_review",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="supervision_recommendation_submitted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "education_review"
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="education_verdict_terminate",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "education_terminated"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "education_terminated"
        assert instance.is_completed is True
