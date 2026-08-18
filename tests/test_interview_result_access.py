"""Tests for interview-result submission access control."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.core.interview_result_access import (
    assert_can_submit_interview_result,
    can_submit_interview_result,
)
from app.core.engine import UnauthorizedError
from app.models.operational_models import InterviewSlot, ProcessInstance, User


async def _make_user(
    db: AsyncSession, *, role: str, prefix: str, roles: list[str] | None = None
) -> User:
    uid = uuid.uuid4()
    role_list = list(roles) if roles is not None else [role]
    user = User(
        id=uid,
        username=f"{prefix}_{uuid.uuid4().hex[:10]}",
        email=f"{prefix}_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa=prefix,
        role=role,
        roles=role_list,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_instance_with_slot(
    db: AsyncSession,
    *,
    sample_student,
    interviewer_user_id: uuid.UUID | None,
    slot_created_by: uuid.UUID,
) -> tuple[ProcessInstance, InterviewSlot]:
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="interview_completed",
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db.add(inst)
    await db.flush()
    t0 = datetime.now(timezone.utc) + timedelta(days=1)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        course_type=None,
        mode="in_person",
        created_by=slot_created_by,
        interviewer_user_id=interviewer_user_id,
        assigned_student_id=sample_student.id,
        assigned_instance_id=inst.id,
    )
    db.add(slot)
    await db.flush()
    return inst, slot


@pytest.mark.asyncio
async def test_assigned_interviewer_can_submit_own_result(
    db_session: AsyncSession, sample_student
) -> None:
    iv = await _make_user(db_session, role="interviewer", prefix="iv_own")
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=iv.id,
        slot_created_by=iv.id,
    )
    assert await can_submit_interview_result(
        db_session,
        instance=inst,
        user=iv,
        trigger_event="interview_result_submitted",
    )


@pytest.mark.asyncio
async def test_other_interviewer_cannot_submit_result(
    db_session: AsyncSession, sample_student
) -> None:
    owner = await _make_user(db_session, role="interviewer", prefix="iv_owner")
    other = await _make_user(db_session, role="interviewer", prefix="iv_other")
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=owner.id,
        slot_created_by=owner.id,
    )
    assert not await can_submit_interview_result(
        db_session,
        instance=inst,
        user=other,
        trigger_event="interview_result_submitted",
    )


@pytest.mark.asyncio
async def test_staff_non_creator_cannot_submit_interview_result(
    db_session: AsyncSession, sample_student
) -> None:
    iv = await _make_user(db_session, role="interviewer", prefix="iv")
    staff = await _make_user(db_session, role="staff", prefix="staff")
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=iv.id,
        slot_created_by=iv.id,
    )
    assert not await can_submit_interview_result(
        db_session,
        instance=inst,
        user=staff,
        trigger_event="interview_result_submitted",
    )


@pytest.mark.asyncio
async def test_staff_slot_creator_can_submit_result(
    db_session: AsyncSession, sample_student
) -> None:
    iv = await _make_user(db_session, role="interviewer", prefix="iv")
    staff = await _make_user(db_session, role="staff", prefix="staff")
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=iv.id,
        slot_created_by=staff.id,
    )
    assert await can_submit_interview_result(
        db_session,
        instance=inst,
        user=staff,
        trigger_event="interview_result_submitted",
    )


@pytest.mark.asyncio
async def test_interviewer_creator_cannot_submit_when_other_interviewer_assigned(
    db_session: AsyncSession, sample_student
) -> None:
    assigned = await _make_user(db_session, role="interviewer", prefix="iv_assigned")
    creator = await _make_user(db_session, role="interviewer", prefix="iv_creator")
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=assigned.id,
        slot_created_by=creator.id,
    )
    assert not await can_submit_interview_result(
        db_session,
        instance=inst,
        user=creator,
        trigger_event="interview_result_submitted",
    )


@pytest.mark.asyncio
async def test_admin_can_submit_any_interview_result(
    db_session: AsyncSession, sample_student
) -> None:
    iv = await _make_user(db_session, role="interviewer", prefix="iv")
    admin = await _make_user(db_session, role="admin", prefix="admin")
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=iv.id,
        slot_created_by=iv.id,
    )
    assert await can_submit_interview_result(
        db_session,
        instance=inst,
        user=admin,
        trigger_event="interview_result_submitted",
    )


@pytest.mark.asyncio
async def test_assert_rejects_staff_non_creator_interview_result_trigger(
    db_session: AsyncSession, sample_student
) -> None:
    iv = await _make_user(db_session, role="interviewer", prefix="iv")
    staff = await _make_user(db_session, role="staff", prefix="staff")
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=iv.id,
        slot_created_by=iv.id,
    )
    with pytest.raises(UnauthorizedError):
        await assert_can_submit_interview_result(
            db_session,
            instance=inst,
            user=staff,
            trigger_event="interview_result_submitted",
        )


@pytest.mark.asyncio
async def test_faculty_1_assigned_like_sara_can_submit_result(
    db_session: AsyncSession, sample_student
) -> None:
    """سارا طراوتی: نقش اصلی faculty_1 بدون interviewer در آرایهٔ roles."""
    sara = await _make_user(
        db_session,
        role="faculty_1",
        prefix="sara_taravati",
        roles=["faculty_1"],
    )
    staff = await _make_user(db_session, role="staff", prefix="staff")
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=sara.id,
        slot_created_by=staff.id,
    )
    assert await can_submit_interview_result(
        db_session,
        instance=inst,
        user=sara,
        trigger_event="interview_result_submitted",
    )
    await assert_can_submit_interview_result(
        db_session,
        instance=inst,
        user=sara,
        trigger_event="interview_result_submitted",
    )


@pytest.mark.asyncio
async def test_faculty_1_cannot_submit_other_interviewers_result(
    db_session: AsyncSession, sample_student
) -> None:
    assigned = await _make_user(db_session, role="interviewer", prefix="iv")
    sara = await _make_user(
        db_session, role="faculty_1", prefix="sara_other", roles=["faculty_1"]
    )
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=assigned.id,
        slot_created_by=assigned.id,
    )
    assert not await can_submit_interview_result(
        db_session,
        instance=inst,
        user=sara,
        trigger_event="interview_result_submitted",
    )


@pytest.mark.asyncio
async def test_faculty_1_can_submit_comprehensive_eval_triggers(
    db_session: AsyncSession, sample_student
) -> None:
    sara = await _make_user(
        db_session, role="faculty_1", prefix="sara_comp", roles=["faculty_1"]
    )
    inst, _slot = await _make_instance_with_slot(
        db_session,
        sample_student=sample_student,
        interviewer_user_id=sara.id,
        slot_created_by=sara.id,
    )
    inst.process_code = "comprehensive_course_registration"
    await db_session.flush()
    for trigger in (
        "interview_result_accepted",
        "interview_result_rejected",
        "interview_result_rejected_with_suggestion",
    ):
        assert await can_submit_interview_result(
            db_session,
            instance=inst,
            user=sara,
            trigger_event=trigger,
        )
