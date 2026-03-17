"""Tests for AttendanceService (BUILD_TODO § د — hours_until_first_slot)."""

import pytest
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.attendance_service import AttendanceService, NO_UPCOMING_SESSION_HOURS
from app.models.operational_models import TherapySession


@pytest.mark.asyncio
class TestAttendanceServiceHoursUntilFirstSlot:

    async def test_get_hours_until_first_slot_no_upcoming_returns_large_value(
        self, db_session: AsyncSession, sample_student
    ):
        """When student has no scheduled session in future, return NO_UPCOMING_SESSION_HOURS."""
        attendance = AttendanceService(db_session)
        today = date(2024, 10, 15)
        hours = await attendance.get_hours_until_first_slot(sample_student.id, today=today)
        assert hours == NO_UPCOMING_SESSION_HOURS

    async def test_get_hours_until_first_slot_with_future_session(
        self, db_session: AsyncSession, sample_student
    ):
        """Hours until first slot = (session_date - today).days * 24."""
        today = date(2024, 10, 15)
        session = TherapySession(
            id=None,
            student_id=sample_student.id,
            therapist_id=None,
            session_date=today + timedelta(days=2),
            session_number=1,
            status="scheduled",
        )
        db_session.add(session)
        await db_session.commit()

        attendance = AttendanceService(db_session)
        hours = await attendance.get_hours_until_first_slot(sample_student.id, today=today)
        assert hours == 48.0  # 2 days * 24

    async def test_get_hours_until_first_slot_session_today_returns_zero(
        self, db_session: AsyncSession, sample_student
    ):
        """When first upcoming session is today, return 0 (for 24_hour_rule)."""
        today = date(2024, 10, 15)
        session = TherapySession(
            id=None,
            student_id=sample_student.id,
            therapist_id=None,
            session_date=today,
            session_number=1,
            status="scheduled",
        )
        db_session.add(session)
        await db_session.commit()

        attendance = AttendanceService(db_session)
        hours = await attendance.get_hours_until_first_slot(sample_student.id, today=today)
        assert hours == 0.0
