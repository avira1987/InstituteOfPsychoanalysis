"""
تست DELETE /api/admin/users/{user_id}: غیرفعال‌سازی (پیش‌فرض)، حذف دائمی،
و پاک‌سازی رکوردهای وابسته (financial / therapy / attendance) قبل از حذف دانشجو.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_password_hash
from app.database import get_db
from app.main import app
from app.models.operational_models import (
    AttendanceRecord,
    FinancialRecord,
    Student,
    TherapySession,
    User,
)


async def _new_user(db: AsyncSession, *, role: str = "student") -> User:
    suffix = uuid.uuid4().hex[:12]
    u = User(
        id=uuid.uuid4(),
        username=f"deltest_{suffix}",
        email=f"{suffix}@user-del.test",
        hashed_password=get_password_hash("secret123"),
        full_name_fa="کاربر تست حذف",
        role=role,
        is_active=True,
    )
    db.add(u)
    await db.flush()
    return u


async def _new_student_profile(db: AsyncSession, user: User) -> Student:
    st = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code=f"DEL-{uuid.uuid4().hex[:8].upper()}",
        course_type="comprehensive",
        term_count=1,
        current_term=1,
        weekly_sessions=1,
        is_intern=False,
    )
    db.add(st)
    await db.flush()
    return st


@pytest_asyncio.fixture
async def admin_delete_client(db_session: AsyncSession, sample_user):
    """کلاینت HTTP با همان نشست پایگاه داده و کاربر مدیر برای تست delete users."""

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


@pytest_asyncio.fixture
async def staff_delete_client_and_admin_id(db_session: AsyncSession, sample_user):
    """کارمند: نباید بتواند حذف کاربر مدیر را انجام دهد (403)."""

    staff = await _new_user(db_session, role="staff")

    async def override_db():
        yield db_session

    async def override_staff():
        return staff

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_staff
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac, sample_user.id
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_staff_cannot_delete_user(staff_delete_client_and_admin_id):
    """نقش staff به endpoint حذف کاربر دسترسی ندارد."""
    client, admin_id = staff_delete_client_and_admin_id
    r = await client.delete(f"/api/admin/users/{admin_id}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_delete_self_returns_400(admin_delete_client, sample_user):
    """حذف یا غیرفعال‌سازی حساب خودی ممنوع است."""
    r = await admin_delete_client.delete(f"/api/admin/users/{sample_user.id}")
    assert r.status_code == 400
    assert "own account" in (r.json().get("detail") or "").lower()


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(admin_delete_client):
    r = await admin_delete_client.delete(f"/api/admin/users/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_default_succeeds(admin_delete_client, db_session: AsyncSession):
    """بدون permanent: فقط is_active=false می‌شود و ردیف در DB می‌ماند."""
    target = await _new_user(db_session)
    uid = target.id

    r = await admin_delete_client.delete(f"/api/admin/users/{uid}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("permanent") is False

    refreshed = await db_session.get(User, uid)
    assert refreshed is not None
    assert refreshed.is_active is False


@pytest.mark.asyncio
async def test_deactivate_succeeds_when_student_has_financial_record(
    admin_delete_client,
    db_session: AsyncSession,
):
    """غیرفعال‌سازی نباید به CASCADE روی دانشجو وابسته باشد؛ FK مانع نشود."""
    user = await _new_user(db_session)
    student = await _new_student_profile(db_session, user)
    db_session.add(
        FinancialRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            record_type="payment",
            amount=1200000.0,
            description_fa="تست مانع غیرفعال‌سازی",
        )
    )
    await db_session.flush()

    r = await admin_delete_client.delete(f"/api/admin/users/{user.id}")
    assert r.status_code == 200, r.text
    remaining = await db_session.get(User, user.id)
    assert remaining is not None and remaining.is_active is False


@pytest.mark.asyncio
async def test_permanent_delete_student_without_blockers(admin_delete_client, db_session):
    """دانشجو بدون ردیف مانع؛ حذف کاربر باید با CASCADE دانشجو را پاک کند."""
    user = await _new_user(db_session)
    await _new_student_profile(db_session, user)
    uid = user.id

    r = await admin_delete_client.delete(f"/api/admin/users/{uid}?permanent=true")
    assert r.status_code == 200, r.text
    assert r.json().get("permanent") is True

    assert await db_session.get(User, uid) is None
    r_st = await db_session.execute(select(Student).where(Student.user_id == uid))
    assert r_st.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_permanent_delete_non_student_user(admin_delete_client, db_session):
    """کاربر بدون پروفایل دانشجویی باید حذف فیزیکی شود."""
    therapist = await _new_user(db_session, role="therapist")

    r = await admin_delete_client.delete(f"/api/admin/users/{therapist.id}?permanent=true")
    assert r.status_code == 200, r.text
    assert await db_session.get(User, therapist.id) is None


@pytest.mark.asyncio
async def test_permanent_delete_succeeds_and_removes_financial_records(
    admin_delete_client,
    db_session: AsyncSession,
):
    """حذف دائمی باید رکوردهای مالی دانشجو را هم پاک کند (FK قبلاً RESTRICT بود)."""
    user = await _new_user(db_session)
    student = await _new_student_profile(db_session, user)
    target_id = user.id
    db_session.add(
        FinancialRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            record_type="debt",
            amount=500000.0,
        )
    )
    await db_session.flush()
    await db_session.commit()

    r = await admin_delete_client.delete(f"/api/admin/users/{target_id}?permanent=true")
    assert r.status_code == 200, r.text
    assert r.json().get("permanent") is True

    fin_count = await db_session.execute(
        select(func.count()).select_from(FinancialRecord).where(FinancialRecord.student_id == student.id)
    )
    assert fin_count.scalar_one() == 0
    assert await db_session.get(User, target_id) is None


@pytest.mark.asyncio
async def test_permanent_delete_succeeds_and_removes_therapy_session(
    admin_delete_client, db_session: AsyncSession
):
    user = await _new_user(db_session)
    student = await _new_student_profile(db_session, user)
    db_session.add(
        TherapySession(
            id=uuid.uuid4(),
            student_id=student.id,
            session_date=date.today(),
            status="scheduled",
        )
    )
    await db_session.flush()

    r = await admin_delete_client.delete(f"/api/admin/users/{user.id}?permanent=true")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_permanent_delete_succeeds_and_removes_attendance_record(
    admin_delete_client, db_session: AsyncSession
):
    user = await _new_user(db_session)
    student = await _new_student_profile(db_session, user)
    db_session.add(
        AttendanceRecord(
            id=uuid.uuid4(),
            student_id=student.id,
            record_date=date.today(),
            status="present",
        )
    )
    await db_session.flush()

    r = await admin_delete_client.delete(f"/api/admin/users/{user.id}?permanent=true")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_permanent_delete_therapist_referenced_as_supervisor_succeeds(
    admin_delete_client,
    db_session,
):
    """_nullify_references باید supervisor_id را خالی کند تا حذف ممکن باشد."""
    therapist = await _new_user(db_session, role="therapist")
    student_owner = await _new_user(db_session)
    student = await _new_student_profile(db_session, student_owner)
    student.supervisor_id = therapist.id
    await db_session.flush()

    r = await admin_delete_client.delete(f"/api/admin/users/{therapist.id}?permanent=true")
    assert r.status_code == 200, r.text
    assert await db_session.get(User, therapist.id) is None

    await db_session.refresh(student)
    assert student.supervisor_id is None


@pytest.mark.asyncio
async def test_permanent_delete_therapist_referenced_as_student_therapist_field_succeeds(
    admin_delete_client,
    db_session,
):
    """students.therapist_id بدون CASCADE باید قبل از حذف با nullify آزاد شود."""
    therapist = await _new_user(db_session, role="therapist")
    student_owner = await _new_user(db_session)
    student = await _new_student_profile(db_session, student_owner)
    student.therapist_id = therapist.id
    await db_session.flush()

    r = await admin_delete_client.delete(f"/api/admin/users/{therapist.id}?permanent=true")
    assert r.status_code == 200, r.text

    await db_session.refresh(student)
    assert student.therapist_id is None
