#!/usr/bin/env python3
"""Create or reset admin user (username=admin, password=admin123)."""
import asyncio
import os
import sys
import uuid

# Add project root to path
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Use same DATABASE_URL as Docker or .env
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito"
)
# For Docker: postgresql+asyncpg://anistito:anistito@db:5432/anistito


def get_password_hash(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def main():
    print("Connecting to database...")
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # Check if users table exists
        try:
            r = await db.execute(text("SELECT 1 FROM users LIMIT 1"))
            r.scalar()
        except Exception as e:
            print(f"Error: users table may not exist. Run alembic upgrade head first. {e}")
            await engine.dispose()
            return 1

        # Check if admin exists
        from app.models.operational_models import User

        result = await db.execute(select(User).where(User.username == "admin"))
        admin = result.scalars().first()

        if admin:
            # Update password
            admin.hashed_password = get_password_hash("admin123")
            admin.is_active = True
            admin.email = admin.email or "admin@anistito.ir"
            admin.full_name_fa = admin.full_name_fa or "مدیر سیستم"
            await db.commit()
            print("Admin user UPDATED: username=admin, password=admin123")
        else:
            # Create new admin
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
            print("Admin user CREATED: username=admin, password=admin123")

    await engine.dispose()
    print("Done.")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
