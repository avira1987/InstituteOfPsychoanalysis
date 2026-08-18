"""تست تخصیص مصاحبه‌گر به اسلات و endpoint my-assigned."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.api.interview_slots_routes import (
    CreateInterviewSlotBody,
    UpdateInterviewSlotBody,
    create_slot,
    list_my_assigned_slots,
    update_slot,
)
from app.models.operational_models import InterviewSlot, PanelFlashMessage, Student, User


def _staff_user() -> User:
    return User(
        id=uuid.uuid4(),
        username=f"staff_{uuid.uuid4().hex[:8]}",
        email=f"staff_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="مدیر داخلی",
        role="staff",
        is_active=True,
    )


def _interviewer_user(*, phone: str = "09121234567") -> User:
    return User(
        id=uuid.uuid4(),
        username=f"iv_{uuid.uuid4().hex[:8]}",
        email=f"iv_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبه‌گر تست",
        role="interviewer",
        is_active=True,
        phone=phone,
    )


@pytest.mark.asyncio
async def test_create_slot_rejects_blank_interviewer(
    db_session: AsyncSession,
) -> None:
    """ایجاد اسلات بدون مصاحبه‌گر معتبر رد می‌شود."""
    from fastapi import HTTPException

    staff = _staff_user()
    db_session.add(staff)
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=4)
    body = CreateInterviewSlotBody(
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        course_type="introductory",
        mode="online",
        interviewer_user_id="   ",
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_slot(body=body, db=db_session, user=staff)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_slot_with_interviewer_assigns_and_notifies(
    db_session: AsyncSession,
) -> None:
    staff = _staff_user()
    interviewer = _interviewer_user()
    db_session.add_all([staff, interviewer])
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=5)
    body = CreateInterviewSlotBody(
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        course_type="comprehensive",
        mode="online",
        interviewer_user_id=str(interviewer.id),
    )
    out = await create_slot(body=body, db=db_session, user=staff)
    await db_session.flush()

    assert out["interviewer_user_id"] == str(interviewer.id)
    assert out["interviewer_name_fa"] == "مصاحبه‌گر تست"

    flash_rows = (
        await db_session.execute(
            PanelFlashMessage.__table__.select().where(
                PanelFlashMessage.user_id == interviewer.id
            )
        )
    ).all()
    assert len(flash_rows) >= 1


@pytest.mark.asyncio
async def test_update_slot_changes_interviewer(
    db_session: AsyncSession,
) -> None:
    staff = _staff_user()
    iv1 = _interviewer_user(phone="09121111111")
    iv2 = _interviewer_user(phone="09122222222")
    db_session.add_all([staff, iv1, iv2])
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=6)
    created = await create_slot(
        body=CreateInterviewSlotBody(
            starts_at=t0,
            ends_at=t0 + timedelta(hours=1),
            mode="online",
            interviewer_user_id=str(iv1.id),
        ),
        db=db_session,
        user=staff,
    )
    await db_session.flush()

    updated = await update_slot(
        slot_id=created["id"],
        body=UpdateInterviewSlotBody(interviewer_user_id=str(iv2.id)),
        db=db_session,
        user=staff,
    )
    assert updated["interviewer_user_id"] == str(iv2.id)
    assert updated["interviewer_name_fa"] == "مصاحبه‌گر تست"


@pytest.mark.asyncio
async def test_my_assigned_lists_free_slots_for_interviewer(
    db_session: AsyncSession,
) -> None:
    staff = _staff_user()
    interviewer = _interviewer_user()
    db_session.add_all([staff, interviewer])
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=7)
    await create_slot(
        body=CreateInterviewSlotBody(
            starts_at=t0,
            ends_at=t0 + timedelta(hours=1),
            course_type="introductory",
            mode="in_person",
            interviewer_user_id=str(interviewer.id),
        ),
        db=db_session,
        user=staff,
    )
    await db_session.flush()

    out = await list_my_assigned_slots(include_past=False, db=db_session, user=interviewer)
    assert len(out["slots"]) == 1
    assert out["slots"][0]["course_type"] == "introductory"


@pytest.mark.asyncio
async def test_update_booked_slot_interviewer_allowed(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    staff = _staff_user()
    iv1 = _interviewer_user(phone="09121111111")
    iv2 = _interviewer_user(phone="09122222222")
    db_session.add_all([staff, iv1, iv2])
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=8)
    created = await create_slot(
        body=CreateInterviewSlotBody(
            starts_at=t0,
            ends_at=t0 + timedelta(hours=1),
            mode="online",
            interviewer_user_id=str(iv1.id),
        ),
        db=db_session,
        user=staff,
    )
    slot = await db_session.get(InterviewSlot, uuid.UUID(created["id"]))
    assert slot is not None
    slot.assigned_student_id = sample_student.id
    slot.booking_payment_deadline_at = None
    await db_session.flush()

    updated = await update_slot(
        slot_id=created["id"],
        body=UpdateInterviewSlotBody(interviewer_user_id=str(iv2.id)),
        db=db_session,
        user=staff,
    )
    assert updated["interviewer_user_id"] == str(iv2.id)
    assert slot.interviewer_user_id == iv2.id


@pytest.mark.asyncio
async def test_update_booked_slot_other_fields_rejected(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    from fastapi import HTTPException

    staff = _staff_user()
    interviewer = _interviewer_user()
    db_session.add_all([staff, interviewer])
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=9)
    created = await create_slot(
        body=CreateInterviewSlotBody(
            starts_at=t0,
            ends_at=t0 + timedelta(hours=1),
            mode="online",
            interviewer_user_id=str(interviewer.id),
        ),
        db=db_session,
        user=staff,
    )
    slot = await db_session.get(InterviewSlot, uuid.UUID(created["id"]))
    assert slot is not None
    slot.assigned_student_id = sample_student.id
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await update_slot(
            slot_id=created["id"],
            body=UpdateInterviewSlotBody(label_fa="برچسب جدید"),
            db=db_session,
            user=staff,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_slot_accepts_secondary_interviewer_role(
    db_session: AsyncSession,
) -> None:
    """نقش مصاحبه‌گر به‌عنوان نقش دوم باید برای تعریف وقت قبول شود."""
    from fastapi import HTTPException

    staff = _staff_user()
    sara = User(
        id=uuid.uuid4(),
        username=f"sara_{uuid.uuid4().hex[:8]}",
        email=f"sara_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="سارا طراوتی",
        role="faculty_1",
        roles=["faculty_1", "interviewer"],
        is_active=True,
    )
    other = User(
        id=uuid.uuid4(),
        username=f"th_{uuid.uuid4().hex[:8]}",
        email=f"th_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="درمانگر بدون نقش مصاحبه",
        role="therapist",
        roles=["therapist"],
        is_active=True,
    )
    db_session.add_all([staff, sara, other])
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=8)
    out = await create_slot(
        body=CreateInterviewSlotBody(
            starts_at=t0,
            ends_at=t0 + timedelta(hours=1),
            course_type="introductory",
            mode="online",
            interviewer_user_id=str(sara.id),
        ),
        db=db_session,
        user=staff,
    )
    assert out["interviewer_user_id"] == str(sara.id)

    with pytest.raises(HTTPException) as exc_info:
        await create_slot(
            body=CreateInterviewSlotBody(
                starts_at=t0 + timedelta(hours=2),
                ends_at=t0 + timedelta(hours=3),
                mode="online",
                interviewer_user_id=str(other.id),
            ),
            db=db_session,
            user=staff,
        )
    assert exc_info.value.status_code == 400
    assert "قابل انتخاب" in (exc_info.value.detail or "")
