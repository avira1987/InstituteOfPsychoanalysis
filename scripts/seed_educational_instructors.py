#!/usr/bin/env python3
"""
ایجاد/به‌روزرسانی کاربران با نقش مدرس آموزشی (educational_instructor).
اگر کاربر با همان نام موجود باشد، دوباره ساخته نمی‌شود؛ فقط نقش اضافه می‌شود.

رمز پیش‌فرض برای کاربران جدید: demo123

اجرا:
  docker exec -w /app -e PYTHONPATH=/app anistito-api python /app/scripts/seed_educational_instructors.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_password_hash
from app.core.user_roles import normalize_roles_list
from app.database import async_session_factory
from app.models.operational_models import User

DEFAULT_PASSWORD = "demo123"
ROLE = "educational_instructor"

# (preferred_username, full_name_fa)
MEMBERS: list[tuple[str, str]] = [
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


def _base_name(name: str) -> str:
    s = (name or "").strip()
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = re.sub(r"^(آقای|خانم|دکتر)\s+", "", s)
    for suf in (
        " (هیئت علمی)",
        "(هیئت علمی)",
        " (درمانگر پیوسته)",
        "(درمانگر پیوسته)",
        " (انترن پیشرفته)",
        "(انترن پیشرفته)",
        " (انترن)",
        "(انترن)",
        " (مدرس آموزشی)",
        "(مدرس آموزشی)",
    ):
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    return re.sub(r"\s+", " ", s)


async def main() -> int:
    pwd_hash = get_password_hash(DEFAULT_PASSWORD)
    created = 0
    role_added = 0
    already_had = 0

    async with async_session_factory() as db:
        res = await db.execute(select(User))
        all_users = list(res.scalars().all())
        by_base: dict[str, list[User]] = {}
        for u in all_users:
            bn = _base_name(u.full_name_fa or "")
            if not bn:
                continue
            by_base.setdefault(bn, []).append(u)

        for preferred_username, full_name_fa in MEMBERS:
            target = _base_name(full_name_fa)
            candidates = by_base.get(target) or []
            # ترجیح: username شناخته‌شده، سپس فعال‌ترین
            user = None
            for c in candidates:
                if c.username == preferred_username:
                    user = c
                    break
            if user is None and candidates:
                active = [c for c in candidates if c.is_active]
                user = (active or candidates)[0]

            if user is None:
                email = f"{preferred_username}@instructor.anistito.local"
                user = User(
                    id=uuid.uuid4(),
                    username=preferred_username,
                    email=email,
                    hashed_password=pwd_hash,
                    portal_password_plain=DEFAULT_PASSWORD,
                    full_name_fa=full_name_fa,
                    role=ROLE,
                    roles=[ROLE],
                    is_active=True,
                    profile_meta={
                        "member_kind": "educational_instructor",
                        "instructor_label_fa": "مدرس آموزشی",
                    },
                )
                db.add(user)
                created += 1
                print(f"CREATED {preferred_username} — {full_name_fa} role={ROLE}")
                continue

            roles_now = normalize_roles_list(user.roles, primary=user.role)
            if ROLE in roles_now:
                already_had += 1
                print(f"EXISTS  {user.username} — already has {ROLE}")
            else:
                roles_now.append(ROLE)
                user.roles = roles_now
                # primary را عوض نکن اگر از قبل نقش دیگری دارد
                if not (user.role or "").strip():
                    user.role = ROLE
                role_added += 1
                print(f"UPDATED {user.username} — added {ROLE}; roles={roles_now}")

            meta = dict(user.profile_meta or {}) if isinstance(user.profile_meta, dict) else {}
            meta["member_kind"] = "educational_instructor"
            meta["instructor_label_fa"] = "مدرس آموزشی"
            user.profile_meta = meta
            flag_modified(user, "profile_meta")
            user.is_active = True

        await db.commit()

    print(
        f"done: created={created} role_added={role_added} "
        f"already_had={already_had} password={DEFAULT_PASSWORD} role={ROLE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
