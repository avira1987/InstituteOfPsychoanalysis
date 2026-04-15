"""OTP (One-Time Password) service for SMS-based authentication."""

import random
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.operational_models import OTPCode, User
from app.services.sms_gateway import normalize_ir_mobile, send_otp_sms
from app.api.auth import create_access_token, get_password_hash

logger = logging.getLogger(__name__)

OTP_EXPIRY_SECONDS = 120
OTP_MAX_ATTEMPTS = 5
OTP_RATE_LIMIT_WINDOW = 600  # 10 minutes
OTP_RATE_LIMIT_COUNT = 3


def _generate_code() -> str:
    return f"{random.randint(100000, 999999)}"


async def request_otp(db: AsyncSession, phone: str) -> dict:
    """Generate and send an OTP code to the given phone number (ورود دانشجو با موبایل)."""
    phone = normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", phone):
        return {"success": False, "error": "شماره موبایل نامعتبر است. فرمت صحیح: 09xxxxxxxxx"}

    settings = get_settings()
    if getattr(settings, "OTP_RESTRICT_TO_STUDENT_PHONES", False):
        urow = await db.execute(
            select(User).where(
                User.phone == phone,
                User.is_active == True,
                User.role == "student",
            )
        )
        if not urow.scalars().first():
            return {
                "success": False,
                "error": "این شماره موبایل برای ورود دانشجویی ثبت نشده است. ابتدا ثبت‌نام کنید یا با آموزش تماس بگیرید.",
            }

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=OTP_RATE_LIMIT_WINDOW)
    result = await db.execute(
        select(OTPCode).where(
            and_(
                OTPCode.phone == phone,
                OTPCode.created_at >= window_start,
            )
        )
    )
    recent_codes = result.scalars().all()
    if len(recent_codes) >= OTP_RATE_LIMIT_COUNT:
        return {"success": False, "error": "تعداد درخواست‌ها بیش از حد مجاز است. لطفاً ۱۰ دقیقه صبر کنید."}

    code = _generate_code()
    otp = OTPCode(
        id=uuid.uuid4(),
        phone=phone,
        code=code,
        expires_at=now + timedelta(seconds=OTP_EXPIRY_SECONDS),
    )
    db.add(otp)
    await db.commit()

    # ملی‌پیامک: ارسال OTP با متد SendOtp (فقط عدد کد؛ متن پیش‌فرض سامانه) — webservice-Otp.pdf
    sms_result = await send_otp_sms(phone, code)
    provider = (settings.SMS_PROVIDER or "log").lower()

    if not sms_result.get("success", False) and provider != "log":
        if settings.OTP_SHOW_CODE_IN_UI:
            logger.warning(
                "SMS send failed but OTP_SHOW_CODE_IN_UI: keeping OTP and returning dev_code (phone=%s)",
                phone,
            )
            return {
                "success": True,
                "message": "پیامک ارسال نشد؛ کد فقط برای تست روی همین صفحه نمایش داده شد.",
                "expires_in": OTP_EXPIRY_SECONDS,
                "sms_failed": True,
                "dev_code": code,
                "dev_hint": (
                    "ارسال پیامک ناموفق بود. کد برای تست روی همین صفحه نمایش داده شد. "
                    "خط، نام کاربری/رمز وب‌سرویس و اتصال را بررسی کنید."
                ),
            }
        logger.error("SMS send failed for %s: %s", phone, sms_result)
        await db.execute(delete(OTPCode).where(OTPCode.id == otp.id))
        await db.commit()
        return {
            "success": False,
            "error": "ارسال پیامک ناموفق بود. شماره خط و اتصال سامانه را بررسی کنید یا بعداً تلاش کنید.",
        }

    result = {"success": True, "message": "کد تأیید ارسال شد.", "expires_in": OTP_EXPIRY_SECONDS}
    # نمایش کد روی وب (dev / تا زمان تکمیل پیامک واقعی) — با OTP_SHOW_CODE_IN_UI=false در production خاموش کنید.
    if settings.OTP_SHOW_CODE_IN_UI:
        result["dev_code"] = code
        result["dev_hint"] = (
            "کد برای تست روی همین صفحه نمایش داده شد. برای ارسال واقعی: "
            "SMS_PROVIDER=mellipayamak، SMS_USERNAME و (SMS_PASSWORD یا همان APIKey در SMS_API_KEY به‌عنوان password طبق پنل) یا فقط SMS_API_KEY برای کنسول، و SMS_LINE_NUMBER."
        )
    return result


async def verify_otp(db: AsyncSession, phone: str, code: str) -> dict:
    """Verify an OTP code and return a JWT token if valid."""
    phone = normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", phone):
        return {"success": False, "error": "شماره موبایل نامعتبر است. فرمت صحیح: 09xxxxxxxxx"}
    settings = get_settings()
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(OTPCode).where(
            and_(
                OTPCode.phone == phone,
                OTPCode.is_used == False,
                OTPCode.expires_at > now,
            )
        ).order_by(OTPCode.created_at.desc())
    )
    otp = result.scalars().first()

    if not otp:
        return {"success": False, "error": "کد منقضی شده یا نامعتبر است. لطفاً دوباره درخواست دهید."}

    otp.attempts += 1
    if otp.attempts > OTP_MAX_ATTEMPTS:
        otp.is_used = True
        await db.commit()
        return {"success": False, "error": "تعداد تلاش‌ها بیش از حد مجاز. لطفاً کد جدید درخواست دهید."}

    if otp.code != code.strip():
        await db.commit()
        remaining = OTP_MAX_ATTEMPTS - otp.attempts
        return {"success": False, "error": f"کد وارد شده صحیح نیست. {remaining} تلاش باقی‌مانده."}

    otp.is_used = True
    await db.commit()

    user_result = await db.execute(select(User).where(User.phone == phone))
    user = user_result.scalars().first()

    if not user:
        if getattr(settings, "OTP_RESTRICT_TO_STUDENT_PHONES", False):
            return {
                "success": False,
                "error": "حساب دانشجویی با این شماره ثبت نشده است.",
            }
        user = User(
            id=uuid.uuid4(),
            username=f"student_{phone}",
            phone=phone,
            hashed_password=get_password_hash(str(uuid.uuid4())),
            full_name_fa="",
            role="student",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role}
    )

    return {
        "success": True,
        "access_token": access_token,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "full_name_fa": user.full_name_fa or "",
            "role": user.role,
            "phone": user.phone,
            "is_new": not bool(user.full_name_fa),
        },
    }
