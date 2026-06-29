"""Tests for student_supervision_cancellation_service (process 25)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student
from app.services.student_supervision_cancellation_service import (
    build_student_supervision_cancellation_context,
    compute_cancellation_percent,
    compute_percent_after,
    get_supervision_cancellation_stats,
    validate_student_supervision_cancellation_selection,
)


class TestSupervisionCancellationPercent:
    def test_compute_percent_zero_base(self):
        assert compute_cancellation_percent(0, 0) == 0.0

    def test_compute_percent_after_additional(self):
        assert compute_percent_after(80, 10, 2) == round(12 / 92 * 100, 2)

    def test_compute_percent_known_ratio(self):
        assert compute_cancellation_percent(27, 3) == 10.0


@pytest.mark.asyncio
class TestStudentSupervisionCancellationService:
    async def test_stats_from_student_extra_data(
        self, db_session: AsyncSession, sample_student: Student
    ):
        extra = dict(sample_student.extra_data or {})
        extra["supervision_hours"] = 50
        extra["supervision_cancelled_sessions_count"] = 5
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        stats = await get_supervision_cancellation_stats(db_session, sample_student.id, 0)
        assert stats["completed_sessions"] >= 50
        assert stats["cancelled_sessions"] >= 5
        assert stats["allowed_cancellation_cap_count"] == 7  # ceil(55 * 0.12)

    async def test_upcoming_sessions_from_supervision_50h_instance(
        self, db_session: AsyncSession, sample_student: Student
    ):
        today = date.today()
        inst = ProcessInstance(
            id=uuid.uuid4(),
            student_id=sample_student.id,
            process_code="supervision_50h_completion",
            current_state_code="session_scheduled",
            context_data={
                "session_date": (today + timedelta(days=5)).isoformat(),
                "preferred_time_hhmm": "10:00",
            },
            is_completed=False,
            is_cancelled=False,
        )
        db_session.add(inst)
        await db_session.commit()

        ctx = await build_student_supervision_cancellation_context(
            db_session, sample_student.id
        )
        assert len(ctx["upcoming_cancellation_sessions"]) >= 1
        assert ctx["upcoming_cancellation_sessions"][0]["value"] == str(inst.id)

    async def test_validate_requires_selection(
        self, db_session: AsyncSession, sample_student: Student
    ):
        err = await validate_student_supervision_cancellation_selection(
            db_session, sample_student.id, []
        )
        assert err is not None
        assert "حداقل" in err

    async def test_context_includes_status_summary(
        self, db_session: AsyncSession, sample_student: Student
    ):
        ctx = await build_student_supervision_cancellation_context(
            db_session, sample_student.id
        )
        assert "cancellation_status_summary_fa" in ctx
        assert "وضعیت غیبت" in ctx["cancellation_status_summary_fa"]
