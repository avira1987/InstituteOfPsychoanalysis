"""
کاربران دمو برای پنل محصول: یک حساب به ازای هر نقش پورتال + کاربران اختصاصی سناریو
(مصاحبه‌گر، مسئول پذیرش، متقاضی) تا در لاگ و ردیابی، actor_id غیر از admin دیده شود.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.models.operational_models import Student, User

ADMIN_PASSWORD = "admin123"
DEFAULT_PASSWORD = "demo123"

SUPPORTED_ROLES: list[str] = [
    "admin",
    "student",
    "therapist",
    "supervisor",
    "staff",
    "finance",
    "site_manager",
    "progress_committee",
    "education_committee",
    "supervision_committee",
    "specialized_commission",
    "therapy_committee_chair",
    "therapy_committee_executor",
    "deputy_education",
    "monitoring_committee_officer",
]

# کاربران اضافه فقط برای actor_id در ترنزیشن‌های مصاحبه/پذیرش (نقش User = staff)
EXTRA_SCENARIO_USERS: list[tuple[str, str]] = [
    ("demo_interviewer", "مصاحبه‌گر دمو (سناریوها)"),
    ("demo_admissions", "مسئول پذیرش دمو (سناریوها)"),
    ("demo_applicant", "متقاضی دمو — سناریوهای ثبت‌نام آشنایی"),
]


def _username_for_role(role: str) -> str:
    return "admin" if role == "admin" else f"{role}1"


def _email_for_username(username: str) -> str:
    return f"{username}@demo.anistito.local"


class DemoActors(NamedTuple):
    admin_id: uuid.UUID
    applicant_id: uuid.UUID
    interviewer_id: uuid.UUID
    admissions_id: uuid.UUID


async def ensure_demo_role_users(db: AsyncSession) -> None:
    """ایجاد/به‌روزرسانی کاربران دمو برای همهٔ نقش‌ها + سه کاربر سناریو."""
    for role in SUPPORTED_ROLES:
        username = _username_for_role(role)
        email = _email_for_username(username)
        full_name_fa = f"کاربر دمو ({role})"
        password = ADMIN_PASSWORD if role == "admin" else DEFAULT_PASSWORD

        result = await db.execute(select(User).where(User.username == username))
        user = result.scalars().first()

        if user:
            user.email = email
            user.full_name_fa = user.full_name_fa or full_name_fa
            user.role = role
            user.hashed_password = get_password_hash(password)
            user.is_active = True
        else:
            user = User(
                id=uuid.uuid4(),
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                full_name_fa=full_name_fa,
                role=role,
                is_active=True,
            )
            db.add(user)
            await db.flush()

        if role == "student":
            r2 = await db.execute(select(Student).where(Student.user_id == user.id))
            student = r2.scalars().first()
            if not student:
                student = Student(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    student_code=f"DEMO-ROLE-STUDENT-{datetime.utcnow().strftime('%Y%m%d')}",
                    course_type="introductory",
                    weekly_sessions=1,
                    term_count=1,
                    current_term=1,
                    therapy_started=False,
                )
                db.add(student)

    for username, full_name_fa in EXTRA_SCENARIO_USERS:
        email = _email_for_username(username)
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        if user:
            user.email = email
            user.full_name_fa = full_name_fa
            user.role = "staff"
            user.hashed_password = get_password_hash(DEFAULT_PASSWORD)
            user.is_active = True
        else:
            user = User(
                id=uuid.uuid4(),
                username=username,
                email=email,
                hashed_password=get_password_hash(DEFAULT_PASSWORD),
                full_name_fa=full_name_fa,
                role="staff",
                is_active=True,
            )
            db.add(user)

    await db.commit()


async def build_demo_actors(db: AsyncSession) -> DemoActors:
    """پس از ensure_demo_role_users، شناسه‌های بازیگران سناریو را برمی‌گرداند."""

    async def _id(username: str) -> uuid.UUID:
        r = await db.execute(select(User).where(User.username == username))
        u = r.scalars().first()
        if not u:
            raise RuntimeError(f"Demo user missing: {username} — run ensure_demo_role_users first")
        return u.id

    return DemoActors(
        admin_id=await _id("admin"),
        applicant_id=await _id("demo_applicant"),
        interviewer_id=await _id("demo_interviewer"),
        admissions_id=await _id("demo_admissions"),
    )
