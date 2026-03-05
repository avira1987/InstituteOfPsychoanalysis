"""OTP (One-Time Password) service for SMS-based authentication."""

import random
import uuid
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.operational_models import OTPCode, User
from app.services.sms_gateway import send_sms
from app.api.auth import create_access_token, get_password_hash

logger = logging.getLogger(__name__)

OTP_EXPIRY_SECONDS = 120
OTP_MAX_ATTEMPTS = 5
OTP_RATE_LIMIT_WINDOW = 600  # 10 minutes
OTP_RATE_LIMIT_COUNT = 3


def _generate_code() -> str:
    return f"{random.randint(100000, 999999)}"


async def request_otp(db: AsyncSession, phone: str) -> dict:
    """Generate and send an OTP code to the given phone number."""
    phone = phone.strip().replace(" ", "")
    if not phone.startswith("09") or len(phone) != 11:
        return {"success": False, "error": "شماره موبایل نامعتبر است. فرمت صحیح: 09xxxxxxxxx"}

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

    message = f"کد ورود شما به انیستیتو روانکاوی تهران: {code}\nاین کد تا ۲ دقیقه معتبر است."
    sms_result = await send_sms(phone, message)

    if not sms_result.get("success", False) and sms_result.get("provider") != "log":
        logger.error(f"SMS send failed for {phone}: {sms_result}")

    result = {"success": True, "message": "کد تأیید ارسال شد.", "expires_in": OTP_EXPIRY_SECONDS}
    # در حالت توسعه (log): کد را در پاسخ برمی‌گردانیم تا تست شود
    if get_settings().DEBUG and sms_result.get("provider") == "log":
        result["dev_code"] = code
        result["dev_hint"] = "SMS در حالت log ارسال نمی‌شود. برای ارسال واقعی، SMS_PROVIDER و SMS_API_KEY را در .env تنظیم کنید."
    return result


async def verify_otp(db: AsyncSession, phone: str, code: str) -> dict:
    """Verify an OTP code and return a JWT token if valid."""
    phone = phone.strip().replace(" ", "")
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
        user = User(
            id=uuid.uuid4(),
            username=f"user_{phone}",
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
