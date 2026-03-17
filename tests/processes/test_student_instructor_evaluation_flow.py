"""Test student_instructor_evaluation flow (BUILD_TODO ه — بسته completion/evaluation)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestStudentInstructorEvaluationFlow:

    async def test_student_instructor_evaluation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند student_instructor_evaluation لود و استارت می‌شود؛ state اول evaluation_open است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "student_instructor_evaluation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="student_instructor_evaluation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "student_instructor_evaluation"
        assert instance.current_state_code == "evaluation_open"
        assert instance.is_completed is False

    async def test_student_instructor_evaluation_flow_to_evaluation_closed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریو: evaluation_open → evaluation_closed با trigger deadline_reached."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "student_instructor_evaluation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="student_instructor_evaluation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="deadline_reached",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert result.success is True
        assert result.to_state == "evaluation_closed"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "evaluation_closed"
        assert instance.is_completed is True

