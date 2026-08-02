"""Tests for term course offering publish and query."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InstituteCalendar, ProcessInstance
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.term_course_offering_service import (
    NO_OFFERINGS_REASON_FA,
    build_term_offerings_response,
    get_offering_options,
    publish_offerings_from_prep,
    resolve_course_code_from_name,
)


def test_resolve_course_code_maps_catalog_label():
    assert resolve_course_code_from_name("تئوری روانکاوی ۱") == "theory_psychoanalysis_1"


@pytest.mark.asyncio
async def test_publish_offerings_from_fall_prep(db_session: AsyncSession):
    anchor = await ensure_institute_operational_student(db_session)
    now = datetime.now(timezone.utc)
    rows = [
        {
            "course_name": "تئوری روانکاوی ۱",
            "day": "شنبه",
            "time": "09:00",
            "classroom_location": "A1",
            "instructor": "مدرس ۱",
        }
    ]
    prep = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code="fall_semester_preparation",
        current_state_code="published",
        is_completed=True,
        is_cancelled=False,
        started_at=now,
        completed_at=now,
        context_data={
            "courses_finalized_fall": rows,
            "per_unit_cost_introductory": 4000000,
            "interview_fee_introductory": 12000000,
        },
    )
    db_session.add(prep)
    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code=f"term-{uuid.uuid4().hex[:6]}",
        is_active=True,
        term_start_date=now.date(),
        term_end_date=(now + timedelta(days=90)).date(),
        published_at=now,
    )
    db_session.add(cal)
    await db_session.flush()

    result = await publish_offerings_from_prep(db_session, prep, prep.context_data)
    assert result["published"] is True
    assert result["count"] >= 1

    options = await get_offering_options(
        db_session, program_kind="introductory", term_number=1, term_code=cal.term_code
    )
    assert len(options) == 1
    assert options[0]["value"] == "theory_psychoanalysis_1"
    assert options[0]["classroom_location"] == "A1"


@pytest.mark.asyncio
async def test_build_term_offerings_empty_without_publish(db_session: AsyncSession):
    resp = await build_term_offerings_response(
        db_session, program_kind="introductory", term_number=1
    )
    assert resp["published"] is False
    assert resp["reason_fa"] == NO_OFFERINGS_REASON_FA
