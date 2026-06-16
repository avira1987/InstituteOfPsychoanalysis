"""تولید اسلات از الگوی هفتگی مصاحبه‌گر (منطقهٔ زمانی تهران)."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from app.api.auth import get_password_hash
from app.models.operational_models import InterviewSlot, InterviewSlotRecurringRule, User
from app.services.interview_slot_recurring_generation import (
    generate_interview_slots_from_recurring_rules,
    normalize_rule_weekdays,
)


@pytest.mark.asyncio
async def test_normalize_rule_weekdays():
    assert normalize_rule_weekdays([0, "5", 0]) == [0, 5]
    assert normalize_rule_weekdays([]) is None
    assert normalize_rule_weekdays([9]) is None


@pytest.mark.asyncio
async def test_generates_slot_on_matching_weekdays(db_session) -> None:
    """دوشنبه ۲۰۲۳-۰۵-۱۵؛ اسلات ده صبح به وقت تهران همان روز باید ساخته شود."""
    uid = uuid.uuid4()
    iv = User(
        id=uid,
        username=f"iv_{uuid.uuid4().hex[:10]}",
        email=f"iv_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبه‌گر تکراری",
        role="interviewer",
    )
    db_session.add(iv)
    await db_session.flush()

    rule = InterviewSlotRecurringRule(
        id=uuid.uuid4(),
        interviewer_user_id=uid,
        days_of_week=[0],
        start_local_time=time(10, 0),
        end_local_time=time(11, 0),
        course_type=None,
        mode="in_person",
        location_fa="سالن",
        is_active=True,
        horizon_days=7,
    )
    db_session.add(rule)
    await db_session.commit()

    now = datetime(2023, 5, 15, 3, 0, tzinfo=timezone.utc)
    summary = await generate_interview_slots_from_recurring_rules(db_session, now=now)
    await db_session.commit()

    assert summary["created_total"] >= 1

    stmt = (
        select(InterviewSlot)
        .where(InterviewSlot.generated_from_rule_id == rule.id)
        .order_by(InterviewSlot.starts_at)
    )
    slots = list((await db_session.execute(stmt)).scalars().all())
    assert len(slots) >= 1
    assert slots[0].interviewer_user_id == uid
    assert slots[0].assigned_student_id is None

    summary2 = await generate_interview_slots_from_recurring_rules(db_session, now=now + timedelta(seconds=2))
    await db_session.commit()
    assert summary2["created_total"] == 0
