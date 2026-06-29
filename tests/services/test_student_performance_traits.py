"""Tests for record_student_performance_traits action."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.services.action_handler import ActionHandler


@pytest.mark.asyncio
async def test_record_student_performance_traits_positive_only(
    db_session: AsyncSession, sample_student, sample_user
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

    ctx = dict(instance.context_data or {})
    ctx.update({
        "q7_has_positive": "yes",
        "q7_positive_traits": ["active_participation"],
        "q7_positive_note": "مشارکت عالی",
        "q8_has_negative": "no",
        "instructor_name": "دکتر تست",
    })
    instance.context_data = ctx

    handler = ActionHandler(db_session)
    result = await handler._handle_record_student_performance_traits(
        {"type": "record_student_performance_traits", "payload": {"source": "article_writing_completion"}},
        instance,
        ctx,
    )
    await db_session.commit()

    assert result == "record_student_performance_traits"
    await db_session.refresh(sample_student)
    log = (sample_student.extra_data or {}).get("monitoring_performance_log") or []
    assert len(log) == 1
    assert log[0]["kind"] == "positive"
    assert "active_participation" in log[0]["traits"]
    assert log[0]["note"] == "مشارکت عالی"


@pytest.mark.asyncio
async def test_record_student_performance_traits_both_kinds(
    db_session: AsyncSession, sample_student, sample_user
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

    ctx = {
        "q7_has_positive": "yes",
        "q7_positive_traits": ["punctuality"],
        "q8_has_negative": "yes",
        "q8_negative_traits": ["missed_deadlines"],
    }
    instance.context_data = ctx

    handler = ActionHandler(db_session)
    await handler._handle_record_student_performance_traits(
        {"type": "record_student_performance_traits", "payload": {}},
        instance,
        ctx,
    )
    await db_session.commit()

    await db_session.refresh(sample_student)
    log = (sample_student.extra_data or {}).get("monitoring_performance_log") or []
    kinds = {e.get("kind") for e in log}
    assert kinds == {"positive", "negative"}
