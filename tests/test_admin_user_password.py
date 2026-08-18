"""تست تنظیم رمز از پنل مدیریت کاربران (PATCH و POST /password)."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_password_hash, verify_password
from app.database import get_db
from app.main import app
from app.models.operational_models import User
from app.services.otp_service import _issue_student_portal_password_if_needed


async def _new_user(db: AsyncSession, *, role: str = "student", username: str | None = None) -> User:
    suffix = uuid.uuid4().hex[:12]
    u = User(
        id=uuid.uuid4(),
        username=username or f"pwtest_{suffix}",
        email=f"{suffix}@user-pw.test",
        hashed_password=get_password_hash("old-secret-99"),
        full_name_fa="کاربر تست رمز",
        role=role,
        is_active=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def admin_pw_client(db_session: AsyncSession, sample_user):
    async def override_db():
        yield db_session

    async def override_user():
        return sample_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_post_set_password_replaces_hash(admin_pw_client, db_session: AsyncSession):
    target = await _new_user(db_session)
    r = await admin_pw_client.post(
        f"/api/admin/users/{target.id}/password",
        json={"password": "NewPass#1"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("password_set") is True
    await db_session.refresh(target)
    assert verify_password("NewPass#1", target.hashed_password)
    assert not verify_password("old-secret-99", target.hashed_password)
    assert (target.profile_meta or {}).get("admin_password_set") is True


@pytest.mark.asyncio
async def test_patch_password_also_applies(admin_pw_client, db_session: AsyncSession):
    target = await _new_user(db_session)
    r = await admin_pw_client.patch(
        f"/api/admin/users/{target.id}",
        json={"password": "PatchPass42"},
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(target)
    assert verify_password("PatchPass42", target.hashed_password)


@pytest.mark.asyncio
async def test_set_password_persian_digits_match_latin_login(
    admin_pw_client, db_session: AsyncSession
):
    target = await _new_user(db_session)
    r = await admin_pw_client.post(
        f"/api/admin/users/{target.id}/password",
        json={"password": "رمز۱۲۳۴"},
    )
    assert r.status_code == 200, r.text
    await db_session.refresh(target)
    assert verify_password("رمز1234", target.hashed_password)
    assert verify_password("رمز۱۲۳۴", target.hashed_password)


@pytest.mark.asyncio
async def test_otp_does_not_overwrite_admin_set_password(db_session: AsyncSession):
    phone = "09121234567"
    target = await _new_user(db_session, username="not-the-phone")
    target.hashed_password = get_password_hash("AdminSet99")
    target.profile_meta = {"admin_password_set": True}
    await db_session.flush()

    issued, plain = await _issue_student_portal_password_if_needed(
        db_session, target, phone, commit=False
    )
    assert issued is False
    assert plain is None
    await db_session.refresh(target)
    assert verify_password("AdminSet99", target.hashed_password)


@pytest.mark.asyncio
async def test_set_password_rejects_too_short(admin_pw_client, db_session: AsyncSession):
    target = await _new_user(db_session)
    r = await admin_pw_client.post(
        f"/api/admin/users/{target.id}/password",
        json={"password": "ab"},
    )
    assert r.status_code == 400
    await db_session.refresh(target)
    assert verify_password("old-secret-99", target.hashed_password)


@pytest.mark.asyncio
async def test_patch_adds_interviewer_role_without_student_profile(
    admin_pw_client, db_session: AsyncSession
):
    """افزودن نقش مصاحبه‌گر از مدیریت کاربران نباید 500 بدهد (MissingGreenlet)."""
    target = await _new_user(db_session, role="course_committee")
    r = await admin_pw_client.patch(
        f"/api/admin/users/{target.id}",
        json={"role": "course_committee", "roles": ["course_committee", "interviewer"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "interviewer" in (body.get("roles") or [])
    assert body.get("role") == "course_committee"
    await db_session.refresh(target)
    assert "interviewer" in (target.roles or [])


@pytest.mark.asyncio
async def test_patch_adds_interviewer_role_on_student(
    admin_pw_client, sample_student_user, sample_student
):
    r = await admin_pw_client.patch(
        f"/api/admin/users/{sample_student_user.id}",
        json={"role": "student", "roles": ["student", "interviewer"]},
    )
    assert r.status_code == 200, r.text
    assert "interviewer" in (r.json().get("roles") or [])
    assert r.json().get("student_code") == sample_student.student_code

