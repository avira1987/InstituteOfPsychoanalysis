"""تست اعلان رزرو اسلات برای مصاحبه‌گر اختصاص‌یافته."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.models.operational_models import InterviewSlot, PanelFlashMessage, Student, User
from app.services.interview_slot_notification_service import (
    notify_interviewer_slot_assigned,
    notify_interviewer_slot_booked,
)


def _slot(*, interviewer_id: uuid.UUID | None, created_by: uuid.UUID, t0: datetime | None = None) -> InterviewSlot:
    start = t0 or (datetime.now(timezone.utc) + timedelta(days=3))
    return InterviewSlot(
        id=uuid.uuid4(),
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        mode="online",
        course_type="introductory",
        created_by=created_by,
        interviewer_user_id=interviewer_id,
    )


@pytest.mark.asyncio
async def test_notify_assigned_creates_flash(db_session: AsyncSession) -> None:
    staff = User(
        id=uuid.uuid4(),
        username=f"staff_{uuid.uuid4().hex[:8]}",
        email=f"staff_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        role="staff",
        is_active=True,
    )
    interviewer = User(
        id=uuid.uuid4(),
        username=f"iv_{uuid.uuid4().hex[:8]}",
        email=f"iv_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="دکتر الف",
        role="interviewer",
        is_active=True,
        phone="09123334444",
    )
    db_session.add_all([staff, interviewer])
    await db_session.flush()

    slot = _slot(interviewer_id=interviewer.id, created_by=staff.id)
    db_session.add(slot)
    await db_session.flush()

    with patch(
        "app.services.interview_slot_notification_service.notification_service.send_notification",
        new_callable=AsyncMock,
    ) as send_sms:
        await notify_interviewer_slot_assigned(
            db_session,
            slot=slot,
            interviewer_user_id=interviewer.id,
        )
        send_sms.assert_awaited_once()

    rows = (
        await db_session.execute(
            PanelFlashMessage.__table__.select().where(
                PanelFlashMessage.user_id == interviewer.id
            )
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_notify_booked_creates_flash(db_session: AsyncSession) -> None:
    staff = User(
        id=uuid.uuid4(),
        username=f"staff_{uuid.uuid4().hex[:8]}",
        email=f"staff_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        role="staff",
        is_active=True,
    )
    interviewer = User(
        id=uuid.uuid4(),
        username=f"iv_{uuid.uuid4().hex[:8]}",
        email=f"iv_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="دکتر ب",
        role="interviewer",
        is_active=True,
        phone="09125556666",
    )
    student_user = User(
        id=uuid.uuid4(),
        username=f"st_{uuid.uuid4().hex[:8]}",
        email=f"st_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="دانشجوی تست",
        role="student",
        is_active=True,
    )
    db_session.add_all([staff, interviewer, student_user])
    await db_session.flush()

    student = Student(
        id=uuid.uuid4(),
        user_id=student_user.id,
        student_code="ST-001",
        course_type="introductory",
    )
    db_session.add(student)
    await db_session.flush()

    slot = _slot(interviewer_id=interviewer.id, created_by=staff.id)
    slot.assigned_student_id = student.id
    db_session.add(slot)
    await db_session.flush()

    with patch(
        "app.services.interview_slot_notification_service.notification_service.send_notification",
        new_callable=AsyncMock,
    ):
        await notify_interviewer_slot_booked(
            db_session,
            slot=slot,
            student=student,
            student_user=student_user,
        )

    rows = (
        await db_session.execute(
            PanelFlashMessage.__table__.select().where(
                PanelFlashMessage.user_id == interviewer.id
            )
        )
    ).all()
    assert len(rows) == 1
    assert "دانشجوی تست" in str(rows[0][2] or "")
