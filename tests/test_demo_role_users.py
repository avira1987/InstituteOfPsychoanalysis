"""حساب‌های دموی پذیرش و معاون آموزش باید با نقش درست و رمز demo123 ساخته شوند."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import authenticate_user
from app.core.user_roles import user_has_role
from app.demo_role_users import ensure_demo_role_users
from app.models.operational_models import User


@pytest.mark.asyncio
async def test_ensure_demo_role_users_creates_prep_operators(db_session: AsyncSession):
    await ensure_demo_role_users(db_session)

    deputy = await authenticate_user(db_session, "deputy_education1", "demo123")
    assert deputy is not None
    assert deputy.is_active
    assert user_has_role(deputy, "deputy_education")
    assert user_has_role(deputy, "deputy_education_director")

    admissions = await authenticate_user(db_session, "demo_admissions", "demo123")
    assert admissions is not None
    assert admissions.is_active
    assert user_has_role(admissions, "staff")
    assert user_has_role(admissions, "admissions_officer")

    by_alias = await authenticate_user(db_session, "admissions_officer", "demo123")
    assert by_alias is not None
    assert by_alias.id == admissions.id

    director_alias = await authenticate_user(db_session, "deputy_education_director", "demo123")
    assert director_alias is not None
    assert director_alias.id == deputy.id


@pytest.mark.asyncio
async def test_ensure_demo_role_users_resets_password(db_session: AsyncSession):
    await ensure_demo_role_users(db_session)
    result = await db_session.execute(select(User).where(User.username == "demo_admissions"))
    user = result.scalars().first()
    assert user is not None
    user.hashed_password = "not-a-valid-hash"
    user.is_active = False
    await db_session.commit()

    await ensure_demo_role_users(db_session)
    restored = await authenticate_user(db_session, "demo_admissions", "demo123")
    assert restored is not None
    assert restored.is_active
