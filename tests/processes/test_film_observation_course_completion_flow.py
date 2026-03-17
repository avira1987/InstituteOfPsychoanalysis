"""Test film_observation_course_completion flow (BUILD_TODO ه — بسته completion/evaluation)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestFilmObservationCourseCompletionFlow:

    async def test_film_observation_course_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند film_observation_course_completion لود و استارت می‌شود؛ state اول grades_entry است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "film_observation_course_completion.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="film_observation_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        assert instance.process_code == "film_observation_course_completion"
        assert instance.current_state_code == "grades_entry"
        assert instance.is_completed is False

    async def test_film_observation_course_completion_flow_to_grades_locked(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی نرمال: grades_entry → grades_locked با trigger grades_submitted."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "film_observation_course_completion.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="film_observation_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="grades_submitted",
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        assert result.success is True
        assert result.to_state == "grades_locked"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "grades_locked"
        assert instance.is_completed is True

