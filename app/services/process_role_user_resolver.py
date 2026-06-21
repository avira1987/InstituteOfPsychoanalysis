"""Map process metadata assigned_role codes to portal User.role values."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import User

# Metadata assigned_role → portal User.role search order
_METADATA_TO_PORTAL_ROLES: dict[str, tuple[str, ...]] = {
    "course_committee_executive": ("deputy_education",),
    "deputy_education_director": ("deputy_education",),
    "scientific_officer_course_committee": ("deputy_education", "staff"),
    "admissions_officer": ("staff", "site_manager", "deputy_education"),
    "site_manager": ("site_manager",),
    "staff": ("staff",),
    "deputy_education": ("deputy_education",),
    "admin": ("admin",),
    "monitoring_committee_officer": ("monitoring_committee_officer",),
    "therapy_committee_chair": ("therapy_committee_chair",),
    "therapy_committee_executor": ("therapy_committee_executor",),
}


def portal_roles_for_assigned_role(assigned_role: str) -> tuple[str, ...]:
    role = (assigned_role or "").strip().lower()
    if not role:
        return ()
    if role in _METADATA_TO_PORTAL_ROLES:
        return _METADATA_TO_PORTAL_ROLES[role]
    return (role,)


async def resolve_users_for_assigned_role(
    db: AsyncSession,
    assigned_role: str,
    *,
    limit: int | None = None,
) -> list[User]:
    """All active users matching a metadata assigned_role (via portal role mapping)."""
    roles = portal_roles_for_assigned_role(assigned_role)
    if not roles:
        return []
    seen: set = set()
    out: list[User] = []
    for pr in roles:
        stmt = select(User).where(User.role == pr, User.is_active.is_(True)).order_by(User.full_name_fa.asc())
        if limit is not None:
            stmt = stmt.limit(max(0, limit - len(out)))
        for u in (await db.execute(stmt)).scalars().all():
            if u.id in seen:
                continue
            seen.add(u.id)
            out.append(u)
            if limit is not None and len(out) >= limit:
                return out
    return out


async def resolve_first_user_for_assigned_role(
    db: AsyncSession,
    assigned_role: str,
) -> User | None:
    users = await resolve_users_for_assigned_role(db, assigned_role, limit=1)
    return users[0] if users else None


async def resolve_contact_for_assigned_role(
    db: AsyncSession,
    assigned_role: str,
) -> str | None:
    user = await resolve_first_user_for_assigned_role(db, assigned_role)
    if not user:
        return None
    return (user.phone or user.email or "").strip() or None


def iter_unique_contacts(users: Iterable[User]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in users:
        c = (u.phone or u.email or "").strip()
        if not c or c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out
