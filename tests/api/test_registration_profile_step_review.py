"""GET/PATCH پرچم مرور مراحل قبلی روی registration-profile."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_current_user, get_password_hash
from app.database import get_db
from app.main import app
from app.models.operational_models import Student, User


def _client_overrides(db_session: AsyncSession, actor: User):
    async def override_db():
        yield db_session

    async def override_user():
        return actor

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user


def _clear_overrides():
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


async def _make_staff(db_session: AsyncSession) -> User:
    suid = uuid.uuid4().hex[:12]
    staff = User(
        id=uuid.uuid4(),
        username=f"staff_test_{suid}",
        email=f"staff_{suid}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="کارمند تست",
        role="staff",
        is_active=True,
    )
    db_session.add(staff)
    await db_session.commit()
    return staff


@pytest.mark.asyncio
async def test_registration_profile_step_review_defaults_false(
    db_session: AsyncSession,
    sample_user: User,
    sample_student: Student,
    sample_student_user: User,
):
    _client_overrides(db_session, sample_user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/students/by-user/{sample_student_user.id}/registration-profile")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["allow_previous_step_review"] is False
        assert body["student_id"] == str(sample_student.id)
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_admin_can_toggle_previous_step_review(
    db_session: AsyncSession,
    sample_user: User,
    sample_student: Student,
    sample_student_user: User,
):
    extra = dict(sample_student.extra_data or {})
    extra["residence_city"] = "تهران"
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    _client_overrides(db_session, sample_user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            enable = await client.patch(
                f"/api/students/by-user/{sample_student_user.id}/registration-profile",
                json={"allow_previous_step_review": True},
            )
            assert enable.status_code == 200, enable.text
            assert enable.json()["allow_previous_step_review"] is True

            got = await client.get(f"/api/students/by-user/{sample_student_user.id}/registration-profile")
            assert got.status_code == 200, got.text
            assert got.json()["allow_previous_step_review"] is True
            assert got.json().get("residence_city") == "تهران"

            keep = await client.patch(
                f"/api/students/by-user/{sample_student_user.id}/registration-profile",
                json={"residence_city": "اصفهان"},
            )
            assert keep.status_code == 200, keep.text
            assert keep.json()["allow_previous_step_review"] is True

            disable = await client.patch(
                f"/api/students/by-user/{sample_student_user.id}/registration-profile",
                json={"allow_previous_step_review": False},
            )
            assert disable.status_code == 200, disable.text
            assert disable.json()["allow_previous_step_review"] is False
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_staff_can_toggle_previous_step_review(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
):
    staff = await _make_staff(db_session)
    _client_overrides(db_session, staff)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                f"/api/students/by-user/{sample_student_user.id}/registration-profile",
                json={"allow_previous_step_review": True},
            )
        assert r.status_code == 200, r.text
        assert r.json()["allow_previous_step_review"] is True
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_student_cannot_toggle_previous_step_review(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
):
    _client_overrides(db_session, sample_student_user)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.patch(
                f"/api/students/by-user/{sample_student_user.id}/registration-profile",
                json={"allow_previous_step_review": True},
            )
        assert r.status_code == 403
    finally:
        _clear_overrides()
