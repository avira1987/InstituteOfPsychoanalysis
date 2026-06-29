"""Test article_writing_completion flow — فرایند ۶۹."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestArticleWritingCompletionFlow:

    async def test_article_writing_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "article_writing_completion.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="article_writing_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        assert instance.process_code == "article_writing_completion"
        assert instance.current_state_code == "course_active"
        assert instance.is_completed is False

    async def test_article_writing_completion_flow_to_eval_pending(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "article_writing_completion.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="article_writing_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        r1 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="completion_ticked",
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()
        assert r1.success is True
        assert r1.to_state == "class_closed_student"

        r2 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="defense_requested",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert r2.success is True
        assert r2.to_state == "instructor_eval_pending"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "instructor_eval_pending"

    async def test_article_writing_completion_evaluation_submitted(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "article_writing_completion.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="article_writing_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="completion_ticked",
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="defense_requested",
            actor_id=sample_user.id,
            actor_role="student",
            payload={
                "q7_has_positive": "yes",
                "q7_positive_traits": ["punctuality"],
                "q8_has_negative": "no",
            },
        )
        await db_session.commit()

        r3 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="evaluation_submitted",
            actor_id=sample_user.id,
            actor_role="instructor",
            payload={
                "q7_has_positive": "yes",
                "q7_positive_traits": ["punctuality", "strong_writing"],
                "q8_has_negative": "no",
            },
        )
        await db_session.commit()
        assert r3.success is True
        assert r3.to_state == "completed_to_defense"

        await db_session.refresh(sample_student)
        log = (sample_student.extra_data or {}).get("monitoring_performance_log") or []
        assert any(e.get("kind") == "positive" for e in log)
