"""Test payment callback -> session_payment transition (BUILD_TODO § و — بخش ۶)."""

import uuid
import pytest
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance, PaymentPending


@pytest.mark.asyncio
async def test_callback_success_fires_payment_successful_transition(
    db_session: AsyncSession, sample_student, sample_user
):
    """When a pending payment exists for session_payment in awaiting_payment, running payment_successful moves to payment_confirmed."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="session_payment",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    await db_session.commit()

    # Move to awaiting_payment (student_initiated_payment -> payment_selection, then payment_selection_submitted -> awaiting_payment)
    await engine.execute_transition(
        instance_id=instance.id,
        trigger_event="student_initiated_payment",
        actor_id=sample_user.id,
        actor_role="student",
    )
    await db_session.commit()

    # payment_selection -> awaiting_payment may have conditions; set state directly for this test
    inst = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))).scalars().first()
    inst.current_state_code = "awaiting_payment"
    await db_session.flush()

    authority = "MOCK-test-auth-123"
    pending = PaymentPending(
        id=uuid.uuid4(),
        authority=authority,
        instance_id=instance.id,
        student_id=sample_student.id,
        amount=500_000,
    )
    db_session.add(pending)
    await db_session.commit()

    # Run the transition that callback would run
    system_actor_id = sample_user.id  # use existing user as system actor
    await engine.execute_transition(
        instance_id=instance.id,
        trigger_event="payment_successful",
        actor_id=system_actor_id,
        actor_role="system",
        payload={"amount": 500_000, "ref_id": "REF-123"},
    )
    await db_session.commit()

    inst = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))).scalars().first()
    assert inst.current_state_code == "payment_confirmed"
    assert inst.is_completed is True


@pytest.mark.asyncio
async def test_payment_unsuccessful_transition_to_payment_failed(
    db_session: AsyncSession, sample_student, sample_user
):
    """دسته و: وقتی پرداخت ناموفق است، transition payment_unsuccessful به payment_failed انجام می‌شود."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="session_payment",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    await db_session.commit()

    inst = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))).scalars().first()
    inst.current_state_code = "awaiting_payment"
    await db_session.flush()

    await engine.execute_transition(
        instance_id=instance.id,
        trigger_event="payment_unsuccessful",
        actor_id=sample_user.id,
        actor_role="system",
    )
    await db_session.commit()

    inst = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))).scalars().first()
    assert inst.current_state_code == "payment_failed"
    assert inst.is_completed is False
