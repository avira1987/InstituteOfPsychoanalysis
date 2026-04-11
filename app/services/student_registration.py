"""Shared logic for public and authenticated student registration."""

import logging
import uuid
from typing import Literal, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, User
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)


async def create_student_profile_for_user(
    db: AsyncSession,
    user: User,
    *,
    course_type: Literal["introductory", "comprehensive"],
    education_level: Optional[str],
    field_of_study: Optional[str],
    motivation: Optional[str],
    registration_source: str,
) -> tuple[Student, str]:
    """
    Create Student row and start initial registration process. Caller must commit.

    Returns (student, student_code).
    """
    student_count = (await db.execute(select(func.count(Student.id)))).scalar() or 0
    student_code = f"STU-{student_count + 1001}"

    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code=student_code,
        course_type=course_type,
        extra_data={
            "education_level": education_level,
            "field_of_study": field_of_study,
            "motivation": motivation,
            "registration_source": registration_source,
        },
    )
    db.add(student)
    await db.flush()

    try:
        service = StudentService(db)
        await service.start_initial_process_for_student(student, user)
    except Exception:
        logger.exception(
            "Failed to auto-start initial process for student %s",
            student.student_code,
        )

    return student, student_code


async def commit_registration_or_rollback(db: AsyncSession) -> None:
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.exception("Student registration commit failed")
        raise


def build_public_registration_response(
    *,
    student_code: str,
    username: str,
    phone: str,
    initial_password_plain: str,
) -> dict:
    return {
        "success": True,
        "message": "ثبت‌نام شما با موفقیت انجام شد. همین حالا می‌توانید وارد پنل کاربری شوید؛ ورود با پیامک یا با نام کاربری و رمز عبور زیر ممکن است.",
        "student_code": student_code,
        "username": username,
        "phone": phone,
        "initial_password": initial_password_plain,
        "login_hint_fa": "در نسخهٔ عملیاتی، همین اطلاعات از طریق پیامک ارسال می‌شود. این صفحه فعلاً همان نقش را دارد.",
    }


def build_complete_registration_response(
    *,
    student_code: str,
    username: str,
    phone: str,
) -> dict:
    return {
        "success": True,
        "message": "ثبت‌نام شما تکمیل شد. می‌توانید از پنل دانشجو مسیر ثبت‌نام را ادامه دهید.",
        "student_code": student_code,
        "username": username,
        "phone": phone,
    }
