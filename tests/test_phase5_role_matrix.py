"""فاز ۵: سلول‌های خالی ماتریس نقش مؤثر (implied / چندنقشه)."""

from __future__ import annotations

import uuid
from datetime import time
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.alocom_routes import _can_provision_interview_slot
from app.api.auth import get_current_user, get_password_hash
from app.core.portal_role_home import redirect_url_for_role
from app.core.user_roles import ordered_actor_roles, primary_role
from app.database import get_db
from app.main import app
from app.models.operational_models import Student, User
from app.services.educational_therapist_slot_service import (
    create_slot,
    list_available_grouped_by_supervisor,
)
from app.services.semester_prep_rbac import (
    any_user_role_can_act_on_prep_state,
    portal_role_can_act_on_prep_state,
)
from app.services.therapy_workbench_service import assert_can_repair_student


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
async def test_educational_instructor_can_read_academic_calendar(
    db_session: AsyncSession,
) -> None:
    edu = await _make_user(
        db_session,
        role="educational_instructor",
        prefix="edu_cal",
        roles=["educational_instructor"],
    )
    await db_session.commit()
    assert await _calendar_status(db_session, edu) == 200


@pytest.mark.asyncio
async def test_faculty_1_slot_appears_on_supervisor_sheet(
    db_session: AsyncSession,
) -> None:
    faculty = await _make_user(db_session, role="faculty_1", prefix="fac_sheet", roles=["faculty_1"])
    therapist = await _make_user(db_session, role="therapist", prefix="th_sheet", roles=["therapist"])
    await db_session.flush()

    await create_slot(
        db_session,
        therapist_user_id=faculty.id,
        day_of_week=2,
        start_local_time=time(9, 0),
        end_local_time=time(10, 0),
    )
    await create_slot(
        db_session,
        therapist_user_id=therapist.id,
        day_of_week=2,
        start_local_time=time(11, 0),
        end_local_time=time(12, 0),
    )
    await db_session.flush()

    grouped = await list_available_grouped_by_supervisor(db_session)
    ids = {row["id"] for row in grouped.get("supervisors") or []}
    assert str(faculty.id) in ids
    assert str(therapist.id) not in ids


def test_faculty_1_cannot_act_on_staff_semester_prep() -> None:
    faculty = _ns_user(role="faculty_1", roles=["faculty_1"])
    roles = ordered_actor_roles(faculty)
    assert portal_role_can_act_on_prep_state(
        "faculty_1", "fall_semester_preparation", "interviewer_assignment"
    ) is False
    assert portal_role_can_act_on_prep_state(
        "staff", "fall_semester_preparation", "interviewer_assignment"
    ) is True
    assert any_user_role_can_act_on_prep_state(
        roles, "fall_semester_preparation", "interviewer_assignment"
    ) is False


def test_plain_interviewer_alocom_only_own_slot() -> None:
    iid = uuid.uuid4()
    plain = _ns_user(user_id=iid, role="interviewer", roles=["interviewer"])
    own = SimpleNamespace(interviewer_user_id=iid, created_by=None)
    other = SimpleNamespace(interviewer_user_id=uuid.uuid4(), created_by=uuid.uuid4())
    assert _can_provision_interview_slot(plain, own) is True
    assert _can_provision_interview_slot(plain, other) is False


def test_home_faculty_1_supervisor_and_dual_therapist_primary() -> None:
    assert redirect_url_for_role("faculty_1") == "/panel/portal/supervisor?tab=reviews"
    dual = _ns_user(role="therapist", roles=["therapist", "interviewer"])
    assert primary_role(dual) == "therapist"
    assert redirect_url_for_role(primary_role(dual)) == "/panel/portal/therapist?tab=pending"


@pytest.mark.asyncio
async def test_assert_can_repair_student_extra_therapist_own_only(
    db_session: AsyncSession,
    sample_student: Student,
) -> None:
    extra = await _make_user(
        db_session,
        role="site_manager",
        prefix="extra_th",
        roles=["site_manager", "therapist"],
    )
    plain = await _make_user(db_session, role="therapist", prefix="plain_th", roles=["therapist"])
    sample_student.therapist_id = extra.id
    await db_session.flush()

    owned = await assert_can_repair_student(db_session, extra, sample_student.id)
    assert owned.id == sample_student.id

    with pytest.raises(PermissionError, match="منتسب نیست"):
        await assert_can_repair_student(db_session, plain, sample_student.id)
