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
    assert resolve_course_code_from_name("تئوری روانکاوی (1)") == "theory_psychoanalysis_1"
    assert resolve_course_code_from_name("تئوری روانکاوی یک") == "theory_psychoanalysis_1"
    assert resolve_course_code_from_name("تئوری تکنیک یک") == "theory_technique_1"
    assert resolve_course_code_from_name("تئوری تکنیک‌ها ۱") == "theory_technique_1"


def test_offering_option_fills_catalog_prerequisites_when_row_empty():
    from types import SimpleNamespace

    from app.services.term_course_offering_service import offering_to_option

    row = SimpleNamespace(
        course_code="theory_psychoanalysis_2",
        course_name_fa="تئوری روانکاوی ۲",
        day=None,
        time_text=None,
        classroom_location=None,
        instructor_name=None,
        teaching_assistant_name=None,
        units=2,
        prerequisite_codes=[],
        track=None,
        per_unit_cost_rial=None,
    )
    opt = offering_to_option(row)
    assert opt["prerequisite_codes"] == ["theory_psychoanalysis_1"]


def test_offering_option_canonicalizes_persian_course_code():
    from types import SimpleNamespace

    from app.services.term_course_offering_service import offering_to_option

    row = SimpleNamespace(
        course_code="تئوری تکنیک یک",
        course_name_fa="تئوری تکنیک یک",
        day=None,
        time_text=None,
        classroom_location=None,
        instructor_name=None,
        teaching_assistant_name=None,
        units=3,
        prerequisite_codes=[],
        track=None,
        per_unit_cost_rial=None,
    )
    opt = offering_to_option(row)
    assert opt["value"] == "theory_technique_1"
    assert opt.get("single_course_allowed") is not True


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
    assert options[0]["units"] == 2


@pytest.mark.asyncio
async def test_publish_winter_uses_catalog_prerequisites(db_session: AsyncSession):
    from app.services.semester_prep_service import WINTER_PREP

    anchor = await ensure_institute_operational_student(db_session)
    now = datetime.now(timezone.utc)
    prep = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code=WINTER_PREP,
        current_state_code="published",
        is_completed=True,
        is_cancelled=False,
        started_at=now,
        completed_at=now,
        context_data={
            "courses_finalized": [
                {"course_name": "تئوری روانکاوی ۲", "day": "شنبه", "time": "09:00"},
                {"course_name": "تئوری تکنیک‌ها ۲", "day": "یکشنبه", "time": "09:00"},
            ],
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
    options = await get_offering_options(
        db_session, program_kind="introductory", term_number=2, term_code=cal.term_code
    )
    by_code = {o["value"]: o for o in options}
    assert by_code["theory_psychoanalysis_2"]["prerequisite_codes"] == ["theory_psychoanalysis_1"]
    assert by_code["theory_technique_2"]["prerequisite_codes"] == ["theory_technique_1"]


@pytest.mark.asyncio
async def test_build_term_offerings_empty_without_publish(db_session: AsyncSession):
    resp = await build_term_offerings_response(
        db_session, program_kind="introductory", term_number=1
    )
    assert resp["published"] is False
    assert resp["reason_fa"] == NO_OFFERINGS_REASON_FA
