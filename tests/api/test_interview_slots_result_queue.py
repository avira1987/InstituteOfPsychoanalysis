"""Tests for GET /api/interview-slots/result-queue."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.api.interview_slots_routes import list_interview_result_queue
from app.models.operational_models import InterviewSlot, ProcessInstance, User


async def _make_user(db: AsyncSession, *, role: str, prefix: str) -> User:
    user = User(
        id=uuid.uuid4(),
        username=f"{prefix}_{uuid.uuid4().hex[:10]}",
        email=f"{prefix}_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa=prefix,
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_queue_row(
    db: AsyncSession,
    *,
    sample_student,
    creator: User,
    interviewer: User | None,
    state: str,
) -> tuple[InterviewSlot, ProcessInstance]:
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code=state,
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db.add(inst)
    await db.flush()
    t0 = datetime.now(timezone.utc) + timedelta(days=2)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        course_type="introductory",
        mode="in_person",
        created_by=creator.id,
        interviewer_user_id=interviewer.id if interviewer else None,
        assigned_student_id=sample_student.id,
        assigned_instance_id=inst.id,
    )
    db.add(slot)
    await db.flush()
    return slot, inst


@pytest.mark.asyncio
async def test_result_queue_shows_slot_for_creator_staff(
    db_session: AsyncSession, sample_student
) -> None:
    staff = await _make_user(db_session, role="staff", prefix="staff")
    iv = await _make_user(db_session, role="interviewer", prefix="iv")
    await _make_queue_row(
        db_session,
        sample_student=sample_student,
        creator=staff,
        interviewer=iv,
        state="interview_completed",
    )
    out = await list_interview_result_queue(include_past=False, db=db_session, user=staff)
    assert len(out["items"]) == 1
    item = out["items"][0]
    assert item["is_slot_creator"] is True
    assert item["can_submit_result"] is True


@pytest.mark.asyncio
async def test_result_queue_hides_other_staff_slots(
    db_session: AsyncSession, sample_student
) -> None:
    staff = await _make_user(db_session, role="staff", prefix="staff")
    other_staff = await _make_user(db_session, role="staff", prefix="staff2")
    iv = await _make_user(db_session, role="interviewer", prefix="iv")
    await _make_queue_row(
        db_session,
        sample_student=sample_student,
        creator=staff,
        interviewer=iv,
        state="interview_completed",
    )
    out = await list_interview_result_queue(include_past=False, db=db_session, user=other_staff)
    assert out["items"] == []


@pytest.mark.asyncio
async def test_result_queue_can_advance_payment_confirmed(
    db_session: AsyncSession, sample_student
) -> None:
    admin = await _make_user(db_session, role="admin", prefix="admin")
    iv = await _make_user(db_session, role="interviewer", prefix="iv")
    await _make_queue_row(
        db_session,
        sample_student=sample_student,
        creator=admin,
        interviewer=iv,
        state="interview_payment_confirmed",
    )
    out = await list_interview_result_queue(include_past=False, db=db_session, user=admin)
    assert len(out["items"]) == 1
    assert out["items"][0]["can_advance"] is True
    assert out["items"][0]["can_submit_result"] is False
