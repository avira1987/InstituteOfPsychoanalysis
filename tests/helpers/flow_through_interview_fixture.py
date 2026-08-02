"""Interview slot fixture for flow-through / onboarding API tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.demo_role_users import ensure_demo_role_users
from app.models.operational_models import InterviewSlot, ProcessInstance, User


async def ensure_open_interview_slot(
    db: AsyncSession,
    *,
    course_type: str = "introductory",
    hours_ahead: float = 48.0,
) -> InterviewSlot:
    """یک اسلات آزاد برای رزرو مصاحبهٔ ثبت‌نام ایجاد می‌کند."""
    await ensure_demo_role_users(db)
    interviewer = (
        await db.execute(select(User).where(User.username == "interviewer1"))
    ).scalar_one_or_none()
    if interviewer is None:
        raise RuntimeError("demo interviewer1 not found — run ensure_demo_role_users")

    now = datetime.now(timezone.utc)
    starts = now + timedelta(hours=hours_ahead)
    ends = starts + timedelta(minutes=45)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        course_type=course_type,
        starts_at=starts,
        ends_at=ends,
        mode="online",
        interviewer_user_id=interviewer.id,
        created_by=interviewer.id,
        assigned_student_id=None,
        assigned_instance_id=None,
    )
    db.add(slot)
    await db.flush()
    return slot


async def ensure_booked_slot_for_instance(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    course_type: str = "introductory",
) -> InterviewSlot:
    """اسلات رزروشده با مصاحبه‌گر دمو برای ثبت نتیجهٔ مصاحبه."""
    await ensure_demo_role_users(db)
    interviewer = (
        await db.execute(select(User).where(User.username == "interviewer1"))
    ).scalar_one_or_none()
    if interviewer is None:
        raise RuntimeError("demo interviewer1 not found")

    existing = (
        await db.execute(
            select(InterviewSlot).where(InterviewSlot.assigned_instance_id == instance.id).limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    now = datetime.now(timezone.utc)
    starts = now + timedelta(hours=24)
    ends = starts + timedelta(minutes=45)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        course_type=course_type,
        starts_at=starts,
        ends_at=ends,
        mode="online",
        interviewer_user_id=interviewer.id,
        created_by=interviewer.id,
        assigned_student_id=instance.student_id,
        assigned_instance_id=instance.id,
    )
    db.add(slot)
    await db.flush()
    return slot
