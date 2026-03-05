"""Public API routes - no authentication required."""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.operational_models import User, Student
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.api.auth import get_password_hash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["Public"])


class StudentRegistrationRequest(BaseModel):
    full_name_fa: str
    phone: str
    email: Optional[str] = None
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    course_type: str = "introductory"  # introductory | comprehensive
    motivation: Optional[str] = None


@router.get("/stats")
async def public_stats(db: AsyncSession = Depends(get_db)):
    """Public statistics for homepage."""
    students = (await db.execute(select(func.count(Student.id)))).scalar() or 0
    processes = (await db.execute(select(func.count(ProcessDefinition.id)))).scalar() or 0
    users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    return {
        "students": students,
        "processes": processes,
        "staff": users,
        "years_active": 5,
    }


@router.get("/processes")
async def public_processes(db: AsyncSession = Depends(get_db)):
    """List process definitions with their states for public display."""
    result = await db.execute(
        select(ProcessDefinition).where(ProcessDefinition.is_active == True)
    )
    processes = result.scalars().all()

    items = []
    for p in processes:
        states_r = await db.execute(
            select(StateDefinition).where(StateDefinition.process_id == p.id)
        )
        states = states_r.scalars().all()
        items.append({
            "code": p.code,
            "name_fa": p.name_fa,
            "name_en": p.name_en,
            "description": p.description,
            "states_count": len(states),
            "states": [
                {
                    "code": s.code,
                    "name_fa": s.name_fa,
                    "state_type": s.state_type,
                    "order": s.order,
                }
                for s in sorted(states, key=lambda x: x.order or 0)
            ],
        })

    return {"processes": items}


@router.post("/register")
async def register_student(data: StudentRegistrationRequest, db: AsyncSession = Depends(get_db)):
    """Public student registration (creates user + student profile)."""
    phone = data.phone.strip().replace(" ", "")
    if not phone.startswith("09") or len(phone) != 11:
        raise HTTPException(status_code=400, detail="شماره موبایل نامعتبر است")

    existing = await db.execute(select(User).where(User.phone == phone))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="این شماره موبایل قبلاً ثبت شده است")

    if data.email:
        existing_email = await db.execute(select(User).where(User.email == data.email))
        if existing_email.scalars().first():
            raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است")

    user = User(
        id=uuid.uuid4(),
        username=f"student_{phone}",
        phone=phone,
        email=data.email,
        hashed_password=get_password_hash(str(uuid.uuid4())),
        full_name_fa=data.full_name_fa,
        role="student",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    student_count = (await db.execute(select(func.count(Student.id)))).scalar() or 0
    student_code = f"STU-{student_count + 1001}"

    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code=student_code,
        course_type=data.course_type,
        extra_data={
            "education_level": data.education_level,
            "field_of_study": data.field_of_study,
            "motivation": data.motivation,
            "registration_source": "public_website",
        },
    )
    db.add(student)
    await db.commit()

    return {
        "success": True,
        "message": "ثبت‌نام شما با موفقیت انجام شد. پس از بررسی، نتیجه از طریق پیامک اطلاع‌رسانی خواهد شد.",
        "student_code": student_code,
    }
