"""قالب یکپارچه شماره/نام کاربری دانشجو (STU-1001 به‌بعد)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash, verify_password
from app.models.operational_models import Student, User
from app.services.otp_service import _issue_student_portal_password_if_needed
from app.services.student_identity import (
    find_user_for_password_login,
    format_student_code,
    is_canonical_student_code,
    next_student_code,
    parse_canonical_stu_number,
    unify_existing_student_identities,
    unify_student_identity,
)


async def _user(db: AsyncSession, username: str, *, role: str = "student") -> User:
    u = User(
        id=uuid.uuid4(),
        username=username,
        email=f"{uuid.uuid4().hex[:10]}@id.test",
        hashed_password=get_password_hash("demo123"),
        full_name_fa="تست هویت",
        role=role,
        roles=[role],
        is_active=True,
        phone="09120000000" if username.startswith("09") else None,
    )
    db.add(u)
    await db.flush()
    return u


async def _student(db: AsyncSession, user: User, code: str) -> Student:
    st = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code=code,
        course_type="comprehensive",
        is_intern=code.upper().startswith("INT"),
    )
    db.add(st)
    await db.flush()
    return st


def test_canonical_template_helpers():
    assert format_student_code(1005) == "STU-1005"
    assert parse_canonical_stu_number("STU-1005") == 1005
    assert parse_canonical_stu_number("stu-1005") == 1005
    assert is_canonical_student_code("STU-1005") is True
    assert is_canonical_student_code("STU-001") is False
    assert is_canonical_student_code("INT-018") is False


@pytest.mark.asyncio
async def test_next_student_code_starts_at_1001(db_session: AsyncSession):
    first = await next_student_code(db_session)
    n = parse_canonical_stu_number(first)
    assert n is not None and n > 1000
    user = await _user(db_session, f"tmp_next_{uuid.uuid4().hex[:8]}")
    await _student(db_session, user, first)
    assert await next_student_code(db_session) == format_student_code(n + 1)


@pytest.mark.asyncio
async def test_unify_intern_code_and_username(db_session: AsyncSession):
    expected = await next_student_code(db_session)
    user = await _user(db_session, "azin_darayan")
    student = await _student(db_session, user, "INT-018")
    result = await unify_student_identity(db_session, student, user)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(student)
    assert result["code"] is True
    assert result["username"] is True
    assert student.student_code == expected
    assert user.username == expected
    assert (student.extra_data or {}).get("legacy_student_code") == "INT-018"
    assert (user.profile_meta or {}).get("legacy_username") == "azin_darayan"


@pytest.mark.asyncio
async def test_unify_phone_username_for_registered_student(db_session: AsyncSession):
    code = await next_student_code(db_session)
    user = await _user(db_session, "09123334455")
    user.phone = "09123334455"
    student = await _student(db_session, user, code)
    result = await unify_student_identity(db_session, student, user)
    await db_session.commit()
    await db_session.refresh(user)
    assert result["code"] is False
    assert result["username"] is True
    assert user.username == code


@pytest.mark.asyncio
async def test_demo_stu_001_username_not_rewritten(db_session: AsyncSession):
    user = await _user(db_session, "student1")
    student = await _student(db_session, user, "STU-001")
    result = await unify_student_identity(db_session, student, user)
    await db_session.commit()
    await db_session.refresh(user)
    assert result == {"code": False, "username": False}
    assert user.username == "student1"
    assert student.student_code == "STU-001"


@pytest.mark.asyncio
async def test_unify_existing_is_idempotent(db_session: AsyncSession):
    expected = await next_student_code(db_session)
    user = await _user(db_session, "azadeh_yousefi")
    await _student(db_session, user, "INT-001")
    first = await unify_existing_student_identities(db_session)
    await db_session.commit()
    second = await unify_existing_student_identities(db_session)
    await db_session.commit()
    assert first["codes"] >= 1
    assert first["usernames"] >= 1
    assert second["codes"] == 0
    assert second["usernames"] == 0
    await db_session.refresh(user)
    assert user.username == expected


@pytest.mark.asyncio
async def test_login_aliases_after_unify(db_session: AsyncSession):
    expected = await next_student_code(db_session)
    user = await _user(db_session, "azin_darayan")
    user.phone = "09125556677"
    student = await _student(db_session, user, "INT-018")
    await unify_student_identity(db_session, student, user)
    await db_session.commit()

    by_new = await find_user_for_password_login(db_session, expected)
    by_old = await find_user_for_password_login(db_session, "azin_darayan")
    by_legacy_code = await find_user_for_password_login(db_session, "INT-018")
    by_phone = await find_user_for_password_login(db_session, "09125556677")
    assert by_new and by_new.id == user.id
    assert by_old and by_old.id == user.id
    assert by_legacy_code and by_legacy_code.id == user.id
    assert by_phone and by_phone.id == user.id


@pytest.mark.asyncio
async def test_otp_does_not_clobber_canonical_username(db_session: AsyncSession):
    uname = format_student_code(18000 + (uuid.uuid4().int % 1000))
    user = await _user(db_session, uname)
    user.phone = "09121112233"
    user.hashed_password = get_password_hash("KeepMe99")
    await db_session.flush()
    issued, plain = await _issue_student_portal_password_if_needed(
        db_session, user, "09121112233", commit=False
    )
    assert issued is False
    assert plain is None
    await db_session.refresh(user)
    assert user.username == uname
    assert verify_password("KeepMe99", user.hashed_password)
