"""کاربران نام‌دار اپراتوری (هیئت علمی / مدرس / مدرس آموزشی) بدون غیرفعال‌سازی دیگران."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_password_hash
from app.core.user_roles import apply_roles_to_user, normalize_roles_list
from app.models.operational_models import User

DEFAULT_PASSWORD = "demo123"

FACULTY_1_MEMBERS: list[tuple[str, str]] = [
    ("edris_salehi", "ادریس صالحی (هیئت علمی)"),
    ("asra_sharifi", "اسرا شریفی (هیئت علمی)"),
    ("akram_jafarian", "اکرم جعفریان (هیئت علمی)"),
    ("zahra_rashvand", "زهرا رشوند (هیئت علمی)"),
    ("mobina_manzarian", "مبینا منظریان (هیئت علمی)"),
    ("hanieh_pourjabar", "هانیه پور جبار (هیئت علمی)"),
    ("fatemeh_mojtahedzadeh", "فاطمه مجتهدزاده (هیئت علمی)"),
    ("fariba_hatami", "فریبا حاتمی (هیئت علمی)"),
    ("shervin_ghaysar", "شروین قیصر (هیئت علمی)"),
    ("ali_alavi", "علی علوی (هیئت علمی)"),
    ("sara_taravati", "سارا طراوتی (هیئت علمی)"),
    ("peymaneh_bahrami", "پیمانه بهرامی (هیئت علمی)"),
    ("zohreh_karimi", "زهره کریمی (هیئت علمی)"),
]

INSTRUCTOR_MEMBERS: list[tuple[str, str]] = [
    ("zahra_rashvand", "زهرا رشوند"),
    ("asra_sharifi", "اسرا شریفی"),
    ("raheleh_nobakht", "راحله نوبخت"),
    ("fariba_hatami", "فریبا حاتمی"),
    ("hanieh_pourjabar", "هانیه پور جبار"),
    ("parisa_roshan", "پریسا روشن"),
    ("peymaneh_bahrami", "پیمانه بهرامی"),
    ("zahra_gharavi", "زهرا غروی"),
    ("mobina_manzarian", "مبینا منظریان"),
]

EDUCATIONAL_INSTRUCTOR_MEMBERS: list[tuple[str, str]] = [
    ("edris_salehi", "ادریس صالحی"),
    ("zohreh_karimi", "زهره کریمی"),
    ("sara_taravati", "سارا طراوتی"),
    ("omid_sina", "امید سینا"),
    ("ali_alavi", "علی علوی"),
    ("fatemeh_mojtahedzadeh", "فاطمه مجتهدزاده"),
    ("yasaman_ekrami", "یاسمن اکرامی"),
    ("sara_khosravi", "سارا خسروی"),
    ("elnaz_bahmanzad", "الناز بهمن زاد"),
]


def _normalize_name(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"^(آقای|خانم|دکتر)\s+", "", s)
    s = s.replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", s)


async def _ensure_user_has_role(
    db: AsyncSession,
    *,
    username: str,
    full_name_fa: str,
    add_role: str,
    password: str,
    email_domain: str,
    profile_meta: dict | None = None,
    force_primary: bool = False,
) -> User:
    """ایجاد کاربر یا افزودن نقش به حساب موجود؛ رمز دمو برای حساب‌های seed."""
    email = f"{username}@{email_domain}"
    pwd_hash = get_password_hash(password)
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if user is None:
        user = User(
            id=uuid.uuid4(),
            username=username,
            email=email,
            hashed_password=pwd_hash,
            portal_password_plain=None,
            full_name_fa=full_name_fa,
            is_active=True,
            profile_meta=profile_meta or {},
        )
        apply_roles_to_user(user, [add_role], primary=add_role)
        db.add(user)
        await db.flush()
        return user

    roles_now = normalize_roles_list(user.roles, primary=user.role)
    if add_role not in roles_now:
        roles_now.append(add_role)
    if force_primary or not user.role or user.role in ("student", "applicant"):
        primary = add_role
    elif "faculty_1" in roles_now:
        primary = "faculty_1"
    else:
        primary = user.role if user.role in roles_now else add_role
    apply_roles_to_user(user, roles_now, primary=primary)
    user.full_name_fa = full_name_fa or user.full_name_fa
    user.is_active = True
    user.hashed_password = pwd_hash
    user.portal_password_plain = None
    if not user.email:
        user.email = email
    if profile_meta:
        meta = dict(user.profile_meta or {})
        meta.update(profile_meta)
        user.profile_meta = meta
        flag_modified(user, "profile_meta")
    return user


async def ensure_faculty_1_users(db: AsyncSession, *, password: str = DEFAULT_PASSWORD) -> None:
    for username, full_name_fa in FACULTY_1_MEMBERS:
        await _ensure_user_has_role(
            db,
            username=username,
            full_name_fa=_normalize_name(full_name_fa),
            add_role="faculty_1",
            password=password,
            email_domain="faculty.anistito.local",
            profile_meta={
                "faculty_level": 1,
                "faculty_band": "faculty_1",
                "faculty_label_fa": "هیئت علمی",
            },
            force_primary=True,
        )


async def ensure_instructor_users(db: AsyncSession, *, password: str = DEFAULT_PASSWORD) -> None:
    for username, full_name_fa in INSTRUCTOR_MEMBERS:
        await _ensure_user_has_role(
            db,
            username=username,
            full_name_fa=full_name_fa,
            add_role="instructor",
            password=password,
            email_domain="instructor.anistito.local",
            profile_meta={
                "member_kind": "instructor",
                "instructor_label_fa": "مدرس",
            },
            force_primary=False,
        )


async def ensure_educational_instructor_users(
    db: AsyncSession, *, password: str = DEFAULT_PASSWORD
) -> None:
    for username, full_name_fa in EDUCATIONAL_INSTRUCTOR_MEMBERS:
        await _ensure_user_has_role(
            db,
            username=username,
            full_name_fa=full_name_fa,
            add_role="educational_instructor",
            password=password,
            email_domain="instructor.anistito.local",
            profile_meta={
                "member_kind": "educational_instructor",
                "instructor_label_fa": "مدرس آموزشی",
            },
            force_primary=False,
        )


async def ensure_operator_named_users(
    db: AsyncSession, *, password: str = DEFAULT_PASSWORD
) -> None:
    """همهٔ کاربران نام‌دار اپراتوری (غیرمخرب — بدون deactivate)."""
    await ensure_faculty_1_users(db, password=password)
    await ensure_instructor_users(db, password=password)
    await ensure_educational_instructor_users(db, password=password)
