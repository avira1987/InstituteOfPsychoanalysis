#!/usr/bin/env python3
"""Replace one process definition in DB from metadata/processes/{code}.json."""
import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.meta.seed import sync_process


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True, help="process code, e.g. introductory_course_registration")
    args = parser.parse_args()

    pf = ROOT / "metadata" / "processes" / f"{args.code}.json"
    if not pf.exists():
        print(f"File not found: {pf}", file=sys.stderr)
        return 1

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito")
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        await sync_process(db, pf)
        await db.commit()
        print(f"Synced process definition: {args.code}")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
