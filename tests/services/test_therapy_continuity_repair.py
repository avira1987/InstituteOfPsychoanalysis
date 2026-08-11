"""تست رفع بن‌بست تقویم درمان برای دانشجوی فعال."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InstituteCalendar, Student, TherapySession, User
from app.services.therapy_session_schedule import (
    ensure_therapy_sessions_until_term_end,
    repair_student_therapy_continuity,
)


@pytest.mark.asyncio
async def test_ensure_creates_sessions_even_if_calendar_term_ended(
    db_session: AsyncSession, sample_student: Student, sample_user: User
):
    therapist = User(
        id=uuid.uuid4(),
        username=f"th_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        role="therapist",
        full_name_fa="درمانگر تست",
        is_active=True,
    )
    db_session.add(therapist)
    sample_student.therapy_started = True
    sample_student.therapist_id = therapist.id
    sample_student.weekly_sessions = 2

    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code=f"ended-{uuid.uuid4().hex[:6]}",
        is_active=True,
        term_start_date=date.today() - timedelta(weeks=20),
        term_end_date=date.today() - timedelta(days=10),
    )
    db_session.add(cal)
    await db_session.flush()

    result = await ensure_therapy_sessions_until_term_end(db_session, sample_student.id)
    await db_session.commit()

    assert result.get("created", 0) > 0
    sessions = (
        await db_session.execute(
            select(TherapySession).where(
                TherapySession.student_id == sample_student.id,
                TherapySession.status == "scheduled",
            )
        )
    ).scalars().all()
    assert len(sessions) == result["created"]
    assert all(s.session_date >= date.today() for s in sessions)


@pytest.mark.asyncio
async def test_repair_opens_session_payment_when_unpaid(
    db_session: AsyncSession, sample_student: Student, sample_user: User
):
    from pathlib import Path

    from app.meta.seed import load_process

    processes_dir = Path(__file__).resolve().parents[2] / "metadata" / "processes"
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()

    therapist = User(
        id=uuid.uuid4(),
        username=f"th_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        role="therapist",
        full_name_fa="درمانگر تست۲",
        is_active=True,
    )
    db_session.add(therapist)
    sample_student.therapy_started = True
    sample_student.therapist_id = therapist.id
    sample_student.weekly_sessions = 1
    await db_session.flush()

    out = await repair_student_therapy_continuity(db_session, sample_student.id)
    await db_session.commit()

    assert (out.get("seed") or {}).get("created", 0) > 0
    assert (out.get("session_payment") or {}).get("started") is True
    assert (out.get("session_payment") or {}).get("instance_id")
