"""Tests for educational therapist slot service."""

from __future__ import annotations

import uuid
from datetime import time

import pytest
from sqlalchemy import select

from app.models.operational_models import EducationalTherapistSlot, ProcessInstance, Student, User
from app.services.educational_therapist_slot_service import (
    book_slots_for_student,
    create_slot,
    list_available_grouped_by_therapist,
    release_slots,
)


@pytest.mark.asyncio
async def test_create_and_list_free_slots(db_session, sample_student):
    therapist = User(
        id=uuid.uuid4(),
        username=f"therapist_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        role="therapist",
        full_name_fa="دکتر تست",
        is_active=True,
    )
    db_session.add(therapist)
    await db_session.flush()

    slot = await create_slot(
        db_session,
        therapist_user_id=therapist.id,
        day_of_week=5,
        start_local_time=time(10, 0),
        end_local_time=time(11, 0),
        course_type="comprehensive",
    )
    await db_session.commit()

    grouped = await list_available_grouped_by_therapist(db_session, course_type="comprehensive")
    assert len(grouped["therapists"]) >= 1
    assert any(t["id"] == str(therapist.id) for t in grouped["therapists"])
    assert slot.status == "free"


@pytest.mark.asyncio
async def test_book_and_release_slots(db_session, sample_student):
    therapist = User(
        id=uuid.uuid4(),
        username=f"therapist_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        role="therapist",
        full_name_fa="دکتر رزرو",
        is_active=True,
    )
    db_session.add(therapist)
    sample_student.course_type = "comprehensive"
    await db_session.flush()

    s1 = await create_slot(
        db_session,
        therapist_user_id=therapist.id,
        day_of_week=5,
        start_local_time=time(10, 0),
        end_local_time=time(11, 0),
    )
    s2 = await create_slot(
        db_session,
        therapist_user_id=therapist.id,
        day_of_week=0,
        start_local_time=time(14, 0),
        end_local_time=time(15, 0),
    )
    await db_session.flush()

    instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        process_code="start_therapy",
        current_state_code="therapist_selection",
        context_data={},
    )
    db_session.add(instance)
    await db_session.flush()

    booked = await book_slots_for_student(
        db_session,
        slot_ids=[s1.id, s2.id],
        therapist_user_id=therapist.id,
        student_id=sample_student.id,
        instance_id=instance.id,
        course_type="comprehensive",
        weekly_sessions=2,
    )
    assert len(booked) == 2
    assert all(s.status == "booked" for s in booked)

    n = await release_slots(db_session, student_id=sample_student.id)
    assert n == 2

    row = await db_session.get(EducationalTherapistSlot, s1.id)
    assert row.status == "free"
    assert row.assigned_student_id is None


@pytest.mark.asyncio
async def test_book_rejects_wrong_weekly_count(db_session, sample_student):
    therapist = User(
        id=uuid.uuid4(),
        username=f"therapist_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        role="therapist",
        full_name_fa="دکتر خطا",
        is_active=True,
    )
    db_session.add(therapist)
    sample_student.course_type = "comprehensive"
    await db_session.flush()

    s1 = await create_slot(
        db_session,
        therapist_user_id=therapist.id,
        day_of_week=5,
        start_local_time=time(10, 0),
        end_local_time=time(11, 0),
    )
    await db_session.flush()

    with pytest.raises(ValueError, match="۲ جلسه"):
        await book_slots_for_student(
            db_session,
            slot_ids=[s1.id],
            therapist_user_id=therapist.id,
            student_id=sample_student.id,
            instance_id=uuid.uuid4(),
            course_type="comprehensive",
            weekly_sessions=1,
        )
