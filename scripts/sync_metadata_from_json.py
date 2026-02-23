#!/usr/bin/env python3
"""Sync process and rule definitions from metadata into DB. Adds only missing items."""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.meta_models import ProcessDefinition
from app.meta.seed import load_process, sync_rules

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito")
METADATA_DIR = Path(__file__).resolve().parents[1] / "metadata"
PROCESSES_DIR = METADATA_DIR / "processes"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    if not PROCESSES_DIR.exists():
        logger.error(f"Processes dir not found: {PROCESSES_DIR}")
        return 1

    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # 1. Sync rules first (processes may reference them)
        rules_added = await sync_rules(db)
        await db.commit()

        # 2. Sync processes
        result = await db.execute(select(ProcessDefinition.code))
        existing_codes = set(result.scalars().all())

        processes_added = 0
        for pf in sorted(PROCESSES_DIR.glob("*.json")):
            import json
            with open(pf, "r", encoding="utf-8") as f:
                data = json.load(f)
            code = data.get("process", {}).get("code")
            if not code:
                logger.warning(f"Skipping {pf.name}: no process.code")
                continue
            if code in existing_codes:
                continue
            await load_process(db, pf)
            existing_codes.add(code)
            processes_added += 1

        await db.commit()
        logger.info(f"Sync complete. Added {rules_added} rule(s), {processes_added} process(es).")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
