"""فاز ۴: لیست‌های سخت قابلیت با implied و نقش ثانویه."""

from __future__ import annotations

import uuid
from datetime import time
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.alocom_routes import _can_access_session, _can_provision_interview_slot
from app.api.auth import get_current_user, get_password_hash
from app.api.therapy_routes import _can_write_session
from app.api.therapy_workbench_routes import _resolve_role_scope
from app.database import get_db
from app.main import app
from app.models.operational_models import User
from app.services.course_committee_roster_service import _user_member_kind
from app.services.educational_therapist_slot_service import create_slot


def _ns_user(*, user_id=None, role: str, roles: list[str] | None = None, **extra) -> SimpleNamespace:
    uid = user_id or uuid.uuid4()
    return SimpleNamespace(
        id=uid,
        role=role,
        roles=list(roles) if roles is not None else [role],
        **extra,
    )


async def _make_user(
    db: AsyncSession,
    *,
    role: str,
    prefix: str,
    roles: list[str] | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        username=f"{prefix}_{uuid.uuid4().hex[:10]}",
        email=f"{prefix}_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa=prefix,
        role=role,
        roles=list(roles) if roles is not None else [role],
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _calendar_status(db: AsyncSession, user: User) -> int:
    async def override_get_db():
        yield db

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/panel/academic-calendar/active")
            return r.status_code
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_faculty_1_and_internal_manager_can_read_academic_calendar(
    db_session: AsyncSession,
) -> None:
    faculty = await _make_user(db_session, role="faculty_1", prefix="fac_cal", roles=["faculty_1"])
    manager = await _make_user(
        db_session, role="internal_manager", prefix="im_cal", roles=["internal_manager"]
    )
    await db_session.commit()
    assert await _calendar_status(db_session, faculty) == 200
    assert await _calendar_status(db_session, manager) == 200


@pytest.mark.asyncio
async def test_create_slot_accepts_faculty_1_and_plain_therapist(
    db_session: AsyncSession,
) -> None:
    faculty = await _make_user(db_session, role="faculty_1", prefix="fac_slot", roles=["faculty_1"])
    therapist = await _make_user(db_session, role="therapist", prefix="th_slot", roles=["therapist"])
    finance = await _make_user(db_session, role="finance", prefix="fin_slot", roles=["finance"])
    await db_session.flush()

    fac_slot = await create_slot(
        db_session,
        therapist_user_id=faculty.id,
        day_of_week=5,
        start_local_time=time(10, 0),
        end_local_time=time(11, 0),
    )
    th_slot = await create_slot(
        db_session,
        therapist_user_id=therapist.id,
        day_of_week=5,
        start_local_time=time(12, 0),
        end_local_time=time(13, 0),
    )
    assert fac_slot.therapist_user_id == faculty.id
    assert th_slot.therapist_user_id == therapist.id

    with pytest.raises(ValueError, match="درمانگر/سوپروایزر"):
        await create_slot(
            db_session,
            therapist_user_id=finance.id,
            day_of_week=5,
            start_local_time=time(14, 0),
            end_local_time=time(15, 0),
        )


def test_user_member_kind_educational_instructor_and_meta_priority() -> None:
    edu = _ns_user(role="educational_instructor", roles=["educational_instructor"], profile_meta={})
    assert _user_member_kind(edu) == "instructor"

    meta_ta = _ns_user(
        role="educational_instructor",
        roles=["educational_instructor"],
        profile_meta={"member_kind": "teaching_assistant"},
    )
    assert _user_member_kind(meta_ta) == "teaching_assistant"


def test_can_write_session_extra_therapist_own_only() -> None:
    own = uuid.uuid4()
    other = uuid.uuid4()
    extra = _ns_user(user_id=own, role="site_manager", roles=["site_manager", "therapist"])
    plain = _ns_user(user_id=own, role="therapist", roles=["therapist"])
    assert _can_write_session(extra, SimpleNamespace(therapist_id=own)) is True
    assert _can_write_session(plain, SimpleNamespace(therapist_id=other)) is False
    assert _can_access_session(extra, SimpleNamespace(therapist_id=own)) is True
    assert _can_access_session(plain, SimpleNamespace(therapist_id=other)) is False


def test_resolve_role_scope_staff_plus_therapist_defaults_to_therapist() -> None:
    dual = _ns_user(role="staff", roles=["staff", "therapist"])
    assert _resolve_role_scope(dual, None) == "therapist"
    admin = _ns_user(role="admin", roles=["admin"])
    assert _resolve_role_scope(admin, None) == "staff"


def test_alocom_interview_ownership_for_faculty_1() -> None:
    fid = uuid.uuid4()
    faculty = _ns_user(user_id=fid, role="faculty_1", roles=["faculty_1"])
    own = SimpleNamespace(interviewer_user_id=fid, created_by=None)
    created = SimpleNamespace(interviewer_user_id=None, created_by=fid)
    other = SimpleNamespace(interviewer_user_id=uuid.uuid4(), created_by=uuid.uuid4())
    assert _can_provision_interview_slot(faculty, own) is True
    assert _can_provision_interview_slot(faculty, created) is True
    assert _can_provision_interview_slot(faculty, other) is False
