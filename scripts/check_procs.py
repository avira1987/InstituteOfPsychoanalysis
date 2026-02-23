import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import async_sessionmaker
from app.models.meta_models import ProcessDefinition

async def main():
    engine = create_async_engine("postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito")
    sess = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sess() as s:
        r = await s.execute(select(ProcessDefinition))
        procs = r.scalars().all()
        print("Count:", len(procs))
        for p in procs[:5]:
            print(p.code, "-", p.name_fa)
    await engine.dispose()

asyncio.run(main())
