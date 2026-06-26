"""Prefill for committees_review / specialized_commission_review forms."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance
from app.services.process_form_prefill import apply_pre_filled_fields


@pytest.mark.asyncio
async def test_committees_review_prefill_from_therapy_parent(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "therapy_early_termination.json")
    await load_process(db_session, processes_dir / "committees_review.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    parent = await engine.start_process(
        process_code="therapy_early_termination",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="therapist",
        initial_context={
            "termination_reason_code": 4,
            "termination_note": "یادداشت تست",
        },
    )
    child = await engine.start_process(
        process_code="committees_review",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="admin",
        initial_context={
            "parent_instance_id": str(parent.id),
            "parent_process_code": "therapy_early_termination",
            "entry_reason": "termination_reason_4",
        },
    )
    await db_session.commit()

    ctx = dict(child.context_data or {})
    out = await apply_pre_filled_fields(
        db_session,
        "committees_review",
        "supervision_review",
        ctx,
        student_id=sample_student.id,
    )
    assert "۴" in out.get("termination_reason_display", "")
    assert out.get("entry_source_display")
    merged = await apply_pre_filled_fields(
        db_session,
        "specialized_commission_review",
        "commission_review",
        {
            "parent_instance_id": str(parent.id),
            "parent_process_code": "therapy_early_termination",
        },
        student_id=sample_student.id,
    )
    assert "یادداشت تست" in (merged.get("termination_note_display") or "")


@pytest.mark.asyncio
async def test_committees_education_review_prefill_supervision_display(
    db_session: AsyncSession, sample_student,
):
    inst = ProcessInstance(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        process_code="committees_review",
        current_state_code="education_review",
        context_data={
            "nezarat_recommendation_code": "continue",
            "nezarat_recommendation_fa": "پیشنهاد ادامه",
        },
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.commit()

    out = await apply_pre_filled_fields(
        db_session,
        "committees_review",
        "education_review",
        dict(inst.context_data),
        student_id=sample_student.id,
    )
    assert "پیشنهاد ادامه" in out.get("supervision_recommendation_display", "")
