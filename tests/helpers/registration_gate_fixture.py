"""Fixture: published fall prep + active calendar + term offerings for intro registration gate tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InstituteCalendar, ProcessInstance
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.term_course_offering_service import publish_offerings_from_prep


async def open_intro_registration_gate(db: AsyncSession) -> tuple[ProcessInstance, InstituteCalendar]:
    """Insert completed fall prep (published), active calendar, and published term offerings."""
    anchor = await ensure_institute_operational_student(db)
    now = datetime.now(timezone.utc)

    course_rows = [
        {
            "course_name": "تئوری روانکاوی ۱",
            "track": "analytic_psychotherapy",
            "day": "شنبه",
            "time": "10:00",
            "instructor": "دکتر نمونه",
            "classroom_location": "کلاس ۱",
        },
        {
            "course_name": "تئوری روانکاوی ۲",
            "track": "analytic_psychotherapy",
            "day": "یکشنبه",
            "time": "10:00",
            "instructor": "دکتر نمونه ۲",
            "classroom_location": "کلاس ۲",
        },
    ]
    prep = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code="fall_semester_preparation",
        current_state_code="published",
        is_completed=True,
        is_cancelled=False,
        started_at=now - timedelta(days=30),
        completed_at=now,
        last_transition_at=now,
        context_data={
            "courses_finalized_fall": course_rows,
            "courses_fall": course_rows,
            "per_unit_cost_introductory": 5000000,
            "interview_fee_introductory": 15000000,
            "term_start_date": (now + timedelta(days=14)).date().isoformat(),
            "registration_open_at": (now - timedelta(days=1)).isoformat(),
            "registration_deadline_at": (now + timedelta(days=60)).isoformat(),
        },
    )
    db.add(prep)
    await db.flush()

    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code=f"fall-test-{uuid.uuid4().hex[:8]}",
        is_active=True,
        term_start_date=(now + timedelta(days=14)).date(),
        term_end_date=(now + timedelta(days=120)).date(),
        registration_open_at=now - timedelta(days=1),
        registration_deadline_at=now + timedelta(days=60),
        published_at=now,
        source_process_instance_id=prep.id,
        extra_data={"source_process_code": "fall_semester_preparation"},
    )
    db.add(cal)
    await db.flush()
    await publish_offerings_from_prep(db, prep, prep.context_data)
    await db.flush()
    return prep, cal
