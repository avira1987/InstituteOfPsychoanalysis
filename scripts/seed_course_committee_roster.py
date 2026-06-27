#!/usr/bin/env python3
"""ایجاد/به‌روزرسانی کاربران مدرس و کمک‌مدرس از metadata/course_committee_roster.json (idempotent)."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
ROSTER_PATH = ROOT / "metadata" / "course_committee_roster.json"
DEFAULT_PASSWORD = "demo123"


def _email_for_username(username: str) -> str:
    return f"{username}@course-committee.anistito.local"


async def seed_course_committee_roster() -> dict:
    from sqlalchemy import select

    from app.api.auth import get_password_hash
    from app.database import async_session_factory
    from app.models.operational_models import User

    with ROSTER_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    created = 0
    updated = 0

    async with async_session_factory() as db:
        for track in data.get("tracks") or []:
            if not isinstance(track, dict):
                continue
            track_code = track.get("code")
            if not track_code:
                continue

            members: list[dict] = []
            edu = track.get("educational_instructor")
            if isinstance(edu, dict):
                members.append(edu)
            members.extend(track.get("instructors") or [])
            members.extend(track.get("teaching_assistants") or [])

            for entry in members:
                if not isinstance(entry, dict):
                    continue
                roster_key = (entry.get("roster_key") or "").strip()
                name_fa = (entry.get("name_fa") or "").strip()
                member_kind = entry.get("member_kind") or "instructor"
                tier = entry.get("tier")
                if not roster_key or not name_fa:
                    continue

                username = f"cc_{track_code}_{roster_key}"
                role = "instructor" if member_kind == "instructor" else "teaching_assistant"
                profile_meta = {
                    "course_committee_tracks": [track_code],
                    "member_kind": member_kind,
                    "tier": tier,
                    "roster_key": roster_key,
                }

                result = await db.execute(select(User).where(User.username == username))
                user = result.scalars().first()
                pwd_hash = get_password_hash(DEFAULT_PASSWORD)

                if user:
                    user.full_name_fa = name_fa
                    user.role = role
                    user.email = _email_for_username(username)
                    user.profile_meta = profile_meta
                    user.is_active = True
                    if not user.portal_password_plain:
                        user.hashed_password = pwd_hash
                        user.portal_password_plain = DEFAULT_PASSWORD
                    updated += 1
                else:
                    user = User(
                        id=uuid.uuid4(),
                        username=username,
                        email=_email_for_username(username),
                        hashed_password=pwd_hash,
                        portal_password_plain=DEFAULT_PASSWORD,
                        full_name_fa=name_fa,
                        role=role,
                        is_active=True,
                        profile_meta=profile_meta,
                    )
                    db.add(user)
                    created += 1

        await db.commit()

    return {"created": created, "updated": updated}


def main() -> None:
    stats = asyncio.run(seed_course_committee_roster())
    print(f"course_committee_roster seed: created={stats['created']} updated={stats['updated']}")


if __name__ == "__main__":
    main()
