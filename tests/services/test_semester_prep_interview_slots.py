"""تست همگام‌سازی تنظیمات مصاحبهٔ آماده‌سازی ترم با اسلات‌های آزاد."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InterviewSlot, Student
from app.services.interview_slot_service import (
    apply_semester_prep_interview_defaults_to_open_slots,
    interview_mode_fa_to_slot_mode,
    resolve_semester_prep_interview_location,
)


def test_interview_mode_fa_to_slot_mode():
    assert interview_mode_fa_to_slot_mode("آنلاین") == "online"
    assert interview_mode_fa_to_slot_mode("حضوری") == "in_person"
    assert interview_mode_fa_to_slot_mode(None) == "in_person"


def test_resolve_semester_prep_interview_location_prefers_new_field():
    ctx = {
        "interview_location_fa": "آدرس جدید",
        "interview_location_or_link": "قدیمی",
    }
    assert resolve_semester_prep_interview_location(ctx) == "آدرس جدید"


@pytest.mark.asyncio
async def test_apply_semester_prep_defaults_updates_only_open_slots(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    t0 = datetime.now(timezone.utc) + timedelta(days=3)
    open_slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(minutes=30),
        mode="in_person",
        location_fa="قدیم",
    )
    booked_slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0 + timedelta(hours=1),
        ends_at=t0 + timedelta(hours=1, minutes=30),
        mode="in_person",
        location_fa="رزروشده",
        assigned_student_id=sample_student.id,
    )
    db_session.add_all([open_slot, booked_slot])
    await db_session.flush()

    updated = await apply_semester_prep_interview_defaults_to_open_slots(
        db_session,
        mode="online",
        location_fa=None,
    )
    await db_session.flush()

    assert updated == 1
    await db_session.refresh(open_slot)
    await db_session.refresh(booked_slot)
    assert open_slot.mode == "online"
    assert open_slot.location_fa is None
    assert booked_slot.mode == "in_person"
    assert booked_slot.location_fa == "رزروشده"


@pytest.mark.asyncio
async def test_apply_semester_prep_defaults_sets_in_person_location(
    db_session: AsyncSession,
) -> None:
    t0 = datetime.now(timezone.utc) + timedelta(days=2)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(minutes=30),
        mode="online",
    )
    db_session.add(slot)
    await db_session.flush()

    await apply_semester_prep_interview_defaults_to_open_slots(
        db_session,
        mode="in_person",
        location_fa="خیابان ولیعصر، پلاک ۱",
    )
    await db_session.flush()
    await db_session.refresh(slot)

    assert slot.mode == "in_person"
    assert slot.location_fa == "خیابان ولیعصر، پلاک ۱"

    rows = (await db_session.execute(select(InterviewSlot))).scalars().all()
    assert len(rows) == 1
