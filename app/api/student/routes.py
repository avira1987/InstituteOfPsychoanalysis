"""Student-facing API endpoints."""

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.core.engine import StateMachineEngine
from app.core.gamification import GAMIFICATION_VERSION, merge_gamification_into_extra
from app.api.auth import get_current_user, require_role
from app.models.operational_models import User, Student
from app.services.student_registration import (
    build_complete_registration_response,
    commit_registration_or_rollback,
    create_student_profile_for_user,
)
from app.services.student_service import StudentService
from app.services.student_tracker_summary import summarize_primary_path_for_student
from app.services.attendance_service import AttendanceService
from app.api.public_routes import (
    StudentRegistrationRequest,
    _validate_registration_data,
    _normalize_phone,
    validate_national_code_ir,
)

router = APIRouter(prefix="/api/students", tags=["Students"])


# ─── Schemas ────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    user_id: str
    student_code: str
    course_type: str  # "introductory" | "comprehensive"
    is_intern: bool = False
    term_count: int = 1
    current_term: int = 1
    weekly_sessions: int = 1


class StudentUpdate(BaseModel):
    course_type: Optional[str] = None
    is_intern: Optional[bool] = None
    term_count: Optional[int] = None
    current_term: Optional[int] = None
    weekly_sessions: Optional[int] = None
    therapy_started: Optional[bool] = None
    extra_data: Optional[dict] = Field(
        default=None,
        description="ادغام سطح‌بالا در student.extra_data — فقط مدیر.",
    )


class CompleteStudentRegistrationBody(BaseModel):
    """تکمیل ثبت‌نام پس از ورود با OTP؛ شماره موبایل از حساب کاربری خوانده می‌شود."""

    full_name_fa: str = Field(..., min_length=1, description="نام و نام خانوادگی")
    national_code: str = Field(..., min_length=1, description="کد ملی")
    email: Optional[str] = None
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    course_type: Literal["introductory", "comprehensive"] = "introductory"
    motivation: Optional[str] = None


class StudentResponse(BaseModel):
    id: str
    user_id: str
    student_code: str
    course_type: str
    is_intern: bool
    term_count: int
    current_term: int
    therapy_started: bool
    weekly_sessions: int
    extra_data: Optional[dict] = None
    # فقط وقتی list_students با tracker_summary=true (مسیر اصلی / اقدام معلق)
    graduation_progress_pct: Optional[int] = None
    pending_action_fa: Optional[str] = None
    primary_process_name_fa: Optional[str] = None
    primary_current_state: Optional[str] = None
    primary_path_missing: Optional[bool] = None
    therapy_hours_progress_fa: Optional[str] = None

    model_config = {"from_attributes": True}


def _extra_for_response(raw) -> Optional[dict]:
    """JSONB گاهی به‌صورت رشته (legacy) است؛ Pydantic فقط dict می‌پذیرد."""
    if raw is None:
        return None
    return StateMachineEngine._as_mapping(raw)


# ─── Endpoints ──────────────────────────────────────────────────

@router.post("", response_model=StudentResponse)
async def create_student(
    student_data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Create a new student profile."""
    student = Student(
        id=uuid.uuid4(),
        user_id=uuid.UUID(student_data.user_id),
        student_code=student_data.student_code,
        course_type=student_data.course_type,
        is_intern=student_data.is_intern,
        term_count=student_data.term_count,
        current_term=student_data.current_term,
        weekly_sessions=student_data.weekly_sessions,
    )
    db.add(student)

    # Auto-start initial registration process for the new student and mark it as primary,
    # using the admin/staff user as actor.
    try:
        service = StudentService(db)
        await service.start_initial_process_for_student(student, current_user)
    except Exception:
        # Do not fail the API if process auto-start fails; just log.
        import logging
        logging.getLogger(__name__).exception(
            "Failed to auto-start initial process for student %s (admin-created)",
            student.student_code,
        )

    await db.flush()

    return StudentResponse(
        id=str(student.id),
        user_id=str(student.user_id),
        student_code=student.student_code,
        course_type=student.course_type,
        is_intern=student.is_intern,
        term_count=student.term_count,
        current_term=student.current_term,
        therapy_started=student.therapy_started,
        weekly_sessions=student.weekly_sessions,
        extra_data=_extra_for_response(student.extra_data),
    )


def _student_to_response(s: Student, tracker: Optional[dict] = None) -> StudentResponse:
    base = dict(
        id=str(s.id),
        user_id=str(s.user_id),
        student_code=s.student_code,
        course_type=s.course_type,
        is_intern=s.is_intern,
        term_count=s.term_count,
        current_term=s.current_term,
        therapy_started=s.therapy_started,
        weekly_sessions=s.weekly_sessions,
        extra_data=_extra_for_response(s.extra_data),
    )
    if tracker:
        base.update(tracker)
    return StudentResponse(**base)


@router.get("", response_model=list[StudentResponse])
async def list_students(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff", "therapist", "supervisor", "site_manager", "progress_committee", "education_committee", "supervision_committee", "specialized_commission", "therapy_committee_chair", "therapy_committee_executor", "deputy_education", "monitoring_committee_officer")),
    tracker_summary: bool = Query(False, description="پیشرفت تقریبی مسیر اصلی و اقدام معلق (دید دانشجو)"),
):
    """List all students (admin/staff/committee/therapist/supervisor)."""
    stmt = select(Student)
    result = await db.execute(stmt)
    students = result.scalars().all()
    out: list[StudentResponse] = []
    for s in students:
        tr: Optional[dict] = None
        if tracker_summary:
            tr = await summarize_primary_path_for_student(db, s)
        out.append(_student_to_response(s, tr))
    return out


@router.post("/complete-registration")
async def complete_student_registration(
    body: CompleteStudentRegistrationBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تکمیل ثبت‌نام برای کاربری که با OTP وارد شده و هنوز رکورد Student ندارد.
    شماره موبایل از حساب کاربری (JWT) است؛ امکان جعل شمارهٔ دیگر وجود ندارد.
    """
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="این مسیر فقط برای نقش دانشجو است.")

    phone = _normalize_phone(current_user.phone or "")
    if not phone:
        raise HTTPException(status_code=400, detail="شماره موبایل در حساب کاربری ثبت نشده است.")

    stmt_existing = select(Student).where(Student.user_id == current_user.id)
    if (await db.execute(stmt_existing)).scalars().first():
        raise HTTPException(status_code=409, detail="پروفایل دانشجویی شما قبلاً ثبت شده است.")

    synth = StudentRegistrationRequest(
        full_name_fa=body.full_name_fa,
        phone=phone,
        national_code=body.national_code,
        email=body.email,
        education_level=body.education_level,
        field_of_study=body.field_of_study,
        course_type=body.course_type,
        motivation=body.motivation,
    )
    _validate_registration_data(synth)
    nc = validate_national_code_ir(body.national_code or "")

    email_value = (body.email or "").strip() or None
    if email_value:
        stmt_email = select(User).where(User.email == email_value, User.id != current_user.id)
        if (await db.execute(stmt_email)).scalars().first():
            raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است.")

    current_user.full_name_fa = (body.full_name_fa or "").strip()
    current_user.email = email_value
    await db.flush()

    _, student_code = await create_student_profile_for_user(
        db,
        current_user,
        course_type=body.course_type,
        education_level=body.education_level,
        field_of_study=body.field_of_study,
        motivation=body.motivation,
        national_code=nc,
        registration_source="otp_then_complete",
    )
    try:
        await commit_registration_or_rollback(db)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="در ذخیره اطلاعات خطایی رخ داد. لطفاً چند دقیقه دیگر تلاش کنید یا با پشتیبانی تماس بگیرید.",
        ) from e

    return build_complete_registration_response(
        student_code=student_code,
        username=current_user.username,
        phone=phone,
    )


@router.get("/me", response_model=StudentResponse)
async def get_my_student_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's student profile (for students)."""
    stmt = select(Student).where(Student.user_id == current_user.id)
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")

    service = StudentService(db)
    profile_changed = await service.ensure_primary_registration_path(student, current_user)
    if profile_changed:
        flag_modified(student, "extra_data")

    extra = StateMachineEngine._as_mapping(student.extra_data)
    hp = extra.get("hidden_progress")
    g = extra.get("gamification")
    if hp and (not g or g.get("version") != GAMIFICATION_VERSION):
        student.extra_data = merge_gamification_into_extra(extra)
        flag_modified(student, "extra_data")
        profile_changed = True

    if profile_changed:
        await db.commit()
        await db.refresh(student)

    therapy_hours_progress_fa: Optional[str] = None
    if student.therapy_started:
        try:
            m = await AttendanceService(db).get_therapy_completion_metrics(student.id)
            th = float(m.get("therapy_hours_2x") or 0)
            therapy_hours_progress_fa = (
                f"پیشرفت ساعات درمان آموزشی (بر اساس جلسات تکمیل‌شده در سامانه): "
                f"{th:g} از ۲۵۰. پس از تکمیل حدنصاب‌های اعلام‌شده، از بخش «درخواست‌های دیگر» "
                f"فرایند «تکمیل و خاتمه درمان آموزشی» را اجرا کنید."
            )
        except Exception:
            therapy_hours_progress_fa = None

    return StudentResponse(
        id=str(student.id),
        user_id=str(student.user_id),
        student_code=student.student_code,
        course_type=student.course_type,
        is_intern=student.is_intern,
        term_count=student.term_count,
        current_term=student.current_term,
        therapy_started=student.therapy_started,
        weekly_sessions=student.weekly_sessions,
        extra_data=_extra_for_response(student.extra_data),
        therapy_hours_progress_fa=therapy_hours_progress_fa,
    )


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a student profile."""
    stmt = select(Student).where(Student.id == uuid.UUID(student_id))
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return StudentResponse(
        id=str(student.id),
        user_id=str(student.user_id),
        student_code=student.student_code,
        course_type=student.course_type,
        is_intern=student.is_intern,
        term_count=student.term_count,
        current_term=student.current_term,
        therapy_started=student.therapy_started,
        weekly_sessions=student.weekly_sessions,
        extra_data=_extra_for_response(student.extra_data),
    )


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    update_data: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Update a student profile."""
    stmt = select(Student).where(Student.id == uuid.UUID(student_id))
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    extra_patch = update_dict.pop("extra_data", None)
    for key, value in update_dict.items():
        setattr(student, key, value)

    if extra_patch is not None:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can merge extra_data")
        merged = dict(StateMachineEngine._as_mapping(student.extra_data))
        merged.update(extra_patch)
        student.extra_data = merged
        flag_modified(student, "extra_data")

    await db.flush()

    return StudentResponse(
        id=str(student.id),
        user_id=str(student.user_id),
        student_code=student.student_code,
        course_type=student.course_type,
        is_intern=student.is_intern,
        term_count=student.term_count,
        current_term=student.current_term,
        therapy_started=student.therapy_started,
        weekly_sessions=student.weekly_sessions,
        extra_data=_extra_for_response(student.extra_data),
    )
