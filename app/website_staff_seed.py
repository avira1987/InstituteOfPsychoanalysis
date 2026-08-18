"""کارمندان دفتر و مدیر داخلی برای seed دمو — رمز پیش‌فرض: demo123"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.core.user_roles import apply_roles_to_user
from app.models.operational_models import User

STAFF_DEMO_PASSWORD = "demo123"

# (username, full_name_fa, email, primary_role, roles)
STAFF_EMPLOYEES: list[tuple[str, str, str, str, list[str]]] = [
    ("dakheli1", "مدیر داخلی", "dakheli1@anistito.ir", "internal_manager", ["internal_manager"]),
    ("staff1", "محمد رضایی", "staff1@anistito.ir", "staff", ["staff"]),
    ("staff2", "سارا احمدی", "staff2@anistito.ir", "staff", ["staff"]),
    ("staff3", "امیر حسینی", "staff3@anistito.ir", "staff", ["staff"]),
    ("staff4", "نیلوفر کریمی", "staff4@anistito.ir", "staff", ["staff"]),
    ("staff5", "کامران مهدوی", "staff5@anistito.ir", "staff", ["staff"]),
    ("staff6", "لیلا نوری", "staff6@anistito.ir", "staff", ["staff"]),
    ("staff7", "بهزاد صادقی", "staff7@anistito.ir", "staff", ["staff"]),
    ("staff8", "مینا فروتن", "staff8@anistito.ir", "staff", ["staff"]),
    ("staff9", "پویان جعفری", "staff9@anistito.ir", "staff", ["staff"]),
    ("staff10", "هدی موسوی", "staff10@anistito.ir", "staff", ["staff"]),
]


async def ensure_staff_employees(db: AsyncSession, password: str | None = None) -> None:
    """ایجاد یا به‌روزرسانی کارمندان دفتر؛ dakheli1 = مدیر داخلی (+ staff)."""
    pwd = password if password is not None else STAFF_DEMO_PASSWORD
    h = get_password_hash(pwd)
    for username, full_name_fa, email, primary_role, roles in STAFF_EMPLOYEES:
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalars().first()
        if user:
            user.email = email
            user.full_name_fa = full_name_fa
            user.hashed_password = h
            user.is_active = True
            apply_roles_to_user(user, roles, primary=primary_role)
        else:
            user = User(
                id=uuid.uuid4(),
                username=username,
                email=email,
                hashed_password=h,
                full_name_fa=full_name_fa,
                is_active=True,
            )
            apply_roles_to_user(user, roles, primary=primary_role)
            db.add(user)
            await db.flush()
