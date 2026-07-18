"""تست انتشار تقویم آموزشی — snapshot دو ترم، merge پاییز در زمستان، sync پرچم."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_password_hash
from app.database import get_db
from app.main import app
from app.models.operational_models import InstituteCalendar, PanelFlashMessage, ProcessInstance, Student, User
from app.services.institute_calendar_service import publish_calendar_from_instance_context
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_service import FALL_PREP, WINTER_PREP

CALENDAR_CTX: dict = {
    "fall_start_date": "2026-09-15",
    "fall_end_date": "2026-12-20",
    "winter_start_date": "2027-01-10",
    "winter_end_date": "2027-04-15",
    "registration_payment_window_start": "2026-08-01T00:00:00+00:00",
    "registration_payment_window_end": "2026-09-01T00:00:00+00:00",
    "fall_break_periods": [{"start": "2026-10-10", "end": "2026-10-15"}],
    "winter_break_periods": [{"start": "2027-02-20", "end": "2027-02-25"}],
    "intern_interview_deadline": "2026-11-01",
    "teaching_assistant_interview_deadline": "2026-11-15",
    "nowruz_holiday_start": "2027-03-20",
    "nowruz_holiday_end": "2027-04-05",
}


@pytest.mark.asyncio
async def test_publish_fall_calendar_stores_full_extra_data(db_session: AsyncSession):
    anchor = await ensure_institute_operational_student(db_session)
    now = datetime.now(timezone.utc)
    instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code=FALL_PREP,
        current_state_code="published",
        is_completed=True,
        started_at=now,
        context_data=dict(CALENDAR_CTX),
    )
    db_session.add(instance)
    await db_session.flush()

    cal = await publish_calendar_from_instance_context(db_session, instance, CALENDAR_CTX)
    await db_session.commit()

    assert cal.is_active is True
    assert cal.term_start_date.isoformat() == "2026-09-15"
    extra = cal.extra_data or {}
    assert extra.get("fall_start_date") == "2026-09-15"
    assert extra.get("winter_end_date") == "2027-04-15"
    assert extra.get("intern_interview_deadline") == "2026-11-01"
    assert isinstance(extra.get("fall_break_periods"), list)


@pytest.mark.asyncio
async def test_winter_publish_merges_fall_calendar_fields(db_session: AsyncSession):
    anchor = await ensure_institute_operational_student(db_session)
    now = datetime.now(timezone.utc)

    fall_instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code=FALL_PREP,
        current_state_code="published",
        is_completed=True,
        is_cancelled=False,
        started_at=now - timedelta(days=60),
        completed_at=now - timedelta(days=30),
        context_data=dict(CALENDAR_CTX),
    )
    db_session.add(fall_instance)

    winter_instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code=WINTER_PREP,
        current_state_code="published",
        is_completed=True,
        is_cancelled=False,
        started_at=now - timedelta(days=10),
        completed_at=now,
        context_data={},
    )
    db_session.add(winter_instance)
    await db_session.flush()

    cal = await publish_calendar_from_instance_context(db_session, winter_instance, {})
    await db_session.commit()

    extra = cal.extra_data or {}
    assert extra.get("fall_start_date") == "2026-09-15"
    assert extra.get("winter_start_date") == "2027-01-10"
    assert extra.get("nowruz_holiday_start") == "2027-03-20"
    assert cal.term_start_date.isoformat() == "2027-01-10"
    assert cal.source_process_instance_id == winter_instance.id

    from app.services.institute_calendar_service import calendar_to_response_dict

    payload = calendar_to_response_dict(cal)
    assert payload["source_process_instance_id"] == str(winter_instance.id)
    assert payload["source_process_code"] == WINTER_PREP


@pytest.mark.asyncio
async def test_publish_creates_flash_notifications_for_institute_users(
    db_session: AsyncSession,
    sample_user: User,
):
    anchor = await ensure_institute_operational_student(db_session)
    now = datetime.now(timezone.utc)
    instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code=FALL_PREP,
        current_state_code="published",
        is_completed=True,
        started_at=now,
        context_data=dict(CALENDAR_CTX),
    )
    db_session.add(instance)
    await db_session.flush()

    cal = await publish_calendar_from_instance_context(db_session, instance, CALENDAR_CTX)
    await db_session.commit()

    assert cal.term_code
    rows = (
        await db_session.execute(
            select(PanelFlashMessage).where(PanelFlashMessage.user_id == sample_user.id)
        )
    ).scalars().all()
    assert any("/panel/academic-calendar" in (r.source_path or "") for r in rows)


@pytest.mark.asyncio
async def test_sync_sets_academic_calendar_published_on_students(
    db_session: AsyncSession,
    sample_student: Student,
):
    anchor = await ensure_institute_operational_student(db_session)
    now = datetime.now(timezone.utc)
    instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code=FALL_PREP,
        current_state_code="published",
        is_completed=True,
        started_at=now,
        context_data=dict(CALENDAR_CTX),
    )
    db_session.add(instance)
    await db_session.flush()

    await publish_calendar_from_instance_context(db_session, instance, CALENDAR_CTX)
    await db_session.commit()

    await db_session.refresh(sample_student)
    extra = sample_student.extra_data or {}
    assert extra.get("academic_calendar_published") is True
    assert extra.get("term_start_date") == "2026-09-15"
    assert extra.get("academic_calendar_published_at")


@pytest.mark.asyncio
async def test_panel_academic_calendar_therapist_role_ok(db_session: AsyncSession):
    from httpx import ASGITransport, AsyncClient

    suffix = uuid.uuid4().hex[:10]
    therapist = User(
        id=uuid.uuid4(),
        username=f"therapist_cal_{suffix}",
        email=f"therapist_cal_{suffix}@test.com",
        hashed_password=get_password_hash("secret123"),
        full_name_fa="درمانگر تست تقویم",
        role="therapist",
        is_active=True,
    )
    db_session.add(therapist)
    await db_session.commit()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return therapist

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/panel/academic-calendar/active")
            assert r.status_code == 200, r.text
            assert r.json() is None or isinstance(r.json(), dict)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_panel_academic_calendar_interviewer_role_ok(db_session: AsyncSession):
    from httpx import ASGITransport, AsyncClient

    suffix = uuid.uuid4().hex[:10]
    interviewer = User(
        id=uuid.uuid4(),
        username=f"interviewer_cal_{suffix}",
        email=f"interviewer_cal_{suffix}@test.com",
        hashed_password=get_password_hash("secret123"),
        full_name_fa="مصاحبه‌گر تست تقویم",
        role="interviewer",
        is_active=True,
    )
    db_session.add(interviewer)
    await db_session.commit()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return interviewer

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/panel/academic-calendar/active")
            assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
