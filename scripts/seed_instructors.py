#!/usr/bin/env python3
"""
ایجاد/به‌روزرسانی کاربران با نقش مدرس (instructor).
اگر کاربر با همان نام موجود باشد، دوباره ساخته نمی‌شود؛ فقط نقش اضافه می‌شود.

رمز پیش‌فرض برای کاربران جدید: demo123

اجرا:
  docker exec -w /app -e PYTHONPATH=/app anistito-api python /app/scripts/seed_instructors.py
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
ROLE = "instructor"

# (preferred_username, full_name_fa)
MEMBERS: list[tuple[str, str]] = [
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


def _base_name(name: str) -> str:
    s = (name or "").strip()
    s = s.replace("ي", "ی").replace("ك", "ک")
    # فاصله‌های ترکیبی مثل «پورجبار» / «پور جبار»
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
        " (مدرس)",
        "(مدرس)",
    ):
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _name_keys(name: str) -> set[str]:
    """کلیدهای تطبیق: با/بدون فاصله بین بخش‌های نام."""
    bn = _base_name(name)
    keys = {bn, bn.replace(" ", "")}
    # پور جبار ↔ پورجبار
    keys.add(re.sub(r"پور\s*جبار", "پور جبار", bn))
    keys.add(re.sub(r"پور\s*جبار", "پورجبار", bn))
    return {k for k in keys if k}


async def main() -> int:
    pwd_hash = get_password_hash(DEFAULT_PASSWORD)
    created = 0
    role_added = 0
    already_had = 0

    async with async_session_factory() as db:
        res = await db.execute(select(User))
        all_users = list(res.scalars().all())
        by_key: dict[str, list[User]] = {}
        for u in all_users:
            for k in _name_keys(u.full_name_fa or ""):
                by_key.setdefault(k, []).append(u)

        for preferred_username, full_name_fa in MEMBERS:
            keys = _name_keys(full_name_fa)
            candidates: list[User] = []
            seen_ids: set[str] = set()
            for k in keys:
                for c in by_key.get(k) or []:
                    cid = str(c.id)
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    candidates.append(c)

            user = None
            for c in candidates:
                if c.username == preferred_username:
                    user = c
                    break
            if user is None and candidates:
                # ترجیح حساب غیر‌دانشجو اگر چند حساب هم‌نام باشد (مثل هانیه)
                non_student = [
                    c
                    for c in candidates
                    if c.is_active and (c.role or "") != "student" and "student" not in (c.roles or [])
                ]
                active = [c for c in candidates if c.is_active]
                user = (non_student or active or candidates)[0]

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
                        "member_kind": "instructor",
                        "instructor_label_fa": "مدرس",
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
                if not (user.role or "").strip():
                    user.role = ROLE
                role_added += 1
                print(f"UPDATED {user.username} — added {ROLE}; roles={roles_now}")

            meta = dict(user.profile_meta or {}) if isinstance(user.profile_meta, dict) else {}
            meta.setdefault("member_kind", "instructor")
            meta["instructor_label_fa"] = "مدرس"
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
