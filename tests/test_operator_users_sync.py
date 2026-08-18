"""پوشش نقش اپراتوری، نگاشت assigned_role، و upsert بدون تغییر رمز."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import authenticate_user, get_password_hash, verify_password
from app.core.user_roles import user_has_role
from app.demo_role_users import ensure_demo_role_users
from app.meta.operator_state_catalog import portal_role_can_act_on_assigned_role
from app.models.operational_models import User
from app.operator_users_sync import (
    list_operator_payloads,
    roles_missing_coverage,
    upsert_operator_from_payload,
)


@pytest.mark.asyncio
async def test_ensure_demo_covers_operator_roles_and_dakheli(db_session: AsyncSession):
    await ensure_demo_role_users(db_session)

    dakheli = await authenticate_user(db_session, "dakheli1", "demo123")
    assert dakheli is not None
    assert user_has_role(dakheli, "internal_manager", admin_bypass=False)
    assert user_has_role(dakheli, "staff", admin_bypass=False)

    marketing = await authenticate_user(db_session, "marketing1", "demo123")
    assert marketing is not None
    assert user_has_role(marketing, "marketing", admin_bypass=False)

    faculty = await authenticate_user(db_session, "sara_taravati", "demo123")
    assert faculty is not None
    assert user_has_role(faculty, "faculty_1", admin_bypass=False)
    assert user_has_role(faculty, "interviewer", admin_bypass=False)

    payloads = await list_operator_payloads(db_session)
    assert payloads
    missing = roles_missing_coverage(payloads)
    assert not missing, f"roles without active operator user: {missing}"


def test_portal_map_faculty_and_instructor_access():
    assert portal_role_can_act_on_assigned_role("faculty_1", "interviewer")
    assert portal_role_can_act_on_assigned_role("faculty_1", "supervisor")
    assert portal_role_can_act_on_assigned_role("instructor", "instructor")
    assert portal_role_can_act_on_assigned_role("teaching_assistant", "teaching_assistant")
    assert portal_role_can_act_on_assigned_role("marketing", "marketing")
    assert portal_role_can_act_on_assigned_role("therapy_education_coordinator", "therapy_education_coordinator")


@pytest.mark.asyncio
async def test_upsert_operator_keeps_existing_password(db_session: AsyncSession):
    old_hash = get_password_hash("host-secret-99")
    user = User(
        id=uuid.uuid4(),
        username="ops_keep_pwd_test",
        email="ops_keep_pwd_test@t.local",
        hashed_password=old_hash,
        full_name_fa="تست حفظ رمز",
        role="staff",
        roles=["staff"],
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    status = await upsert_operator_from_payload(
        db_session,
        {
            "username": "ops_keep_pwd_test",
            "email": "ops_keep_pwd_test@t.local",
            "full_name_fa": "تست حفظ رمز به‌روز",
            "role": "staff",
            "roles": ["staff", "admissions_officer"],
            "is_active": True,
            "hashed_password": get_password_hash("demo123"),
        },
        keep_existing_password=True,
    )
    assert status == "updated"
    result = await db_session.execute(select(User).where(User.username == "ops_keep_pwd_test"))
    refreshed = result.scalars().first()
    assert refreshed is not None
    assert refreshed.hashed_password == old_hash
    assert verify_password("host-secret-99", refreshed.hashed_password)
    assert user_has_role(refreshed, "admissions_officer", admin_bypass=False)


@pytest.mark.asyncio
async def test_upsert_operator_creates_with_demo_password(db_session: AsyncSession):
    status = await upsert_operator_from_payload(
        db_session,
        {
            "username": "ops_new_host_user",
            "email": "ops_new_host_user@t.local",
            "full_name_fa": "اپراتور جدید",
            "role": "reference_center",
            "roles": ["reference_center"],
            "is_active": True,
        },
        keep_existing_password=True,
    )
    assert status == "created"
    created = await authenticate_user(db_session, "ops_new_host_user", "demo123")
    assert created is not None
    assert user_has_role(created, "reference_center", admin_bypass=False)
