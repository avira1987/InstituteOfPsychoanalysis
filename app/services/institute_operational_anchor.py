"""Institute-level operational student anchor for non-student workflows (semester prep)."""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.config import get_settings
from app.models.operational_models import Student, User

ANCHOR_LABEL_FA = "پرونده عملیاتی انستیتو"
ANCHOR_DESCRIPTION_FA = (
    "رکورد سیستمی برای فرایندهای سطح مؤسسه (آماده‌سازی ترم پاییز/زمستان). "
    "دانشجوی واقعی نیست و در ردیابی دانشجویان نمایش داده نمی‌شود."
)


def institute_operational_student_code() -> str:
    return (get_settings().INSTITUTE_OPERATIONAL_STUDENT_CODE or "INST-OPS").strip()


def is_institute_operational_student(student: Student | None) -> bool:
    """True when the row is the institute operational anchor (not a real student)."""
    if student is None:
        return False
    code = institute_operational_student_code()
    if (student.student_code or "").strip() == code:
        return True
    extra = student.extra_data
    if isinstance(extra, Mapping) and extra.get("institute_operational_anchor"):
        return True
    return False


def is_institute_operational_student_payload(
    *,
    student_code: str | None = None,
    extra_data: Any = None,
) -> bool:
    """Same check for API/FE payloads without a Student ORM instance."""
    code = institute_operational_student_code()
    if (student_code or "").strip() == code:
        return True
    if isinstance(extra_data, Mapping) and extra_data.get("institute_operational_anchor"):
        return True
    return False


def anchor_public_info(student: Student) -> dict[str, Any]:
    """Compact descriptor for admin semester-prep UI."""
    return {
        "student_id": str(student.id),
        "student_code": student.student_code,
        "label_fa": ANCHOR_LABEL_FA,
        "description_fa": ANCHOR_DESCRIPTION_FA,
        "is_system": True,
    }


async def ensure_institute_operational_student(db: AsyncSession) -> Student:
    """Return (and create if needed) the institute operational student record."""
    code = institute_operational_student_code()

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
        full_name_fa=ANCHOR_LABEL_FA,
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
    code = institute_operational_student_code()
    stmt = select(Student).where(Student.student_code == code)
    return (await db.execute(stmt)).scalars().first()
