#!/usr/bin/env python3
"""
ساخت کاربران برای نقش‌های کمیته‌ای که هنوز کاربر فعال ندارند.
رمز پیش‌فرض: demo123

حساب‌های واحد:
  - progress_committee1 ← پیشرفت + پروژه + علمی
  - supervision_committee1 ← نظارت + مسئول علمی اجرایی
  - therapy_committee_chair1 ← مسئول پروژه + مجری کمیته درمان
  - course_committee1 ← اجرایی + علمی کمیته دروس

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

# نقش‌هایی که هنوز جدا ساخته می‌شوند (ادغام‌شده‌ها این‌جا نیستند)
COMMITTEE_ROLES: list[tuple[str, str]] = [
    ("specialized_commission", "کاربر کمیسیون تخصصی"),
    ("education_committee", "کاربر کمیته آموزش"),
]

UNIFIED_ACCOUNTS: list[dict] = [
    {
        "username": "progress_committee1",
        "primary": "progress_committee",
        "roles": [
            "progress_committee",
            "progress_committee_project",
            "progress_committee_scientific",
        ],
        "full_name": "کاربر کمیته پیشرفت",
        "legacy": (
            "progress_committee_project1",
            "progress_committee_scientific1",
        ),
        "meta_key": "unified_progress",
    },
    {
        "username": "supervision_committee1",
        "primary": "supervision_committee",
        "roles": [
            "supervision_committee",
            "monitoring_committee_officer",
        ],
        "full_name": "کاربر کمیته نظارت",
        "legacy": ("monitoring_committee_officer1",),
        "meta_key": "unified_supervision",
    },
    {
        "username": "therapy_committee_chair1",
        "primary": "therapy_committee_chair",
        "roles": [
            "therapy_committee_chair",
            "therapy_committee_executor",
        ],
        "full_name": "کاربر کمیته درمان",
        "legacy": ("therapy_committee_executor1",),
        "meta_key": "unified_therapy",
    },
    {
        "username": "course_committee1",
        "primary": "course_committee",
        "roles": [
            "course_committee",
            "course_committee_executive",
            "scientific_officer_course_committee",
            "course_committee_scientific",
        ],
        "full_name": "کاربر کمیته دروس",
        "legacy": (
            "course_committee_executive1",
            "scientific_officer_course_committee1",
            "course_committee_scientific1",
        ),
        "meta_key": "unified_course_committee",
    },
]


def _active_role_codes(users: list[User]) -> set[str]:
    out: set[str] = set()
    for u in users:
        if not u.is_active:
            continue
        out.update(normalize_roles_list(u.roles, primary=u.role))
    return out


def _ensure_unified_account(
    db,
    users: list[User],
    pwd_hash: str,
    cfg: dict,
    created: list[tuple[str, str, str]],
    reactivated: list[tuple[str, str, str]],
) -> None:
    username = cfg["username"]
    primary = cfg["primary"]
    roles = list(cfg["roles"])
    full_name = cfg["full_name"]
    email = f"{username}@committee.anistito.local"
    existing = next((u for u in users if u.username == username), None)
    if existing:
        apply_roles_to_user(existing, roles, primary=primary)
        existing.is_active = True
        existing.full_name_fa = full_name
        existing.hashed_password = pwd_hash
        existing.portal_password_plain = DEFAULT_PASSWORD
        existing.email = existing.email or email
        meta = dict(existing.profile_meta or {})
        meta[cfg["meta_key"]] = True
        meta["committee_roles"] = roles
        existing.profile_meta = meta
        reactivated.append((username, full_name, "+".join(roles)))
    else:
        db.add(
            User(
                id=uuid.uuid4(),
                username=username,
                email=email,
                hashed_password=pwd_hash,
                portal_password_plain=DEFAULT_PASSWORD,
                full_name_fa=full_name,
                role=primary,
                roles=roles,
                is_active=True,
                profile_meta={
                    "committee_role": primary,
                    cfg["meta_key"]: True,
                    "committee_roles": roles,
                },
            )
        )
        created.append((username, full_name, "+".join(roles)))

    for uname in cfg["legacy"]:
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

        for cfg in UNIFIED_ACCOUNTS:
            _ensure_unified_account(db, users, pwd_hash, cfg, created, reactivated)

        assigned = _active_role_codes(users)
        for cfg in UNIFIED_ACCOUNTS:
            assigned.update(cfg["roles"])

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

    print("=== UNIFIED ACCOUNTS ===")
    for cfg in UNIFIED_ACCOUNTS:
        print(f"{cfg['username']}\t{DEFAULT_PASSWORD}\t{','.join(cfg['roles'])}")
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
