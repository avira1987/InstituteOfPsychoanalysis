"""Unit tests for therapy_workbench_service counters."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.models.operational_models import Student, TherapySession, User
from app.services.therapy_workbench_service import get_workbench_summary


async def _make_therapist(db_session: AsyncSession) -> User:
    suid = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        username=f"svc_th_{suid}",
        email=f"svc_th_{suid}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="درمانگر سرویس",
        role="therapist",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_summary_counts_multiple_students(
    db_session: AsyncSession,
    sample_student: Student,
):
    therapist = await _make_therapist(db_session)
    sample_student.therapist_id = therapist.id
    sample_student.therapy_started = True

    other_user = User(
        id=uuid.uuid4(),
        username=f"stu_wb_{uuid.uuid4().hex[:8]}",
        email=f"stu_wb_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="دانشجوی دوم",
        role="student",
    )
    db_session.add(other_user)
    other = Student(
        id=uuid.uuid4(),
        user_id=other_user.id,
        student_code="STU-WB-2",
        course_type="introductory",
        therapist_id=therapist.id,
        therapy_started=True,
        weekly_sessions=1,
    )
    db_session.add(other)
    await db_session.flush()

    db_session.add(
        TherapySession(
            id=uuid.uuid4(),
            student_id=sample_student.id,
            therapist_id=therapist.id,
            session_date=date.today() + timedelta(days=1),
            status="scheduled",
            payment_status="pending",
        )
    )
    db_session.add(
        TherapySession(
            id=uuid.uuid4(),
            student_id=other.id,
            therapist_id=therapist.id,
            session_date=date.today() + timedelta(days=2),
            status="scheduled",
            payment_status="paid",
        )
    )
    await db_session.commit()

    out = await get_workbench_summary(db_session, therapist, role_scope="therapist")
    assert out["totals"]["students"] == 2
    codes = {s["student_code"] for s in out["students"]}
    assert sample_student.student_code in codes
    assert "STU-WB-2" in codes
    missing = [s for s in out["students"] if s["missing_future_schedule"]]
    assert len(missing) == 0


@pytest.mark.asyncio
async def test_admin_therapist_scope_sees_all_started_students(
    db_session: AsyncSession,
    sample_student: Student,
):
    therapist = await _make_therapist(db_session)
    sample_student.therapist_id = therapist.id
    sample_student.therapy_started = True
    admin = User(
        id=uuid.uuid4(),
        username=f"svc_admin_{uuid.uuid4().hex[:8]}",
        email=f"svc_admin_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="مدیر سرویس",
        role="admin",
        roles=["admin"],
    )
    db_session.add(admin)
    await db_session.commit()

    out = await get_workbench_summary(db_session, admin, role_scope="therapist")
    codes = {s["student_code"] for s in out["students"]}
    assert sample_student.student_code in codes
