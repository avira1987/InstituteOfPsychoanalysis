"""Public API routes - no authentication required."""

import uuid
import logging
import re
import secrets
import string
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.operational_models import User, Student
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.api.auth import get_password_hash
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["Public"])


class StudentRegistrationRequest(BaseModel):
    full_name_fa: str = Field(..., min_length=1, description="نام و نام خانوادگی")
    phone: str = Field(..., min_length=1, description="شماره موبایل")
    email: Optional[str] = None
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    course_type: Literal["introductory", "comprehensive"] = "introductory"
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


def _normalize_phone(phone: str) -> str:
    return phone.strip().replace(" ", "").replace("-", "")

def _validate_registration_data(data: StudentRegistrationRequest) -> None:
    """Validate and raise HTTPException with Persian message if invalid."""
    name = (data.full_name_fa or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="نام و نام خانوادگی را وارد کنید.")
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="نام و نام خانوادگی باید حداقل ۲ کاراکتر باشد.")

    phone = _normalize_phone(data.phone or "")
    if not phone:
        raise HTTPException(status_code=400, detail="شماره موبایل را وارد کنید.")
    if not re.match(r"^09\d{9}$", phone):
        raise HTTPException(
            status_code=400,
            detail="شماره موبایل باید با ۰۹ شروع شود و ۱۱ رقم باشد (مثال: ۰۹۱۲۳۴۵۶۷۸۹).",
        )

    if data.email and (data.email or "").strip():
        email = data.email.strip()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(status_code=400, detail="فرمت ایمیل نامعتبر است.")
    if data.course_type not in ("introductory", "comprehensive"):
        raise HTTPException(status_code=400, detail="نوع دوره نامعتبر است.")


@router.post("/register")
async def register_student(data: StudentRegistrationRequest, db: AsyncSession = Depends(get_db)):
    """Public student registration (creates user + student profile)."""
    _validate_registration_data(data)

    phone = _normalize_phone(data.phone)
    existing = await db.execute(select(User).where(User.phone == phone))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="این شماره موبایل قبلاً ثبت شده است.")

    email_value = (data.email or "").strip() or None  # avoid storing "" (breaks unique constraint)
    if email_value:
        existing_email = await db.execute(select(User).where(User.email == email_value))
        if existing_email.scalars().first():
            raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است.")

    # رمز اولیه برای ورود با نام کاربری؛ در محیط واقعی باید از طریق پیامک ارسال شود (اینجا یک‌بار در پاسخ برمی‌گردد)
    alphabet = string.ascii_letters + string.digits
    initial_password_plain = "".join(secrets.choice(alphabet) for _ in range(14))

    user = User(
        id=uuid.uuid4(),
        username=f"student_{phone}",
        phone=phone,
        email=email_value,
        hashed_password=get_password_hash(initial_password_plain),
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

    # Auto-start initial registration process for the new student and mark it as primary.
    # This should not block registration if it fails; errors are logged but not exposed to the user.
    try:
        service = StudentService(db)
        await service.start_initial_process_for_student(student, user)
    except Exception:
        logger.exception("Failed to auto-start initial process for student %s", student.student_code)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.exception("Student registration commit failed")
        raise HTTPException(
            status_code=500,
            detail="در ذخیره اطلاعات خطایی رخ داد. لطفاً چند دقیقه دیگر تلاش کنید یا با پشتیبانی تماس بگیرید.",
        ) from e

    return {
        "success": True,
        "message": "ثبت‌نام شما با موفقیت انجام شد. همین حالا می‌توانید وارد پنل کاربری شوید؛ ورود با پیامک یا با نام کاربری و رمز عبور زیر ممکن است.",
        "student_code": student_code,
        "username": user.username,
        "phone": phone,
        "initial_password": initial_password_plain,
        "login_hint_fa": "در نسخهٔ عملیاتی، همین اطلاعات از طریق پیامک ارسال می‌شود. این صفحه فعلاً همان نقش را دارد.",
    }
