"""Institute-level operational student anchor for non-student workflows (semester prep)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.config import get_settings
from app.models.operational_models import Student, User


async def ensure_institute_operational_student(db: AsyncSession) -> Student:
    """Return (and create if needed) the institute operational student record."""
    settings = get_settings()
    code = (settings.INSTITUTE_OPERATIONAL_STUDENT_CODE or "INST-OPS").strip()

    stmt = select(Student).where(Student.student_code == code)
    existing = (await db.execute(stmt)).scalars().first()
    if existing is not None:
        return existing

    uid = uuid.uuid4()
    user = User(
        id=uid,
        username=f"institute_ops_{code.lower().replace('-', '_')}",
        email=f"{code.lower()}@institute.local",
        hashed_password=get_password_hash("unused-institute-anchor"),
        full_name_fa="پرونده عملیاتی انستیتو",
        role="student",
        is_active=True,
    )
    db.add(user)
    student = Student(
        id=uuid.uuid4(),
        user_id=uid,
        student_code=code,
        course_type="comprehensive",
        is_sample_data=False,
        extra_data={"institute_operational_anchor": True},
    )
    db.add(student)
    await db.flush()
    return student


async def get_institute_operational_student(db: AsyncSession) -> Student | None:
    settings = get_settings()
    code = (settings.INSTITUTE_OPERATIONAL_STUDENT_CODE or "INST-OPS").strip()
    stmt = select(Student).where(Student.student_code == code)
    return (await db.execute(stmt)).scalars().first()
