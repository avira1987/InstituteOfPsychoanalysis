#!/usr/bin/env python3
"""Create or reset admin user (username=admin, password=admin123). Run: python -m app.create_admin"""
import asyncio
import uuid

from sqlalchemy import select
from app.database import async_session_factory, init_db
from app.models.operational_models import User
from app.api.auth import get_password_hash


async def main():
    print("Ensuring database tables exist...")
    await init_db()
    print("Creating/resetting admin user...")
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        admin = result.scalars().first()

        if admin:
            admin.hashed_password = get_password_hash("admin123")
            admin.is_active = True
            admin.email = admin.email or "admin@anistito.ir"
            admin.full_name_fa = admin.full_name_fa or "مدیر سیستم"
            await db.commit()
            print("Admin UPDATED: username=admin, password=admin123")
        else:
            admin = User(
                id=uuid.uuid4(),
                username="admin",
                email="admin@anistito.ir",
                hashed_password=get_password_hash("admin123"),
                full_name_fa="مدیر سیستم",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            await db.commit()
            print("Admin CREATED: username=admin, password=admin123")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
