"""Shared authorization helpers — prevent IDOR on student/process resources."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_roles import user_has_any_role, user_has_role
from app.models.operational_models import ProcessInstance, Student, User

# Roles that may read any student/process data (operator portals).
_OPERATOR_READ_ROLES = frozenset(
    {
        "admin",
        "staff",
        "finance",
        "deputy_education",
        "site_manager",
        "committee",
        "supervisor",
        "therapist",
        "interviewer",
        "instructor",
        "ta",
        "faculty_1",
        "educational_instructor",
    }
)


def normalize_role(role: Optional[str]) -> str:
    return (role or "").strip().lower() or "student"


def is_operator_role(role: Optional[str]) -> bool:
    """Legacy helper: single role string. Prefer is_operator_user for multi-role accounts."""
    r = normalize_role(role)
    return r in _OPERATOR_READ_ROLES or r == "admin"


def is_operator_user(user: User) -> bool:
    return user_has_any_role(user, _OPERATOR_READ_ROLES, admin_bypass=True)


async def student_for_user(db: AsyncSession, user: User) -> Optional[Student]:
    r = await db.execute(select(Student).where(Student.user_id == user.id))
    return r.scalars().first()


async def ensure_can_read_student(
    db: AsyncSession,
    current_user: User,
    student_id: uuid.UUID,
) -> Student:
    """Students may only read their own profile; operators may read any."""
    stmt = select(Student).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if is_operator_user(current_user):
        return student
    if not user_has_role(current_user, "student", admin_bypass=False):
        raise HTTPException(status_code=403, detail="دسترسی به پروفایل دانشجو مجاز نیست.")
    if student.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="این پروفایل متعلق به حساب شما نیست.")
    return student


async def ensure_can_read_process_instance(
    db: AsyncSession,
    current_user: User,
    instance: ProcessInstance,
) -> None:
    """Students may only access their own process instances."""
    if instance is None:
        return
    if is_operator_user(current_user):
        return
    if not user_has_role(current_user, "student", admin_bypass=False):
        raise HTTPException(status_code=403, detail="دسترسی به این فرایند مجاز نیست.")
    st = await student_for_user(db, current_user)
    if not st or st.id != instance.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این فرایند متعلق به حساب شما نیست.",
        )


async def ensure_can_pay_for_instance(
    db: AsyncSession,
    current_user: User,
    student_id: uuid.UUID,
    instance_id: Optional[uuid.UUID],
) -> None:
    """Payment create/verify: student must own student_id and instance (if given)."""
    if is_operator_user(current_user):
        return
    st = await student_for_user(db, current_user)
    if not st or st.id != student_id:
        raise HTTPException(status_code=403, detail="پرداخت برای این دانشجو مجاز نیست.")
    if instance_id is None:
        return
    r = await db.execute(select(ProcessInstance).where(ProcessInstance.id == instance_id))
    inst = r.scalars().first()
    if not inst:
        raise HTTPException(status_code=404, detail="فرایند یافت نشد.")
    if inst.student_id != student_id:
        raise HTTPException(status_code=403, detail="فرایند با دانشجو هم‌خوانی ندارد.")
    await ensure_can_read_process_instance(db, current_user, inst)
