"""کارمندان دفتر (نقش staff) برای seed دمو — رمز پیش‌فرض: demo123"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.models.operational_models import User

STAFF_DEMO_PASSWORD = "demo123"

# (username, full_name_fa, email)
STAFF_EMPLOYEES: list[tuple[str, str, str]] = [
    ("staff1", "محمد رضایی", "staff1@anistito.ir"),
    ("staff2", "سارا احمدی", "staff2@anistito.ir"),
    ("staff3", "امیر حسینی", "staff3@anistito.ir"),
    ("staff4", "نیلوفر کریمی", "staff4@anistito.ir"),
    ("staff5", "کامران مهدوی", "staff5@anistito.ir"),
    ("staff6", "لیلا نوری", "staff6@anistito.ir"),
    ("staff7", "بهزاد صادقی", "staff7@anistito.ir"),
    ("staff8", "مینا فروتن", "staff8@anistito.ir"),
    ("staff9", "پویان جعفری", "staff9@anistito.ir"),
    ("staff10", "هدی موسوی", "staff10@anistito.ir"),
]


async def ensure_staff_employees(db: AsyncSession, password: str | None = None) -> None:
    """ایجاد یا به‌روزرسانی همهٔ کاربران با نقش staff طبق STAFF_EMPLOYEES."""
    pwd = password if password is not None else STAFF_DEMO_PASSWORD
    h = get_password_hash(pwd)
    for username, full_name_fa, email in STAFF_EMPLOYEES:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        if user:
            user.email = email
            user.full_name_fa = full_name_fa
            user.role = "staff"
            user.hashed_password = h
            user.is_active = True
        else:
            db.add(
                User(
                    id=uuid.uuid4(),
                    username=username,
                    email=email,
                    hashed_password=h,
                    full_name_fa=full_name_fa,
                    role="staff",
                    is_active=True,
                )
            )
            await db.flush()
