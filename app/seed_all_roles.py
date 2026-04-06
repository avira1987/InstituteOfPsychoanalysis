#!/usr/bin/env python3

"""

Seed one demo user per supported role (+ کاربران سناریو: demo_interviewer و ...).



Passwords:

- admin: admin123

- others: demo123

"""



import asyncio

import os

import sys



from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine



# Ensure `/app` is on sys.path inside Docker so `import app.*` works.

_this_dir = os.path.dirname(os.path.abspath(__file__))

_repo_root = os.path.dirname(_this_dir)

if _repo_root not in sys.path:

    sys.path.insert(0, _repo_root)





async def main() -> int:

    try:

        from app.config import get_settings



        database_url = os.getenv("DATABASE_URL") or get_settings().DATABASE_URL

    except Exception:

        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito")



    print("Connecting to database...")

    engine = create_async_engine(database_url)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)



    async with session_factory() as db:

        try:

            await db.execute(text("SELECT 1 FROM users LIMIT 1"))

        except Exception as e:

            print(f"Error: users table may not exist. Run alembic upgrade head first. {e}")

            await engine.dispose()

            return 1



        from app.demo_role_users import ensure_demo_role_users



        await ensure_demo_role_users(db)



    await engine.dispose()



    print("\n" + "=" * 60)

    print("Demo credentials: admin / admin123 | other roles / demo123")

    print("Scenario actors: demo_interviewer, demo_admissions, demo_applicant (demo123)")

    print("=" * 60)

    return 0





if __name__ == "__main__":

    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):

        try:

            sys.stdout.reconfigure(encoding="utf-8")

        except Exception:

            pass

    raise SystemExit(asyncio.run(main()))

