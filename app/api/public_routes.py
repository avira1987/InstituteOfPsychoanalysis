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
from app.models.operational_models import User, Student, ProcessInstance
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.api.auth import get_password_hash
from app.services.student_registration import (
    build_public_registration_response,
    commit_registration_or_rollback,
    create_student_profile_for_user,
    find_student_by_national_code,
)
from app.services.student_registration_profile import (
    StudentRegistrationProfileFields,
    validate_registration_profile_fields,
)
from app.services.installment_settings_service import get_installment_policy
from app.services.sms_gateway import normalize_ir_mobile
from app.meta.student_lifecycle_matrix import get_student_lifecycle_matrix
from app.config import get_settings
from app.services.sms_gateway import send_sms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["Public"])


def _normalize_national_code_digits(raw: str) -> str:
    return (raw or "").strip().replace(" ", "").replace("-", "")


def validate_national_code_ir(raw: str) -> str:
    """کد ملی ایران — ۱۰ رقم با رقم کنترل؛ مقدار نرمال‌شدهٔ فقط رقمی برمی‌گردد."""
    s = _normalize_national_code_digits(raw)
    if not re.fullmatch(r"\d{10}", s):
        raise HTTPException(status_code=400, detail="کد ملی باید دقیقاً ۱۰ رقم باشد.")
    if len(set(s)) == 1:
        raise HTTPException(status_code=400, detail="کد ملی نامعتبر است.")
    check = int(s[9])
    csum = sum(int(s[i]) * (10 - i) for i in range(9)) % 11
    if csum < 2:
        if check != csum:
            raise HTTPException(status_code=400, detail="کد ملی نامعتبر است.")
    else:
        if check != 11 - csum:
            raise HTTPException(status_code=400, detail="کد ملی نامعتبر است.")
    return s


class StudentRegistrationRequest(StudentRegistrationProfileFields):
    full_name_fa: str = Field(..., min_length=1, description="نام و نام خانوادگی")
    phone: str = Field(..., min_length=1, description="شماره موبایل")
    national_code: str = Field(..., min_length=1, description="کد ملی")
    email: str = Field(..., min_length=1, description="ایمیل")
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    course_type: Literal["introductory", "comprehensive"] = "introductory"
    motivation: Optional[str] = None


@router.get("/portal-config")
async def public_portal_config():
    """تنظیمات عمومی پورتال برای UI (بدون auth)."""
    s = get_settings()
    return {
        "interview_booking_payment_deadline_minutes": int(
            getattr(s, "INTERVIEW_BOOKING_PAYMENT_DEADLINE_MINUTES", 10)
        ),
        "app_version": s.APP_VERSION,
    }


@router.get("/installment-policy")
async def public_installment_policy(db: AsyncSession = Depends(get_db)):
    """سیاست اقساط برای نمایش در وب‌سایت (بدون احراز هویت) — شامل فعال/غیرفعال بودن پرداخت قسطی."""
    return await get_installment_policy(db)


@router.get("/institute-info")
async def public_institute_info(db: AsyncSession = Depends(get_db)):
    """اطلاعات عمومی انستیتو برای فرم پذیرش (شماره پروانه فعالیت)."""
    from app.services.institute_activity_license_service import (
        activity_license_public_payload,
        get_activity_license_number,
    )

    number = await get_activity_license_number(db)
    return activity_license_public_payload(number)


@router.get("/sms-simulation-status")
async def public_sms_simulation_status():
    """وضعیت پاپ‌آپ تست پیامک — برای UI و اشکال‌زدایی (بدون auth)."""
    from app.config import get_settings
    from app.services import sms_simulation_service as sms_sim

    s = get_settings()
    return {
        "enabled": sms_sim.simulation_popup_enabled(),
        "provider": (s.SMS_PROVIDER or "log").lower(),
        "simulation_ui": bool(getattr(s, "SMS_SIMULATION_UI", False)),
        "mirror_real_sends": sms_sim.simulation_mirror_real_sends(),
        "popup_show_all": sms_sim.simulation_popup_show_all_setting(),
    }


@router.get("/stats")
async def public_stats(db: AsyncSession = Depends(get_db)):
    """Public statistics for homepage."""
    students = (await db.execute(select(func.count(Student.id)))).scalar() or 0
    processes = (await db.execute(select(func.count(ProcessDefinition.id)))).scalar() or 0
    users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    processes_in_progress = (
        await db.execute(
            select(func.count(ProcessInstance.id)).where(
                ProcessInstance.is_completed.is_(False),
                ProcessInstance.is_cancelled.is_(False),
            )
        )
    ).scalar() or 0

    return {
        "students": students,
        "processes": processes,
        "staff": users,
        "processes_in_progress": processes_in_progress,
    }


@router.get("/student-lifecycle-matrix")
async def public_student_lifecycle_matrix():
    """مسیر تحصیلی و نقش‌ها — نمای عمومی (بدون DB)."""
    return get_student_lifecycle_matrix()


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
    return normalize_ir_mobile(phone or "")

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

    email = (data.email or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="ایمیل را وارد کنید.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="فرمت ایمیل نامعتبر است.")
    if data.course_type not in ("introductory", "comprehensive"):
        raise HTTPException(status_code=400, detail="نوع دوره نامعتبر است.")
    validate_registration_profile_fields(data)


@router.get("/registration-gate")
async def get_intro_registration_gate(
    db: AsyncSession = Depends(get_db),
):
    """وضعیت باز/بسته بودن ثبت‌نام دورهٔ آشنایی (وابسته به آماده‌سازی ترم)."""
    from app.services.registration_readiness_service import check_intro_registration_gate

    return (await check_intro_registration_gate(db)).to_dict()


@router.post("/register")
async def register_student(data: StudentRegistrationRequest, db: AsyncSession = Depends(get_db)):
    """Public student registration (creates user + student profile)."""
    _validate_registration_data(data)
    if data.course_type == "introductory":
        from app.services.registration_readiness_service import check_intro_registration_gate

        gate = await check_intro_registration_gate(db)
        if not gate.allowed:
            raise HTTPException(status_code=403, detail=gate.reason_fa)
    nc = validate_national_code_ir(data.national_code or "")

    existing_by_nc = await find_student_by_national_code(db, nc)
    if existing_by_nc:
        gates = {}
        if isinstance(existing_by_nc.extra_data, dict):
            gates = (existing_by_nc.extra_data or {}).get("gates") or {}
        if gates.get("future_applications_blocked"):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "admission_rejected_blocked",
                    "message": (
                        "بر اساس نتیجهٔ مصاحبهٔ قبلی، امکان تکمیل مجدد فرم پذیرش برای ترم‌های آینده "
                        "برای این کد ملی وجود ندارد. در صورت پرسش با واحد پذیرش تماس بگیرید."
                    ),
                },
            )
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_national_id",
                "message": (
                    "این کد ملی قبلاً برای یک پروندهٔ دانشجویی ثبت شده است. "
                    "در صورت اشتباه بودن ورودی، کد را اصلاح کنید. "
                    "اگر با شمارهٔ موبایل جدید هستید و کد ملی متعلق به خودتان است، "
                    "از منوی «تیکت‌ها و درخواست‌ها» یک تیکت باز کنید و هنگام ثبت، گزینهٔ مربوط به نداشتن پروفایل دانشجویی را فعال کنید تا واحد پشتیبانی هماهنگی را انجام دهد."
                ),
            },
        )

    phone = _normalize_phone(data.phone)
    existing_row = await db.execute(select(User).where(User.phone == phone))
    existing_user = existing_row.scalars().first()
    if existing_user:
        stmt_st = select(Student).where(Student.user_id == existing_user.id)
        has_student = (await db.execute(stmt_st)).scalars().first()
        if not has_student:
            raise HTTPException(
                status_code=400,
                detail=(
                    "این شماره قبلاً برای ورود با پیامک ثبت شده است. "
                    "لطفاً وارد شوید و از منوی پنل، تکمیل ثبت‌نام دانشجو را انجام دهید."
                ),
            )
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
        username=phone,
        phone=phone,
        email=email_value,
        hashed_password=get_password_hash(initial_password_plain),
        portal_password_plain=None,
        full_name_fa=data.full_name_fa,
        role="student",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    student, student_code = await create_student_profile_for_user(
        db,
        user,
        course_type=data.course_type,
        education_level=data.education_level,
        field_of_study=data.field_of_study,
        motivation=data.motivation,
        national_code=nc,
        registration_source="public_website",
        profile_extra=validate_registration_profile_fields(data),
    )
    try:
        await commit_registration_or_rollback(db)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="در ذخیره اطلاعات خطایی رخ داد. لطفاً چند دقیقه دیگر تلاش کنید یا با پشتیبانی تماس بگیرید.",
        ) from e

    try:
        from app.services.otp_service import _student_portal_welcome_sms_text

        sms_text = _student_portal_welcome_sms_text(user.username, initial_password_plain)
        await send_sms(
            phone,
            sms_text,
            template_key="student_portal_welcome_credentials",
            context={"username": user.username, "password": initial_password_plain},
        )
    except Exception:
        logger.warning("Registration welcome SMS failed for phone=%s", phone, exc_info=True)

    return build_public_registration_response(
        student_code=student_code,
        username=user.username,
        phone=phone,
        initial_password_plain=initial_password_plain,
    )
