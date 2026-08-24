#!/usr/bin/env python3
"""یکپارچه‌سازی شماره/نام کاربری دانشجویان موجود به قالب STU-{n}.

اجرا:
  docker exec -w /app -e PYTHONPATH=/app anistito-api python /app/scripts/unify_student_identity.py
"""
from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import async_session_factory
from app.services.student_identity import unify_existing_student_identities


async def main() -> int:
    async with async_session_factory() as db:
        stats = await unify_existing_student_identities(db)
        await db.commit()
    print(
        "unified: codes={codes} usernames={usernames} scanned={scanned}".format(**stats)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
