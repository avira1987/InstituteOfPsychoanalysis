"""با ثبت وقت آزاد جدید، حذف خودکار وقت‌های آزاد قبلیٔ همان مصاحبه‌گر (رزرونشده)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.models.operational_models import InterviewSlot, User
from app.services.interview_slot_service import delete_prior_unbooked_slots_for_interviewer


@pytest.mark.asyncio
async def test_interviewer_create_replaces_prior_unbooked_slots(db_session: AsyncSession, sample_student) -> None:
    uid = uuid.uuid4()
    iv = User(
        id=uid,
        username=f"iv_{uuid.uuid4().hex[:10]}",
        email=f"iv_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبه‌گر تست",
        role="interviewer",
    )
    db_session.add(iv)
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=10)
    t1 = t0 + timedelta(hours=1)

    keep_booked_id = uuid.uuid4()
    stu_id = sample_student.id
    old_free = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t1,
        course_type=None,
        mode="in_person",
        created_by=uid,
        interviewer_user_id=uid,
        assigned_student_id=None,
    )
    booked = InterviewSlot(
        id=keep_booked_id,
        starts_at=t0 + timedelta(days=7),
        ends_at=t0 + timedelta(days=7, hours=1),
        course_type=None,
        mode="in_person",
        created_by=uid,
        interviewer_user_id=uid,
        assigned_student_id=stu_id,
    )
    other_iv = uuid.uuid4()
    colleague = User(
        id=other_iv,
        username=f"iv_other_{uuid.uuid4().hex[:10]}",
        email=f"iv_other_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبهٔ همکار",
        role="interviewer",
    )
    db_session.add(colleague)
    await db_session.flush()
    colleague_slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0 + timedelta(days=1),
        ends_at=t0 + timedelta(days=1, hours=1),
        course_type=None,
        mode="online",
        created_by=other_iv,
        interviewer_user_id=other_iv,
        assigned_student_id=None,
    )
    db_session.add_all([old_free, booked, colleague_slot])
    await db_session.flush()

    n = await delete_prior_unbooked_slots_for_interviewer(db_session, interviewer_user_id=uid)
    await db_session.commit()

    assert n == 1
    ids = (await db_session.execute(select(InterviewSlot.id))).scalars().all()
    assert keep_booked_id in ids
    assert colleague_slot.id in ids
    assert old_free.id not in ids


@pytest.mark.asyncio
async def test_office_pool_slots_not_cleared_when_interviewer_prunes_own(db_session: AsyncSession) -> None:
    """پاکسازی فقط برای همان interviewer_user_id؛ اسلات عمومی کارمند (بدون مصاحبه‌گر) دست‌نخورده می‌ماند."""
    staff_id = uuid.uuid4()
    iv_id = uuid.uuid4()
    db_session.add_all(
        [
            User(
                id=staff_id,
                username=f"st_{uuid.uuid4().hex[:10]}",
                email=f"st_{uuid.uuid4().hex[:10]}@t.test",
                hashed_password=get_password_hash("x"),
                full_name_fa="کارمند",
                role="staff",
            ),
            User(
                id=iv_id,
                username=f"iv2_{uuid.uuid4().hex[:10]}",
                email=f"iv2_{uuid.uuid4().hex[:10]}@t.test",
                hashed_password=get_password_hash("x"),
                full_name_fa="مصاحبه‌گر دو",
                role="interviewer",
            ),
        ]
    )
    await db_session.flush()

    t0 = datetime.now(timezone.utc) + timedelta(days=30)
    pool = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=2),
        course_type=None,
        mode="in_person",
        created_by=staff_id,
        interviewer_user_id=None,
        assigned_student_id=None,
    )
    iv_unbooked = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0 + timedelta(days=1),
        ends_at=t0 + timedelta(days=1, hours=1),
        course_type=None,
        mode="in_person",
        created_by=iv_id,
        interviewer_user_id=iv_id,
        assigned_student_id=None,
    )
    db_session.add_all([pool, iv_unbooked])
    await db_session.flush()

    n = await delete_prior_unbooked_slots_for_interviewer(db_session, interviewer_user_id=iv_id)
    await db_session.commit()

    assert n == 1
    ids = (await db_session.execute(select(InterviewSlot.id))).scalars().all()
    assert pool.id in ids
    assert iv_unbooked.id not in ids
