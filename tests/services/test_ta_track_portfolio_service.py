"""Tests for ta_track_portfolio_service — فرایند ۵۲."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance, Student, User
from app.services.action_handler import ActionHandler
from app.services.ta_track_portfolio_service import (
    build_ta_portfolio,
    label_rank_fa,
    mark_ta_track_completed,
    progress_label_fa,
)


def test_label_rank_fa():
    assert label_rank_fa("teaching_assistant") == "کمک مدرس"
    assert label_rank_fa("assistant_faculty") == "دستیار هیئت علمی"


def test_progress_label_fa():
    assert "۰ از ۲" in progress_label_fa(0)
    assert "۱ از ۲" in progress_label_fa(1)
    assert "۲ از ۲" in progress_label_fa(2)


@pytest.mark.asyncio
async def test_build_ta_portfolio_from_extra(db_session: AsyncSession, sample_student: Student, sample_student_user: User):
    sample_student.extra_data = {
        "rank": "teaching_assistant",
        "ta_portfolio": {
            "assigned_tracks": ["analytic_psychotherapy"],
            "courses": [
                {
                    "course_code": "theory_psychoanalysis_1",
                    "course_name_fa": "تئوری روانکاوی ۱",
                    "track_code": "analytic_psychotherapy",
                    "successful_ta_count": 1,
                },
            ],
            "completed_tracks": [],
        },
    }
    portfolio = build_ta_portfolio(sample_student, sample_student_user)
    assert portfolio["rank_fa"] == "کمک مدرس"
    assert portfolio["has_ta_data"] is True
    assert len(portfolio["courses"]) == 1
    assert portfolio["courses"][0]["progress_fa"].startswith("۱ از ۲")
    assert len(portfolio["active_tracks"]) >= 1


@pytest.mark.asyncio
async def test_mark_ta_track_completed(db_session: AsyncSession, sample_student: Student):
    sample_student.extra_data = {
        "rank": "teaching_assistant",
        "ta_portfolio": {
            "assigned_tracks": ["analytic_psychotherapy"],
            "courses": [],
        },
    }
    result = mark_ta_track_completed(
        sample_student,
        track_code="analytic_psychotherapy",
        track_name_fa="رواندرمانی تحلیلی",
    )
    assert "track_completed" in result
    completed = sample_student.extra_data["ta_portfolio"]["completed_tracks"]
    assert len(completed) == 1
    assert completed[0]["code"] == "analytic_psychotherapy"


@pytest.mark.asyncio
async def test_update_record_ta_track_completion(
    db_session: AsyncSession, sample_student: Student
):
    instance = ProcessInstance(
        id=uuid.uuid4(),
        process_code="ta_track_completion",
        student_id=sample_student.id,
        current_state_code="end_of_track_check",
        context_data={
            "track_code": "analytic_psychotherapy",
            "track_name_fa": "رواندرمانی تحلیلی",
        },
    )
    db_session.add(instance)
    await db_session.flush()

    handler = ActionHandler(db_session)
    result = await handler.handle_actions([{"type": "update_record"}], instance, {})
    await db_session.commit()

    assert "track_completed" in result[0].get("detail", "")
    await db_session.refresh(sample_student)
    portfolio = sample_student.extra_data.get("ta_portfolio") or {}
    assert len(portfolio.get("completed_tracks") or []) == 1
