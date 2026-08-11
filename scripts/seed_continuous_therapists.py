#!/usr/bin/env python3
"""
ایجاد/به‌روزرسانی درمانگران پیوسته (نقش therapist).

رمز پیش‌فرض: demo123

اجرا:
  docker exec -w /app -e PYTHONPATH=/app anistito-api python /app/scripts/seed_continuous_therapists.py
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

from app.api.auth import get_password_hash
from app.database import async_session_factory
from app.models.operational_models import User

DEFAULT_PASSWORD = "demo123"
ROLE = "therapist"

# (username, full_name_fa)
CONTINUOUS_THERAPISTS: list[tuple[str, str]] = [
    ("tahereh_yaghoubi", "طاهره یعقوبی"),
    ("fatemeh_shokoofeh", "فاطمه شکوفه"),
    ("fatemeh_alidoosti", "فاطمه علیدوستی"),
    ("sara_khosravi", "سارا خسروی"),
]


def _normalize_name(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"^(آقای|خانم|دکتر)\s+", "", s)
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = re.sub(r"\s+", " ", s)
    return s


async def main() -> int:
    pwd_hash = get_password_hash(DEFAULT_PASSWORD)

    async with async_session_factory() as db:
        created = 0
        updated = 0
        for username, full_name_fa in CONTINUOUS_THERAPISTS:
            name = _normalize_name(full_name_fa)
            email = f"{username}@therapist.anistito.local"
            res = await db.execute(select(User).where(User.username == username))
            user = res.scalars().first()
            profile_meta = {
                "therapist_kind": "continuous",
                "therapist_label_fa": "درمانگر پیوسته",
            }
            if user:
                user.full_name_fa = name
                user.email = email
                user.role = ROLE
                user.roles = [ROLE]
                user.is_active = True
                user.hashed_password = pwd_hash
                user.portal_password_plain = DEFAULT_PASSWORD
                user.profile_meta = profile_meta
                updated += 1
            else:
                db.add(
                    User(
                        id=uuid.uuid4(),
                        username=username,
                        email=email,
                        hashed_password=pwd_hash,
                        portal_password_plain=DEFAULT_PASSWORD,
                        full_name_fa=name,
                        role=ROLE,
                        roles=[ROLE],
                        is_active=True,
                        profile_meta=profile_meta,
                    )
                )
                created += 1

        await db.commit()

    print(
        f"done: therapist_created={created} therapist_updated={updated} "
        f"password={DEFAULT_PASSWORD} role={ROLE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
