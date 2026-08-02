"""تست انتشار تقویم آموزشی — snapshot دو ترم، merge پاییز در زمستان، sync پرچم."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_password_hash
from app.database import get_db
from app.main import app
from app.models.operational_models import InstituteCalendar, PanelFlashMessage, ProcessInstance, Student, User
from app.services.institute_calendar_service import (
    calendar_payload_from_context,
    publish_calendar_from_instance_context,
    resolve_registration_window,
    upsert_active_calendar,
)
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_service import FALL_PREP, WINTER_PREP
from app.utils.shamsi_calendar_utils import tehran_today

CALENDAR_CTX: dict = {
    "fall_start_date": "2026-09-15",
    "fall_end_date": "2026-12-20",
    "winter_start_date": "2027-01-10",
    "winter_end_date": "2027-04-15",
    "registration_payment_window_start": "2026-08-01T00:00:00+00:00",
    "registration_payment_window_end": "2026-09-01T00:00:00+00:00",
    "fall_break_periods": [{"start": "2026-10-10", "end": "2026-10-15"}],
    "winter_break_periods": [{"start": "2027-02-20", "end": "2027-02-25"}],
    "intern_interview_deadline_start": "2026-10-25",
    "intern_interview_deadline_end": "2026-11-01",
    "teaching_assistant_interview_deadline_start": "2026-11-08",
    "teaching_assistant_interview_deadline_end": "2026-11-15",
    "nowruz_holiday_start": "2027-03-20",
    "nowruz_holiday_end": "2027-04-05",
}


@pytest.mark.asyncio
async def test_date_only_registration_window_uses_tehran_day_bounds():
    payload = calendar_payload_from_context(
        {
            "fall_start_date": "2026-09-15",
            "registration_payment_window_start": "2026-08-01",
            "registration_payment_window_end": "2026-09-01",
        },
        source_process_code=FALL_PREP,
    )
    assert payload["registration_open_at"] is not None
    assert payload["registration_deadline_at"] is not None
    # پایان روز ۱ شهریور تهران ≈ ۲۰:۲۹:۵۹ UTC
    assert payload["registration_deadline_at"].hour == 20
    assert payload["registration_deadline_at"].minute == 29


@pytest.mark.asyncio
async def test_resolve_registration_window_from_extra_data_snapshot(db_session: AsyncSession):
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

    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code="fall-stale-window",
        is_active=True,
        term_start_date=datetime(2026, 9, 15).date(),
        term_end_date=datetime(2026, 12, 20).date(),
        registration_open_at=None,
        registration_deadline_at=None,
        published_at=now,
        source_process_instance_id=instance.id,
        extra_data={
            "registration_payment_window_start": "2026-08-01",
            "registration_payment_window_end": "2026-09-01",
        },
    )
    db_session.add(cal)
    await db_session.flush()

    reg_open, reg_deadline = resolve_registration_window(cal)
    assert reg_open is not None
    assert reg_deadline is not None
    assert reg_deadline.hour == 20
    assert reg_deadline.minute == 29


@pytest.mark.asyncio
async def test_upsert_preserves_registration_window_when_payload_missing(
    db_session: AsyncSession,
):
    now = datetime.now(timezone.utc)
    existing = InstituteCalendar(
        id=uuid.uuid4(),
        term_code="fall-preserve-window",
        is_active=True,
        term_start_date=datetime(2026, 9, 15).date(),
        term_end_date=datetime(2026, 12, 20).date(),
        registration_open_at=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        registration_deadline_at=datetime(2026, 9, 1, 20, 29, 59, tzinfo=timezone.utc),
        published_at=now,
        extra_data={},
    )
    db_session.add(existing)
    await db_session.flush()

    updated = await upsert_active_calendar(
        db_session,
        payload={
            "term_code": "winter-preserve-window",
            "term_start_date": datetime(2027, 1, 10).date(),
            "term_end_date": datetime(2027, 4, 15).date(),
            "registration_open_at": None,
            "registration_deadline_at": None,
        },
    )
    assert updated.registration_open_at == existing.registration_open_at
    assert updated.registration_deadline_at == existing.registration_deadline_at


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
    assert extra.get("intern_interview_deadline_start") == "2026-10-25"
    assert extra.get("intern_interview_deadline_end") == "2026-11-01"
    assert isinstance(extra.get("fall_break_periods"), list)


@pytest.mark.asyncio
async def test_upsert_aligns_columns_from_registration_snapshot(
    db_session: AsyncSession,
):
    """وقتی snapshot جدید در extra است، نباید ستون‌های قدیمی پنجرهٔ ثبت‌نام حفظ شوند."""
    from app.utils.shamsi_calendar_utils import tehran_day_end_utc, tehran_day_start_utc

    today = tehran_today()
    new_start = today - timedelta(days=1)
    new_end = today + timedelta(days=30)
    old_start = date(2025, 1, 1)
    old_end = date(2025, 2, 1)

    existing = InstituteCalendar(
        id=uuid.uuid4(),
        term_code="fall-align-window",
        is_active=True,
        term_start_date=date(2026, 9, 15),
        term_end_date=date(2026, 12, 20),
        registration_open_at=tehran_day_start_utc(old_start),
        registration_deadline_at=tehran_day_end_utc(old_end),
        published_at=datetime.now(timezone.utc),
        extra_data={},
    )
    db_session.add(existing)
    await db_session.flush()

    updated = await upsert_active_calendar(
        db_session,
        payload={
            "term_code": "fall-align-window",
            "term_start_date": date(2026, 9, 15),
            "term_end_date": date(2026, 12, 20),
            "registration_open_at": None,
            "registration_deadline_at": None,
            "extra_data": {
                "registration_payment_window_start": new_start.isoformat(),
                "registration_payment_window_end": new_end.isoformat(),
            },
        },
    )
    assert updated.registration_open_at == tehran_day_start_utc(new_start)
    assert updated.registration_deadline_at == tehran_day_end_utc(new_end)


@pytest.mark.asyncio
async def test_resolve_registration_window_uses_column_when_extra_snapshot_stale(
    db_session: AsyncSession,
):
    """پس از اصلاح از طریق scheduler، ستون‌های تقویم باید بر snapshot قدیمی غلبه کنند."""
    from app.utils.shamsi_calendar_utils import tehran_day_end_utc, tehran_day_start_utc

    today = tehran_today()
    new_start = today - timedelta(days=1)
    new_end = today + timedelta(days=30)
    old_start = date(2025, 1, 1)
    old_end = date(2025, 2, 1)

    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code="fall-desync-window",
        is_active=True,
        term_start_date=date(2026, 9, 15),
        term_end_date=date(2026, 12, 20),
        registration_open_at=tehran_day_start_utc(new_start),
        registration_deadline_at=tehran_day_end_utc(new_end),
        published_at=datetime.now(timezone.utc),
        extra_data={
            "registration_payment_window_start": old_start.isoformat(),
            "registration_payment_window_end": old_end.isoformat(),
        },
    )
    db_session.add(cal)
    await db_session.flush()

    reg_open, reg_deadline = resolve_registration_window(cal)
    assert reg_open == tehran_day_start_utc(new_start)
    assert reg_deadline == tehran_day_end_utc(new_end)


@pytest.mark.asyncio
async def test_prep_calendar_correction_reopens_registration_window(
    db_session: AsyncSession,
    sample_user: User,
):
    """پس از گذشت مهلت ثبت‌نام، اصلاح پنجره در آماده‌سازی پاییز باید gate را باز کند."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.institute_calendar_service import get_active_calendar
    from app.services.registration_readiness_service import check_intro_registration_gate
    from app.services.semester_prep_service import sync_active_institute_calendar_after_prep_correction
    from app.utils.shamsi_calendar_utils import tehran_today

    anchor = await ensure_institute_operational_student(db_session)
    now = datetime.now(timezone.utc)
    instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code=FALL_PREP,
        current_state_code="published",
        is_completed=True,
        started_at=now,
        context_data=dict(CALENDAR_CTX)
        | {
            "registration_payment_window_start": "2025-01-01",
            "registration_payment_window_end": "2025-02-01",
        },
    )
    db_session.add(instance)
    await db_session.flush()

    await publish_calendar_from_instance_context(db_session, instance, instance.context_data)
    await db_session.commit()

    gate_before = await check_intro_registration_gate(db_session)
    assert gate_before.allowed is False
    assert gate_before.in_registration_window is False

    today = tehran_today()
    new_start = (today - timedelta(days=1)).isoformat()
    new_end = (today + timedelta(days=30)).isoformat()
    instance.context_data = {
        **(instance.context_data or {}),
        "registration_payment_window_start": new_start,
        "registration_payment_window_end": new_end,
    }
    flag_modified(instance, "context_data")
    await db_session.flush()

    await sync_active_institute_calendar_after_prep_correction(
        db_session,
        instance,
        updated_field_names={
            "registration_payment_window_start",
            "registration_payment_window_end",
        },
        published_by=sample_user.id,
    )
    await db_session.commit()

    cal = await get_active_calendar(db_session)
    reg_open, reg_deadline = resolve_registration_window(cal)
    assert reg_open is not None
    assert reg_deadline is not None
    assert cal.extra_data.get("registration_payment_window_start") == new_start
    assert cal.extra_data.get("registration_payment_window_end") == new_end

    gate_after = await check_intro_registration_gate(db_session)
    assert gate_after.allowed is True
    assert gate_after.in_registration_window is True


@pytest.mark.asyncio
async def test_prep_calendar_correction_syncs_active_institute_calendar(
    db_session: AsyncSession,
    sample_user: User,
):
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.semester_prep_service import sync_active_institute_calendar_after_prep_correction

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

    instance.context_data = {
        **(instance.context_data or {}),
        "intern_interview_deadline_start": "2026-10-28",
    }
    flag_modified(instance, "context_data")
    await db_session.flush()

    await sync_active_institute_calendar_after_prep_correction(
        db_session,
        instance,
        updated_field_names={"intern_interview_deadline_start"},
        published_by=sample_user.id,
    )
    await db_session.commit()

    cal = (
        await db_session.execute(
            select(InstituteCalendar).where(InstituteCalendar.is_active.is_(True))
        )
    ).scalars().first()
    assert cal is not None
    extra = cal.extra_data or {}
    assert extra.get("intern_interview_deadline_start") == "2026-10-28"


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
