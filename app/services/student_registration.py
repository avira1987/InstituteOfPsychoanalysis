"""Shared logic for public and authenticated student registration."""

import logging
import re
import uuid
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, User
from app.services.student_service import StudentService

logger = logging.getLogger(__name__)

_STUDENT_CODE_RE = re.compile(r"^STU-(\d+)$")
_STUDENT_CODE_BASE = 1000  # شماره‌گذاری از STU-1001 به‌بعد


async def find_student_by_national_code(db: AsyncSession, national_code: str) -> Optional[Student]:
    """اولین دانشجویی که کد ملی در extra_data ذخیره شده دارد (هم‌خوان با create_student_profile_for_user)."""
    nc = (national_code or "").strip()
    if len(nc) != 10 or not nc.isdigit():
        return None
    # `extra_data` is generic JSON (PG `json`); `.contains()` compiles to LIKE and fails there.
    r = await db.execute(
        select(Student)
        .where(Student.extra_data["national_code"].as_string() == nc)
        .limit(1)
    )
    return r.scalars().first()


async def _next_student_code(db: AsyncSession) -> str:
    """STU-<n+1> با n=بزرگ‌ترین عدد موجود در ستون student_code (نه از روی COUNT(*) که با حذف/seed تصادم می‌دهد)."""
    rows = await db.execute(select(Student.student_code).where(Student.student_code.like("STU-%")))
    max_num = _STUDENT_CODE_BASE
    for code in rows.scalars().all():
        m = _STUDENT_CODE_RE.match(code or "")
        if not m:
            continue
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        if n > max_num:
            max_num = n
    return f"STU-{max_num + 1}"


async def create_student_profile_for_user(
    db: AsyncSession,
    user: User,
    *,
    course_type: Literal["introductory", "comprehensive"],
    education_level: Optional[str],
    field_of_study: Optional[str],
    motivation: Optional[str],
    national_code: Optional[str] = None,
    registration_source: str,
    profile_extra: Optional[dict] = None,
) -> tuple[Student, str]:
    """
    Create Student row and start initial registration process. Caller must commit.

    Returns (student, student_code).

    در صورت تصادم Unique (race بین دو ثبت‌نام هم‌زمان یا داده دستی)، حداکثر تا ۵ بار با کد بعدی تلاش می‌کند.
    """
    extra_data = {
        "education_level": education_level,
        "field_of_study": field_of_study,
        "motivation": motivation,
        "registration_source": registration_source,
        **({"national_code": national_code} if national_code else {}),
        **(profile_extra or {}),
    }

    last_err: Optional[Exception] = None
    student: Optional[Student] = None
    student_code = ""
    for attempt in range(5):
        student_code = await _next_student_code(db)
        try:
            async with db.begin_nested():  # SAVEPOINT: فقط INSERT دانشجو را در صورت تصادم برمی‌گرداند
                student = Student(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    student_code=student_code,
                    course_type=course_type,
                    extra_data=extra_data,
                )
                db.add(student)
                await db.flush()
            last_err = None
            break
        except IntegrityError as e:
            last_err = e
            student = None
            logger.warning(
                "student_code collision (attempt %s): %s — retrying with fresh code",
                attempt + 1,
                student_code,
            )
            continue

    if last_err is not None or student is None:
        if last_err is not None:
            raise last_err
        raise RuntimeError("Could not allocate student_code after retries")

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
    initial_password_plain: str | None = None,
) -> dict:
    from app.config import get_settings

    settings = get_settings()
    out = {
        "success": True,
        "message": "ثبت‌نام شما با موفقیت انجام شد. اطلاعات ورود از طریق پیامک ارسال می‌شود.",
        "student_code": student_code,
        "username": username,
        "phone": phone,
        "login_hint_fa": "رمز عبور اولیه از طریق پیامک برای شما ارسال شده است.",
    }
    if settings.DEBUG and initial_password_plain:
        out["initial_password"] = initial_password_plain
        out["login_hint_fa"] = "حالت توسعه: رمز در پاسخ API نمایش داده می‌شود؛ در production فقط پیامک."
    return out


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
