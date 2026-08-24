"""GET /api/students باید نام کاربر لینک‌شده را مثل مدیریت کاربران برگرداند."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models.operational_models import Student, User


@pytest.mark.asyncio
async def test_list_students_includes_full_name_fa(
    db_session: AsyncSession,
    sample_user: User,
    sample_student: Student,
    sample_student_user: User,
):
    async def override_db():
        yield db_session

    async def override_user():
        return sample_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/students")
        assert r.status_code == 200, r.text
        rows = r.json()
        match = next((row for row in rows if row.get("id") == str(sample_student.id)), None)
        assert match is not None
        assert match["student_code"] == sample_student.student_code
        assert match["full_name_fa"] == sample_student_user.full_name_fa
        assert match["full_name_fa"] == "دانشجوی تست"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_get_student_includes_full_name_fa(
    db_session: AsyncSession,
    sample_user: User,
    sample_student: Student,
    sample_student_user: User,
):
    async def override_db():
        yield db_session

    async def override_user():
        return sample_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/students/{sample_student.id}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["full_name_fa"] == sample_student_user.full_name_fa
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
