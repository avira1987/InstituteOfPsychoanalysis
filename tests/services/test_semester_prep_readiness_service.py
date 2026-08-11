"""Tests for semester prep readiness checklist."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import User
from app.services.course_committee_roster_service import (
    add_course_to_catalog,
    add_member_to_roster,
    add_track_to_roster,
    reload_catalog_cache,
    reload_roster_cache,
)
from app.services.semester_prep_readiness_service import compute_semester_prep_readiness


@pytest.mark.asyncio
async def test_readiness_empty_catalog_and_roster(db_session: AsyncSession):
    reload_catalog_cache()
    reload_roster_cache()
    result = await compute_semester_prep_readiness(db_session)
    assert result["ready"] is False
    assert result["incomplete_count"] > 0
    keys = {i["key"] for i in result["items"]}
    assert "course_catalog" in keys
    assert "course_roster" in keys
    assert "interviewers" in keys
    assert "license" in keys


@pytest.mark.asyncio
async def test_readiness_with_catalog_track_instructor_and_interviewer(
    db_session: AsyncSession,
    sample_user,
):
    reload_catalog_cache()
    reload_roster_cache()
    track = add_track_to_roster("رسته آزمایشی")
    add_course_to_catalog("درس آزمایشی", track=track["value"])
    add_member_to_roster(track=track["value"], kind="instructor", name_fa="مدرس آزمایشی")

    interviewer = User(
        id=__import__("uuid").uuid4(),
        username="test_interviewer_readiness",
        email="iv@test.local",
        hashed_password="x",
        full_name_fa="مصاحبه‌گر آزمایشی",
        role="interviewer",
        is_active=True,
    )
    db_session.add(interviewer)
    await db_session.flush()

    result = await compute_semester_prep_readiness(db_session)
    by_key = {i["key"]: i for i in result["items"]}
    assert by_key["course_catalog"]["complete"] is True
    assert by_key["course_roster"]["complete"] is True
    assert by_key["interviewers"]["complete"] is True
    assert by_key["interviewers"]["count"] >= 1
