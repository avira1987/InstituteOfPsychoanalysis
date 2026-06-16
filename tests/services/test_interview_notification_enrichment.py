"""Tests for interview slot context enrichment, payment-flow visibility, and notification conditions."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.api.interview_slots_routes import _is_meeting_link_visible_for_user
from app.models.operational_models import InterviewSlot, ProcessInstance, Student, User
from app.services.action_handler import ActionHandler
from app.services.interview_slot_service import enrich_interview_notification_context


@pytest.mark.asyncio
async def test_enrich_interview_notification_context_online_link(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
) -> None:
    sample_student_user.phone = "09120001122"
    await db_session.flush()
    inst_id = uuid.uuid4()
    instance = ProcessInstance(
        id=inst_id,
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="interview_payment_confirmed",
        context_data={"selected_timeslot": ""},
    )
    db_session.add(instance)
    await db_session.flush()
    t0 = datetime.now(timezone.utc) + timedelta(days=1)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.example/iv",
        assigned_student_id=sample_student.id,
        assigned_instance_id=inst_id,
    )
    db_session.add(slot)
    await db_session.flush()
    instance.context_data = {**dict(instance.context_data or {}), "selected_timeslot": str(slot.id)}
    await db_session.flush()

    ctx = await enrich_interview_notification_context(db_session, instance)
    assert ctx.get("interview_type") == "online"
    assert ctx.get("interview_link") == "https://meet.example/iv"
    assert "interview_date" in ctx
    assert ctx.get("student_name")


@pytest.mark.asyncio
async def test_enrich_interview_in_person_location(db_session: AsyncSession, sample_student: Student) -> None:
    inst_id = uuid.uuid4()
    instance = ProcessInstance(
        id=inst_id,
        process_code="comprehensive_course_registration",
        student_id=sample_student.id,
        current_state_code="interview_completed",
        context_data={},
    )
    db_session.add(instance)
    await db_session.flush()
    t0 = datetime.now(timezone.utc) + timedelta(days=2)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="in_person",
        location_fa="ساختمان الف، طبقه ۲",
        assigned_student_id=sample_student.id,
        assigned_instance_id=inst_id,
    )
    db_session.add(slot)
    await db_session.flush()

    ctx = await enrich_interview_notification_context(db_session, instance)
    assert ctx.get("interview_type") == "in_person"
    assert "ساختمان" in (ctx.get("interview_location") or "")


@pytest.mark.asyncio
async def test_notification_skipped_when_condition_fails(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
) -> None:
    sample_student_user.phone = "09123334455"
    await db_session.flush()
    instance = ProcessInstance(
        id=uuid.uuid4(),
        process_code="comprehensive_course_registration",
        student_id=sample_student.id,
        current_state_code="interview_payment",
        context_data={"interview_type": "in_person"},
    )
    db_session.add(instance)
    await db_session.flush()

    handler = ActionHandler(db_session)
    results = await handler.handle_actions(
        [
            {
                "type": "notification",
                "notification_type": "sms",
                "template": "interview_scheduled_student_online",
                "recipients": ["student"],
                "condition": "interview_type == 'online'",
            }
        ],
        instance,
        {},
    )
    assert results[0]["success"] is True
    assert "skipped_condition" in str(results[0].get("detail", ""))


@pytest.mark.asyncio
async def test_interviewer_link_visible_after_payment_deadline_cleared(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    uid = uuid.uuid4()
    interviewer = User(
        id=uid,
        username=f"iv_{uuid.uuid4().hex[:8]}",
        email=f"iv_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبه‌گر تست",
        role="interviewer",
        phone="09127777777",
    )
    db_session.add(interviewer)
    await db_session.flush()
    t0 = datetime.now(timezone.utc) + timedelta(days=3)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.example/post-pay",
        assigned_student_id=sample_student.id,
        assigned_instance_id=None,
        interviewer_user_id=uid,
        booking_payment_deadline_at=None,
    )
    db_session.add(slot)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    assert _is_meeting_link_visible_for_user(slot, interviewer, now) is True


@pytest.mark.asyncio
async def test_student_link_visible_after_payment_deadline_cleared(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
) -> None:
    sample_student_user.role = "student"
    await db_session.flush()
    t0 = datetime.now(timezone.utc) + timedelta(days=3)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.example/post-pay-student",
        assigned_student_id=sample_student.id,
        booking_payment_deadline_at=None,
    )
    db_session.add(slot)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    assert _is_meeting_link_visible_for_user(slot, sample_student_user, now) is True


@pytest.mark.asyncio
async def test_student_link_hidden_while_payment_deadline_active(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
) -> None:
    t0 = datetime.now(timezone.utc) + timedelta(days=3)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.example/pre-pay-student",
        assigned_student_id=sample_student.id,
        booking_payment_deadline_at=datetime.now(timezone.utc) + timedelta(minutes=9),
    )
    db_session.add(slot)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    assert _is_meeting_link_visible_for_user(slot, sample_student_user, now) is False


@pytest.mark.asyncio
async def test_interviewer_link_hidden_while_payment_deadline_active(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    uid = uuid.uuid4()
    interviewer = User(
        id=uid,
        username=f"iv2_{uuid.uuid4().hex[:8]}",
        email=f"iv2_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبه‌گر ۲",
        role="interviewer",
    )
    db_session.add(interviewer)
    await db_session.flush()
    t0 = datetime.now(timezone.utc) + timedelta(days=3)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.example/pre-pay",
        assigned_student_id=sample_student.id,
        interviewer_user_id=uid,
        booking_payment_deadline_at=datetime.now(timezone.utc) + timedelta(minutes=9),
    )
    db_session.add(slot)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    assert _is_meeting_link_visible_for_user(slot, interviewer, now) is False
