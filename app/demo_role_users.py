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
from app.core.user_roles import apply_roles_to_user
from app.models.operational_models import Student, User
from app.operator_named_users_seed import ensure_operator_named_users
from app.website_staff_seed import ensure_staff_employees

ADMIN_PASSWORD = "admin123"
DEFAULT_PASSWORD = "demo123"

# نقش‌هایی که حساب {role}1 می‌گیرند (به‌جز admin)
SUPPORTED_ROLES: list[str] = [
    "admin",
    "student",
    "therapist",
    "supervisor",
    "staff",
    "finance",
    "site_manager",
    "interviewer",
    "progress_committee",
    "education_committee",
    "supervision_committee",
    "specialized_commission",
    "therapy_committee_chair",
    "deputy_education",
    "course_committee",
    "instructor",
    "educational_instructor",
    "teaching_assistant",
    "assistant_faculty",
    "therapy_education_coordinator",
    "reference_center",
    "marketing",
]

# نقش‌هایی که فقط از طریق alias / حساب واحد پوشش داده می‌شوند (بدون {role}1 جدا)
_MERGED_ROLE_ALIASES_FOR_LOGIN = frozenset({
    "monitoring_committee_officer",
    "progress_committee_project",
    "progress_committee_scientific",
    "therapy_committee_executor",
    "course_committee_executive",
    "course_committee_scientific",
    "scientific_officer_course_committee",
    "deputy_education_director",
    "admissions_officer",
    "internal_manager",
    "faculty_1",
})

# نام کاربری قدیمی / نام نقش → حساب واحد
_LOGIN_USERNAME_ALIASES: dict[str, str] = {
    "monitoring_committee_officer": "supervision_committee1",
    "monitoring_committee_officer1": "supervision_committee1",
    "progress_committee_project": "progress_committee1",
    "progress_committee_project1": "progress_committee1",
    "progress_committee_scientific": "progress_committee1",
    "progress_committee_scientific1": "progress_committee1",
    "therapy_committee_executor": "therapy_committee_chair1",
    "therapy_committee_executor1": "therapy_committee_chair1",
    "course_committee_executive": "course_committee1",
    "course_committee_executive1": "course_committee1",
    "scientific_officer_course_committee": "course_committee1",
    "scientific_officer_course_committee1": "course_committee1",
    "course_committee_scientific": "course_committee1",
    "course_committee_scientific1": "course_committee1",
    "staf1": "staff1",
    "dakheli": "dakheli1",
    "internal_manager": "dakheli1",
    "internal_manager1": "dakheli1",
    "admissions_officer": "demo_admissions",
    "admissions_officer1": "demo_admissions",
    "deputy_education_director": "deputy_education1",
    "deputy_education_director1": "deputy_education1",
}

_LEGACY_UNIFIED_USERNAMES: tuple[str, ...] = (
    "monitoring_committee_officer1",
    "progress_committee_project1",
    "progress_committee_scientific1",
    "therapy_committee_executor1",
    "course_committee_executive1",
    "scientific_officer_course_committee1",
    "course_committee_scientific1",
)

_MULTI_ROLES_BY_PRIMARY: dict[str, list[str]] = {
    "progress_committee": [
        "progress_committee",
        "progress_committee_project",
        "progress_committee_scientific",
    ],
    "supervision_committee": [
        "supervision_committee",
        "monitoring_committee_officer",
    ],
    "therapy_committee_chair": [
        "therapy_committee_chair",
        "therapy_committee_executor",
    ],
    "course_committee": [
        "course_committee",
        "course_committee_executive",
        "scientific_officer_course_committee",
        "course_committee_scientific",
    ],
    "deputy_education": [
        "deputy_education",
        "deputy_education_director",
    ],
}

# کاربران اضافهٔ سناریو: (username, full_name_fa, primary_role, extra_roles)
EXTRA_SCENARIO_USERS: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("demo_interviewer", "مصاحبه‌گر دمو (سناریوها)", "interviewer", ()),
    (
        "demo_admissions",
        "مسئول پذیرش دمو (سناریوها)",
        "staff",
        ("admissions_officer",),
    ),
    ("demo_applicant", "متقاضی دمو — سناریوهای ثبت‌نام آشنایی", "staff", ()),
]

# موبایل ثابت برای ورود/اعلان دمو (با seed آماده‌سازی ترم هم‌خوان است)
_DEMO_OPERATOR_PHONES: dict[str, str] = {
    "deputy_education1": "09121000001",
    "staff1": "09121000002",
    "site_manager1": "09121000003",
    "demo_admissions": "09121000004",
    "course_committee1": "09121000005",
}


def _username_for_role(role: str) -> str:
    return "admin" if role == "admin" else f"{role}1"


def resolve_portal_login_username(username: str) -> str:
    """حساب‌های دمو با پسوند ۱ ساخته می‌شوند؛ نام نقش بدون ۱ هم پذیرفته می‌شود."""
    u = (username or "").strip()
    if not u or u == "admin":
        return u
    alias = _LOGIN_USERNAME_ALIASES.get(u)
    if alias:
        return alias
    if u.endswith("1"):
        return u
    if u in SUPPORTED_ROLES:
        return f"{u}1"
    return u


def _email_for_username(username: str) -> str:
    return f"{username}@demo.anistito.local"


class DemoActors(NamedTuple):
    admin_id: uuid.UUID
    applicant_id: uuid.UUID
    interviewer_id: uuid.UUID
    admissions_id: uuid.UUID


DEMO_ROLE_NAMES_FA: dict[str, str] = {
    "deputy_education": "معاون آموزش (دمو)",
    "instructor": "مدرس (دمو)",
    "educational_instructor": "مدرس آموزشی (دمو)",
    "teaching_assistant": "کمک‌مدرس (دمو)",
    "assistant_faculty": "دستیار آموزشی (دمو)",
    "therapy_education_coordinator": "هماهنگ‌کننده آموزش درمان (دمو)",
    "reference_center": "مرکز مرجع (دمو)",
    "marketing": "مارکتینگ (دمو)",
}


async def _email_taken_by_other(
    db: AsyncSession, email: str, user_id: uuid.UUID | None
) -> bool:
    result = await db.execute(select(User).where(User.email == email))
    owner = result.scalars().first()
    if not owner:
        return False
    return user_id is None or owner.id != user_id


async def _upsert_demo_user(
    db: AsyncSession,
    *,
    username: str,
    full_name_fa: str,
    role: str,
    roles_list: list[str],
    password: str,
) -> User:
    """ایجاد یا بازنشانی حساب دمو با نقش و رمز مشخص."""
    desired_email = _email_for_username(username)
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    hashed = get_password_hash(password)
    phone = _DEMO_OPERATOR_PHONES.get(username)
    if user:
        apply_roles_to_user(user, roles_list, primary=role)
        user.full_name_fa = full_name_fa
        user.hashed_password = hashed
        user.portal_password_plain = None
        user.is_active = True
        if not await _email_taken_by_other(db, desired_email, user.id):
            user.email = desired_email
        if phone:
            user.phone = phone
        return user
    email = None if await _email_taken_by_other(db, desired_email, None) else desired_email
    user = User(
        id=uuid.uuid4(),
        username=username,
        email=email,
        hashed_password=hashed,
        portal_password_plain=None,
        full_name_fa=full_name_fa,
        is_active=True,
        phone=phone,
    )
    apply_roles_to_user(user, roles_list, primary=role)
    db.add(user)
    await db.flush()
    return user


async def ensure_demo_role_users(db: AsyncSession) -> None:
    """ایجاد/به‌روزرسانی کاربران دمو برای همهٔ نقش‌ها + سه کاربر سناریو."""
    for role in SUPPORTED_ROLES:
        username = _username_for_role(role)
        full_name_fa = DEMO_ROLE_NAMES_FA.get(role, f"کاربر دمو ({role})")
        password = ADMIN_PASSWORD if role == "admin" else DEFAULT_PASSWORD
        roles_list = _MULTI_ROLES_BY_PRIMARY.get(role, [role])
        user = await _upsert_demo_user(
            db,
            username=username,
            full_name_fa=full_name_fa,
            role=role,
            roles_list=roles_list,
            password=password,
        )

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
                    is_sample_data=True,
                )
                db.add(student)

    for username, full_name_fa, primary_role, extra_roles in EXTRA_SCENARIO_USERS:
        roles_list = [primary_role, *extra_roles]
        await _upsert_demo_user(
            db,
            username=username,
            full_name_fa=full_name_fa,
            role=primary_role,
            roles_list=roles_list,
            password=DEFAULT_PASSWORD,
        )

    for legacy_username in _LEGACY_UNIFIED_USERNAMES:
        result = await db.execute(select(User).where(User.username == legacy_username))
        legacy = result.scalars().first()
        if legacy and legacy.is_active:
            legacy.is_active = False

    await ensure_staff_employees(db, password=DEFAULT_PASSWORD)
    await ensure_operator_named_users(db, password=DEFAULT_PASSWORD)

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
