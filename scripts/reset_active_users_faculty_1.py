#!/usr/bin/env python3
"""
غیرفعال‌سازی همهٔ کاربران فعال غیر از admin، سپس ایجاد اعضای هیئت علمی ۱.

رمز پیش‌فرض: demo123
نقش: faculty_1 (هیئت علمی)

اجرا:
  docker exec -w /app anistito-api python /app/scripts/reset_active_users_faculty_1.py
"""
from __future__ import annotations

import asyncio
import re
import sys
import uuid

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import select

from app.api.auth import get_password_hash
from app.database import async_session_factory
from app.models.operational_models import User

DEFAULT_PASSWORD = "demo123"
ROLE = "faculty_1"

# (username, full_name_fa, role, email) — نام نمایشی با پسوند (هیئت علمی)
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


def _normalize_name(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"^(آقای|خانم|دکتر)\s+", "", s)
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = re.sub(r"\s+", " ", s)
    return s


async def main() -> int:
    pwd_hash = get_password_hash(DEFAULT_PASSWORD)
    keep_usernames = {u for u, _ in FACULTY_1_MEMBERS}

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.is_active.is_(True)))
        active = list(result.scalars().all())

        deactivated = 0
        for user in active:
            if (user.role or "").strip().lower() == "admin":
                continue
            if user.username in keep_usernames:
                continue
            user.is_active = False
            deactivated += 1

        created = 0
        updated = 0
        for username, full_name_fa in FACULTY_1_MEMBERS:
            name = _normalize_name(full_name_fa)
            email = f"{username}@faculty.anistito.local"
            res = await db.execute(select(User).where(User.username == username))
            user = res.scalars().first()
            profile_meta = {
                "faculty_level": 1,
                "faculty_band": "faculty_1",
                "faculty_label_fa": "هیئت علمی",
            }
            if user:
                user.full_name_fa = name
                user.email = email
                user.role = ROLE
                if hasattr(user, "roles"):
                    try:
                        user.roles = [ROLE]
                    except Exception:
                        pass
                user.is_active = True
                user.hashed_password = pwd_hash
                user.portal_password_plain = DEFAULT_PASSWORD
                user.profile_meta = profile_meta
                updated += 1
            else:
                kwargs = dict(
                    id=uuid.uuid4(),
                    username=username,
                    email=email,
                    hashed_password=pwd_hash,
                    portal_password_plain=DEFAULT_PASSWORD,
                    full_name_fa=name,
                    role=ROLE,
                    is_active=True,
                    profile_meta=profile_meta,
                )
                # ستون roles ممکن است هنوز migrate نشده باشد
                try:
                    u = User(**kwargs, roles=[ROLE])
                except TypeError:
                    u = User(**kwargs)
                db.add(u)
                created += 1

        await db.commit()

    print(
        f"done: deactivated={deactivated} faculty_created={created} "
        f"faculty_updated={updated} password={DEFAULT_PASSWORD} role={ROLE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
