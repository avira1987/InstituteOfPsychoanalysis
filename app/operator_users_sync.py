"""استخراج و upsert کاربران اپراتوری (بدون دانشجویان دمو)."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_password_hash
from app.core.user_roles import apply_roles_to_user, normalize_roles_list
from app.meta.role_labels import role_labels_map
from app.models.operational_models import User

DEFAULT_PASSWORD = "demo123"

# پیشوند/الگوی نام کاربری دانشجویان دمو — از همگام‌سازی اپراتور حذف می‌شوند
_STUDENT_DEMO_USERNAME_RE = re.compile(
    r"^(AUTO-DEMO-|DEMO-SCEN-|DEMO-OP-|DEMO-ROLE-STUDENT-|regdemo_|AUTO-PROFILE-)",
    re.I,
)
_STUDENT_SUFFIX_RE = re.compile(r"_stu$", re.I)

_PURE_NON_OPERATOR = frozenset({"student", "applicant", "system"})

# نقش‌هایی که باید حداقل یک کاربر فعال داشته باشند (کاتالوگ منهای assigned ترکیبی و system)
_SKIP_COVERAGE_ROLES = frozenset({
    "system",
    "applicant",
    "student",
    "teaching_assistant_or_instructor",
    # aliasهای ادغام‌شده — پوشش از حساب واحد
    "progress_committee_project",
    "progress_committee_scientific",
    "monitoring_committee_officer",
    "therapy_committee_executor",
    "course_committee_executive",
    "course_committee_scientific",
    "scientific_officer_course_committee",
    "deputy_education_director",
    "admissions_officer",  # demo_admissions
})


def is_student_demo_username(username: str | None) -> bool:
    u = (username or "").strip()
    if not u:
        return True
    if _STUDENT_DEMO_USERNAME_RE.match(u):
        return True
    if _STUDENT_SUFFIX_RE.search(u):
        return True
    return False


def is_operator_user(user: Any) -> bool:
    """کاربر پرسنل/کمیته/مدرس — نه دانشجو/متقاضی خالص دمو."""
    if user is None or not getattr(user, "is_active", False):
        return False
    username = getattr(user, "username", None) or ""
    if is_student_demo_username(username):
        return False
    roles = set(normalize_roles_list(getattr(user, "roles", None), primary=getattr(user, "role", None)))
    if not roles:
        return False
    if roles <= _PURE_NON_OPERATOR:
        return False
    return True


def user_to_operator_payload(user: User) -> dict[str, Any]:
    roles = normalize_roles_list(user.roles, primary=user.role)
    meta = user.profile_meta if isinstance(user.profile_meta, dict) else None
    return {
        "username": user.username,
        "email": user.email,
        "full_name_fa": user.full_name_fa,
        "role": user.role,
        "roles": roles,
        "phone": user.phone,
        "is_active": bool(user.is_active),
        "profile_meta": meta,
        "hashed_password": user.hashed_password,
    }


async def list_operator_payloads(db: AsyncSession) -> list[dict[str, Any]]:
    result = await db.execute(select(User).where(User.is_active.is_(True)))
    users = [u for u in result.scalars().all() if is_operator_user(u)]
    users.sort(key=lambda u: (u.username or ""))
    return [user_to_operator_payload(u) for u in users]


def operator_roles_covered(payloads: list[dict[str, Any]]) -> set[str]:
    covered: set[str] = set()
    for p in payloads:
        covered.update(normalize_roles_list(p.get("roles"), primary=p.get("role")))
    return covered


def roles_missing_coverage(payloads: list[dict[str, Any]]) -> list[str]:
    known = set(role_labels_map().keys()) - _SKIP_COVERAGE_ROLES
    covered = operator_roles_covered(payloads)
    # internal_manager covered by dakheli1; faculty_1 by named users
    return sorted(r for r in known if r not in covered)


async def upsert_operator_from_payload(
    db: AsyncSession,
    payload: dict[str, Any],
    *,
    keep_existing_password: bool = True,
    default_password: str = DEFAULT_PASSWORD,
) -> str:
    """
    ایجاد یا به‌روزرسانی یک اپراتور.
    خروجی: created | updated | unchanged
    """
    username = (payload.get("username") or "").strip()
    if not username:
        raise ValueError("username required")
    roles_list = normalize_roles_list(payload.get("roles"), primary=payload.get("role"))
    if not roles_list:
        raise ValueError(f"roles empty for {username}")
    primary = (payload.get("role") or roles_list[0]).strip()

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if user is None:
        hashed = payload.get("hashed_password") or get_password_hash(default_password)
        user = User(
            id=uuid.uuid4(),
            username=username,
            email=payload.get("email"),
            hashed_password=hashed,
            portal_password_plain=None,
            full_name_fa=payload.get("full_name_fa"),
            phone=payload.get("phone"),
            is_active=bool(payload.get("is_active", True)),
            profile_meta=payload.get("profile_meta") if isinstance(payload.get("profile_meta"), dict) else {},
        )
        apply_roles_to_user(user, roles_list, primary=primary)
        db.add(user)
        await db.flush()
        return "created"

    changed = False
    before_roles = normalize_roles_list(user.roles, primary=user.role)
    before_primary = user.role
    apply_roles_to_user(user, roles_list, primary=primary)
    if before_roles != normalize_roles_list(user.roles, primary=user.role) or before_primary != user.role:
        changed = True
    for attr, key in (
        ("full_name_fa", "full_name_fa"),
        ("email", "email"),
        ("phone", "phone"),
    ):
        new_val = payload.get(key)
        if new_val is not None and getattr(user, attr) != new_val:
            setattr(user, attr, new_val)
            changed = True
    if bool(payload.get("is_active", True)) != bool(user.is_active):
        user.is_active = bool(payload.get("is_active", True))
        changed = True
    meta = payload.get("profile_meta")
    if isinstance(meta, dict) and meta != (user.profile_meta or {}):
        user.profile_meta = meta
        flag_modified(user, "profile_meta")
        changed = True

    if not keep_existing_password:
        user.hashed_password = payload.get("hashed_password") or get_password_hash(default_password)
        user.portal_password_plain = None
        changed = True

    return "updated" if changed else "unchanged"


async def upsert_operators_from_payloads(
    db: AsyncSession,
    payloads: list[dict[str, Any]],
    *,
    keep_existing_password: bool = True,
    default_password: str = DEFAULT_PASSWORD,
) -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {
        "created": [],
        "updated": [],
        "unchanged": [],
        "skipped_password": [],
    }
    for p in payloads:
        status = await upsert_operator_from_payload(
            db,
            p,
            keep_existing_password=keep_existing_password,
            default_password=default_password,
        )
        summary[status].append(p["username"])
        if status in ("updated", "unchanged") and keep_existing_password:
            summary["skipped_password"].append(p["username"])
    await db.commit()
    return summary


def payloads_to_json(payloads: list[dict[str, Any]]) -> str:
    return json.dumps(payloads, ensure_ascii=False, indent=2)


def payloads_from_json(raw: str) -> list[dict[str, Any]]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("payload must be a JSON array")
    return data
