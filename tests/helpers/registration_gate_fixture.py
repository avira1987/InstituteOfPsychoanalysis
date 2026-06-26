"""Fixture: published fall prep + active calendar for intro registration gate tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InstituteCalendar, ProcessInstance
from app.services.institute_operational_anchor import ensure_institute_operational_student


async def open_intro_registration_gate(db: AsyncSession) -> tuple[ProcessInstance, InstituteCalendar]:
    """Insert completed fall prep (published) and an active institute calendar with open window."""
    anchor = await ensure_institute_operational_student(db)
    now = datetime.now(timezone.utc)

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
            "courses": [
                {"course_name": "تئوری روانکاوی ۱"},
                {"course_name": "تئوری روانکاوی ۲"},
                {"course_name": "تئوری روانکاوی ۳"},
                {"course_name": "تئوری روانکاوی ۴"},
                {"course_name": "تئوری روانکاوی ۵"},
            ],
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
    return prep, cal
