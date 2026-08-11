"""کمیته نظارت باید بتواند فهرست درمانگران شیت وقت آزاد را ببیند."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models.operational_models import User


@pytest.mark.asyncio
async def test_manage_therapists_visible_to_supervision_committee(db_session: AsyncSession):
    therapist = User(
        id=uuid.uuid4(),
        username=f"therapist_list_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        role="therapist",
        full_name_fa="درمانگر شیت تست",
        is_active=True,
    )
    committee = User(
        id=uuid.uuid4(),
        username=f"sup_comm_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        role="supervision_committee",
        full_name_fa="کمیته نظارت تست",
        is_active=True,
    )
    db_session.add_all([therapist, committee])
    await db_session.commit()

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return committee

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            denied = await client.get(
                "/api/admin/users", params={"role": "therapist", "is_active": True}
            )
            assert denied.status_code == 403

            ok = await client.get("/api/educational-therapist-slots/manage/therapists")
            assert ok.status_code == 200, ok.text
            rows = ok.json().get("therapists") or []
            assert any(r["id"] == str(therapist.id) for r in rows)
            hit = next(r for r in rows if r["id"] == str(therapist.id))
            assert hit["label_fa"] == "درمانگر شیت تست"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_manage_therapists_forbidden_for_student(
    db_session: AsyncSession, sample_student_user: User
):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return sample_student_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.get("/api/educational-therapist-slots/manage/therapists")
            assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
