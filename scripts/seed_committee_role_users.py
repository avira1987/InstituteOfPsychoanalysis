#!/usr/bin/env python3
"""
ساخت کاربران برای نقش‌های کمیته‌ای که هنوز کاربر فعال ندارند.
رمز پیش‌فرض: demo123

کمیته پیشرفت + پروژه + علمی → یک حساب واحد: progress_committee1

اجرا:
  docker exec -w /app -e PYTHONPATH=/app anistito-api python /app/scripts/seed_committee_role_users.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select

from app.api.auth import get_password_hash
from app.core.user_roles import apply_roles_to_user, normalize_roles_list
from app.database import async_session_factory
from app.meta.role_labels import role_labels_map
from app.models.operational_models import User

DEFAULT_PASSWORD = "demo123"

# نقش‌هایی که عنوانشان به کمیته/کمیسیون مربوط است
# (پیشرفت پروژه/علمی جدا ساخته نمی‌شوند — در UNIFIED_PROGRESS ادغام‌اند)
COMMITTEE_ROLES: list[tuple[str, str]] = [
    ("supervision_committee", "کاربر کمیته نظارت"),
    ("specialized_commission", "کاربر کمیسیون تخصصی"),
    ("therapy_committee_chair", "مسئول پروژه کمیته درمان"),
    ("therapy_committee_executor", "مجری کمیته درمان"),
    ("monitoring_committee_officer", "مسئول علمی اجرایی کمیته نظارت"),
    ("course_committee_executive", "مسئول اجرایی کمیته دروس"),
    ("scientific_officer_course_committee", "مسئول علمی کمیته دروس (کد فرایند)"),
    ("education_committee", "کاربر کمیته آموزش"),
    ("course_committee", "کاربر کمیته دروس"),
    ("course_committee_scientific", "مسئول علمی کمیته دروس"),
]

UNIFIED_PROGRESS_ROLES = [
    "progress_committee",
    "progress_committee_project",
    "progress_committee_scientific",
]
UNIFIED_PROGRESS_USERNAME = "progress_committee1"
LEGACY_PROGRESS_USERNAMES = (
    "progress_committee_project1",
    "progress_committee_scientific1",
)


def _active_role_codes(users: list[User]) -> set[str]:
    out: set[str] = set()
    for u in users:
        if not u.is_active:
            continue
        out.update(normalize_roles_list(u.roles, primary=u.role))
    return out


def _ensure_unified_progress(
    db,
    users: list[User],
    pwd_hash: str,
    created: list[tuple[str, str, str]],
    reactivated: list[tuple[str, str, str]],
) -> None:
    full_name = "کاربر کمیته پیشرفت"
    email = f"{UNIFIED_PROGRESS_USERNAME}@committee.anistito.local"
    existing = next((u for u in users if u.username == UNIFIED_PROGRESS_USERNAME), None)
    if existing:
        apply_roles_to_user(existing, UNIFIED_PROGRESS_ROLES, primary="progress_committee")
        existing.is_active = True
        existing.full_name_fa = full_name
        existing.hashed_password = pwd_hash
        existing.portal_password_plain = DEFAULT_PASSWORD
        existing.email = existing.email or email
        meta = dict(existing.profile_meta or {})
        meta["unified_progress"] = True
        meta["committee_roles"] = list(UNIFIED_PROGRESS_ROLES)
        existing.profile_meta = meta
        reactivated.append((UNIFIED_PROGRESS_USERNAME, full_name, "+".join(UNIFIED_PROGRESS_ROLES)))
    else:
        db.add(
            User(
                id=uuid.uuid4(),
                username=UNIFIED_PROGRESS_USERNAME,
                email=email,
                hashed_password=pwd_hash,
                portal_password_plain=DEFAULT_PASSWORD,
                full_name_fa=full_name,
                role="progress_committee",
                roles=list(UNIFIED_PROGRESS_ROLES),
                is_active=True,
                profile_meta={
                    "committee_role": "progress_committee",
                    "unified_progress": True,
                    "committee_roles": list(UNIFIED_PROGRESS_ROLES),
                },
            )
        )
        created.append((UNIFIED_PROGRESS_USERNAME, full_name, "+".join(UNIFIED_PROGRESS_ROLES)))

    for uname in LEGACY_PROGRESS_USERNAMES:
        legacy = next((u for u in users if u.username == uname), None)
        if legacy and legacy.is_active:
            legacy.is_active = False


async def main() -> int:
    labels = role_labels_map()
    pwd_hash = get_password_hash(DEFAULT_PASSWORD)
    created: list[tuple[str, str, str]] = []
    reactivated: list[tuple[str, str, str]] = []
    skipped: list[tuple[str, str]] = []

    async with async_session_factory() as db:
        res = await db.execute(select(User))
        users = list(res.scalars().all())

        _ensure_unified_progress(db, users, pwd_hash, created, reactivated)

        assigned = _active_role_codes(users)
        assigned.update(UNIFIED_PROGRESS_ROLES)

        for role, default_name in COMMITTEE_ROLES:
            label = labels.get(role, default_name)
            if role in assigned:
                skipped.append((role, label))
                continue

            username = f"{role}1"
            email = f"{username}@committee.anistito.local"
            full_name = default_name

            existing = next((u for u in users if u.username == username), None)
            if existing:
                existing.role = role
                existing.roles = [role]
                existing.is_active = True
                existing.full_name_fa = full_name
                existing.hashed_password = pwd_hash
                existing.portal_password_plain = DEFAULT_PASSWORD
                existing.email = existing.email or email
                reactivated.append((username, full_name, role))
            else:
                db.add(
                    User(
                        id=uuid.uuid4(),
                        username=username,
                        email=email,
                        hashed_password=pwd_hash,
                        portal_password_plain=DEFAULT_PASSWORD,
                        full_name_fa=full_name,
                        role=role,
                        roles=[role],
                        is_active=True,
                        profile_meta={"committee_role": role, "label_fa": label},
                    )
                )
                created.append((username, full_name, role))

        await db.commit()

    print("=== UNIFIED PROGRESS ===")
    print(f"{UNIFIED_PROGRESS_USERNAME}\t{DEFAULT_PASSWORD}\t{','.join(UNIFIED_PROGRESS_ROLES)}")
    print("=== CREATED ===")
    for u, n, r in created:
        print(f"{u}\t{DEFAULT_PASSWORD}\t{n}\t{r}\t{labels.get(r, r)}")
    print("=== REACTIVATED/UPDATED ===")
    for u, n, r in reactivated:
        print(f"{u}\t{DEFAULT_PASSWORD}\t{n}\t{r}\t{labels.get(r, r)}")
    print("=== SKIPPED (already assigned to an active user) ===")
    for r, label in skipped:
        print(f"{r}\t{label}")
    print(
        f"done: created={len(created)} reactivated={len(reactivated)} "
        f"skipped={len(skipped)} password={DEFAULT_PASSWORD}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
