"""Tests for rescheduling booked interview slots and join-link gating."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.api.interview_slots_routes import (
    CreateInterviewSlotBody,
    _can_reschedule_booked_slot,
    _is_meeting_link_visible_for_user,
)
from app.models.operational_models import InterviewSlot, ProcessInstance, Student, User
from app.services.interview_slot_service import reschedule_booked_interview_slot


def _interviewer(uid: uuid.UUID | None = None) -> User:
    return User(
        id=uid or uuid.uuid4(),
        username=f"iv_{uuid.uuid4().hex[:8]}",
        email=f"iv_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبه‌گر",
        role="interviewer",
    )


@pytest.mark.asyncio
async def test_reschedule_updates_slot_and_resets_join_gate(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    t0 = datetime.now(timezone.utc) + timedelta(days=5)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.example/iv",
        assigned_student_id=sample_student.id,
        booking_payment_deadline_at=None,
        student_join_open=True,
        reminder_sent_at=datetime.now(timezone.utc),
    )
    db_session.add(slot)
    await db_session.flush()

    new_start = datetime.now(timezone.utc) + timedelta(days=7)
    new_end = new_start + timedelta(hours=1)
    out = await reschedule_booked_interview_slot(
        db_session,
        slot=slot,
        new_starts_at=new_start,
        new_ends_at=new_end,
    )
    assert out["success"] is True
    assert slot.starts_at == new_start
    assert slot.ends_at == new_end
    assert slot.student_join_open is False
    assert slot.reminder_sent_at is None


@pytest.mark.asyncio
async def test_reschedule_rejects_unpaid_booking(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    t0 = datetime.now(timezone.utc) + timedelta(days=2)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        assigned_student_id=sample_student.id,
        booking_payment_deadline_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db_session.add(slot)
    await db_session.flush()

    out = await reschedule_booked_interview_slot(
        db_session,
        slot=slot,
        new_starts_at=t0 + timedelta(days=1),
        new_ends_at=t0 + timedelta(days=1, hours=1),
    )
    assert out["success"] is False
    assert "پرداخت" in (out.get("error") or "")


@pytest.mark.asyncio
async def test_student_link_hidden_before_rescheduled_window(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
) -> None:
    new_start = datetime.now(timezone.utc) + timedelta(days=2)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=new_start,
        ends_at=new_start + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.example/rescheduled",
        assigned_student_id=sample_student.id,
        booking_payment_deadline_at=None,
        student_join_open=False,
    )
    db_session.add(slot)
    await db_session.flush()

    now = new_start - timedelta(hours=1)
    assert _is_meeting_link_visible_for_user(slot, sample_student_user, now) is False


@pytest.mark.asyncio
async def test_reschedule_sends_online_sms(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
) -> None:
    sample_student_user.phone = "09121234567"
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=4)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        course_type="introductory",
        meeting_link="https://meet.example/sms",
        assigned_student_id=sample_student.id,
        booking_payment_deadline_at=None,
    )
    db_session.add(slot)
    await db_session.flush()

    mock_result = AsyncMock()
    mock_result.success = True
    with patch(
        "app.services.interview_slot_service.notification_service.send_notification",
        new=AsyncMock(return_value=mock_result),
    ) as send_mock:
        out = await reschedule_booked_interview_slot(
            db_session,
            slot=slot,
            new_starts_at=t0 + timedelta(days=1),
            new_ends_at=t0 + timedelta(days=1, hours=1),
        )
    assert out["success"] is True
    assert out["sms_sent"] is True
    send_mock.assert_awaited_once()
    args = send_mock.await_args.args
    assert args[0] == "sms"
    assert args[1] == "interview_scheduled_student_online"


@pytest.mark.asyncio
async def test_reschedule_syncs_process_context(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    inst_id = uuid.uuid4()
    instance = ProcessInstance(
        id=inst_id,
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="interview_payment_confirmed",
        context_data={},
    )
    db_session.add(instance)
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=3)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.example/ctx",
        assigned_student_id=sample_student.id,
        assigned_instance_id=inst_id,
        booking_payment_deadline_at=None,
    )
    db_session.add(slot)
    await db_session.flush()

    new_start = t0 + timedelta(days=2)
    await reschedule_booked_interview_slot(
        db_session,
        slot=slot,
        new_starts_at=new_start,
        new_ends_at=new_start + timedelta(hours=1),
    )
    await db_session.refresh(instance)
    ctx = instance.context_data or {}
    from app.utils.shamsi_calendar_utils import tehran_datetime_parts

    expected_date, _ = tehran_datetime_parts(new_start)
    assert ctx.get("interview_date") == expected_date


def test_can_reschedule_staff_and_own_interviewer() -> None:
    staff = User(
        id=uuid.uuid4(),
        username="staff1",
        email="s@test.com",
        hashed_password="x",
        role="staff",
    )
    iv_id = uuid.uuid4()
    interviewer = _interviewer(iv_id)
    colleague = _interviewer()
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=datetime.now(timezone.utc) + timedelta(days=1),
        ends_at=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
        mode="online",
        created_by=uuid.uuid4(),
        interviewer_user_id=iv_id,
        assigned_student_id=uuid.uuid4(),
    )
    assert _can_reschedule_booked_slot(staff, slot) is True
    assert _can_reschedule_booked_slot(interviewer, slot) is True

    slot.interviewer_user_id = colleague.id
    assert _can_reschedule_booked_slot(interviewer, slot) is False


@pytest.mark.asyncio
async def test_create_slot_requires_interviewer_field(
    db_session: AsyncSession,
) -> None:
    """فیلد interviewer_user_id در بدنهٔ ایجاد اسلات الزامی است."""
    from pydantic import ValidationError

    t0 = datetime.now(timezone.utc) + timedelta(days=4)
    with pytest.raises(ValidationError):
        CreateInterviewSlotBody(
            starts_at=t0,
            ends_at=t0 + timedelta(hours=1),
            course_type="introductory",
            mode="online",
        )
