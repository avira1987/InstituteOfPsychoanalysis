"""Unit tests for process 47 — upgrade_to_ta eligibility."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ta_upgrade_service import (
    TA_THERAPY_HOURS_TARGET,
    build_ta_upgrade_context,
    validate_conditions_met_trigger,
)


@pytest.mark.asyncio
async def test_build_ta_upgrade_context_all_met():
    student_id = uuid.uuid4()
    student = MagicMock()
    student.id = student_id
    student.is_intern = True
    student.extra_data = {
        "lms": {"cumulative_gpa": 15.0},
        "comprehensive_term2_courses_passed": True,
    }

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=student))))
    )

    with patch(
        "app.services.ta_upgrade_service.AttendanceService",
    ) as AttendanceCls:
        inst = AttendanceCls.return_value
        inst.get_therapy_completion_metrics = AsyncMock(
            return_value={"therapy_hours_2x": TA_THERAPY_HOURS_TARGET}
        )
        ctx = await build_ta_upgrade_context(db, student_id)

    assert ctx["ta_eligibility_met"] is True
    assert ctx["ta_term2_courses_met"] is True
    assert ctx["ta_gpa_met"] is True
    assert ctx["ta_therapy_met"] is True
    assert ctx["ta_intern_met"] is True
    assert len(ctx["ta_conditions_preview"]) == 4
    assert validate_conditions_met_trigger(ctx) is None


@pytest.mark.asyncio
async def test_build_ta_upgrade_context_not_met():
    student_id = uuid.uuid4()
    student = MagicMock()
    student.id = student_id
    student.is_intern = False
    student.extra_data = {"lms": {"cumulative_gpa": 12.0}}

    db = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=student))))
    )

    with patch(
        "app.services.ta_upgrade_service.AttendanceService",
    ) as AttendanceCls:
        inst = AttendanceCls.return_value
        inst.get_therapy_completion_metrics = AsyncMock(return_value={"therapy_hours_2x": 10.0})
        ctx = await build_ta_upgrade_context(db, student_id)

    assert ctx["ta_eligibility_met"] is False
    assert validate_conditions_met_trigger(ctx) is not None
