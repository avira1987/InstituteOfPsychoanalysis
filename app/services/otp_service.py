"""OTP (One-Time Password) service for SMS-based authentication."""

import hashlib
import hmac
import logging
import secrets
import re
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_access_token, get_password_hash
from app.config import get_settings
from app.models.operational_models import OTPCode, User, Student
from app.services import sms_simulation_service as sms_simulation
from app.services.sms_gateway import _otp_login_sms_body_fa, normalize_ir_mobile, send_otp_sms, send_sms

OTP_EXPIRY_SECONDS = 120
OTP_MAX_ATTEMPTS = 5
OTP_RATE_LIMIT_WINDOW = 600  # 10 minutes
OTP_RATE_LIMIT_COUNT = 3

logger = logging.getLogger(__name__)


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _generate_portal_password() -> str:
    """رمز عددی ساده برای ورود با نام کاربری (مسیر ورود پرسنل)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _student_portal_welcome_sms_text(username: str, password: str) -> str:
    return (
        "انستیتو روانکاوی تهران: خوش آمدید. "
        f"نام کاربری ورود بدون پیامک (همان شماره موبایل): {username} "
        f"رمز عبور: {password} "
        "از صفحهٔ ورود، «ورود پرسنل و مدیران» را بزنید و همین نام کاربری و رمز را وارد کنید."
    )


def _student_portal_welcome_ui_message() -> str:
    """بدون افشای رمز در پاسخ JSON؛ فقط پس از صدور اولین رمز پورتال."""
    return (
        "به انستیتو روانکاوی تهران خوش آمدید. "
        "نام کاربری ورود «بدون پیامک» همان شماره موبایل شماست و یک رمز عددی ساده برایتان صادر و در سامانه ذخیره شد. "
        "در صورت فعال بودن پیامک، همان نام کاربری و رمز نیز برای شما پیامک می‌شود؛ "
        "می‌توانید از پایین صفحهٔ ورود با لینک «ورود پرسنل و مدیران» با این مشخصات وارد شوید."
    )


async def _issue_student_portal_password_if_needed(
    db: AsyncSession, user: User, phone: str, *, commit: bool = True
) -> tuple[bool, str | None]:
    """Issue portal password for student if needed. Returns (issued, plain_password_for_sms)."""
    if (user.role or "").strip() != "student":
        return False, None
    if user.hashed_password and (user.username or "").strip() == phone:
        return False, None

    settings = get_settings()
    if (user.username or "").strip() != phone:
        taken = (
            await db.execute(
                select(User.id).where(User.username == phone, User.id != user.id).limit(1)
            )
        ).scalar_one_or_none()
        if taken is None:
            user.username = phone
    plain = _generate_portal_password()
    user.hashed_password = get_password_hash(plain)
    user.portal_password_plain = None
    if commit:
        await db.commit()
        await db.refresh(user)
    else:
        await db.flush()

    if commit and getattr(settings, "STUDENT_FIRST_LOGIN_WELCOME_SMS", True):
        text = _student_portal_welcome_sms_text(user.username, plain)
        try:
            await send_sms(
                phone,
                text,
                template_key="student_portal_welcome_credentials",
                context={"username": user.username, "password": plain},
            )
        except Exception:
            logger.warning("ارسال پیامک خوش‌آمد/رمز پورتال ناموفق بود", exc_info=True)
    return True, plain


_FA_DIGITS_OTP = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_AR_DIGITS_OTP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_LATIN_TO_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def normalize_otp_code(raw: str) -> str:
    """فقط رقم لاتین ۰–۹؛ ارقام فارسی/عربی و فاصله حذف می‌شوند (هم‌خوان با متن پیامک)."""
    if raw is None:
        return ""
    t = str(raw).strip().translate(_FA_DIGITS_OTP).translate(_AR_DIGITS_OTP)
    return "".join(c for c in t if c.isdigit())


def hash_otp_code(code: str) -> str:
    """Store OTP as HMAC so DB leaks do not reveal live codes."""
    secret = (get_settings().SECRET_KEY or "").encode("utf-8")
    return hmac.new(secret, normalize_otp_code(code).encode("utf-8"), hashlib.sha256).hexdigest()


def _otp_matches(stored: str | None, code_norm: str) -> bool:
    if not stored:
        return False
    # Backward-compatible: legacy rows may still hold plaintext 6-digit codes
    if len(stored) == 6 and stored.isdigit():
        return hmac.compare_digest(stored, code_norm)
    return hmac.compare_digest(stored, hash_otp_code(code_norm))


def _phone_storage_variants(normalized: str) -> list[str]:
    """مقادیر متداول users.phone از import/ثبت دستی که با normalize_ir_mobile فرق دارند."""
    if not re.fullmatch(r"09\d{9}", normalized):
        return []
    tail = normalized[1:]
    out = [
        normalized,
        normalized.translate(_LATIN_TO_FA_DIGITS),
        f"+98{tail}",
        f"0098{tail}",
        f"98{tail}",
    ]
    seen: set[str] = set()
    unique: list[str] = []
    for v in out:
        if v and v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _login_phone_match_score(user: User, normalized_phone: str) -> int:
    score = 0
    if user.is_active:
        score += 20
    if (user.role or "").strip() == "student":
        score += 10
    stored = normalize_ir_mobile(user.phone or "")
    if stored == normalized_phone:
        score += 5
    if (user.username or "").strip() == normalized_phone:
        score += 3
    return score


async def find_user_by_login_phone(db: AsyncSession, phone: str) -> User | None:
    """یافتن کاربر برای ورود OTP: phone نرمال، نام‌کاربری=موبایل، و قالب‌های قدیمی phone."""
    normalized = normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", normalized):
        return None

    by_id: dict[uuid.UUID, User] = {}
    for variant in _phone_storage_variants(normalized):
        rows = (await db.execute(select(User).where(User.phone == variant))).scalars().all()
        for u in rows:
            by_id[u.id] = u

    for u in (await db.execute(select(User).where(User.username == normalized))).scalars().all():
        by_id[u.id] = u

    if not by_id:
        return None

    return max(by_id.values(), key=lambda u: _login_phone_match_score(u, normalized))


async def _sync_user_phone_for_login(
    db: AsyncSession, user: User, normalized_phone: str, *, commit: bool = True
) -> None:
    """ذخیرهٔ یکسان 09xxxxxxxxx حتی اگر مقدار قبلی +98/ارقام فارسی بود."""
    if (user.phone or "").strip() != normalized_phone:
        user.phone = normalized_phone
        if commit:
            await db.commit()
            await db.refresh(user)
        else:
            await db.flush()


async def _invalidate_other_active_otps(
    db: AsyncSession, phone: str, keep_id: uuid.UUID
) -> None:
    """پس از صدور کد جدید، هر OTP فعال دیگر همان شماره را باطل می‌کند (رفع race درخواست دوبل)."""
    await db.execute(
        update(OTPCode)
        .where(
            and_(
                OTPCode.phone == phone,
                OTPCode.is_used.is_(False),
                OTPCode.id != keep_id,
            )
        )
        .values(is_used=True)
    )


async def _fetch_active_otps(db: AsyncSession, phone: str, now: datetime) -> list[OTPCode]:
    result = await db.execute(
        select(OTPCode)
        .where(
            and_(
                OTPCode.phone == phone,
                OTPCode.is_used.is_(False),
                OTPCode.expires_at > now,
            )
        )
        .order_by(OTPCode.created_at.desc())
    )
    return list(result.scalars().all())


async def request_otp(db: AsyncSession, phone: str) -> dict:
    """Generate and send an OTP code to the given phone number (ورود دانشجو با موبایل)."""
    phone = normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", phone):
        return {"success": False, "error": "شماره موبایل نامعتبر است. فرمت صحیح: 09xxxxxxxxx"}

    settings = get_settings()
    if getattr(settings, "OTP_RESTRICT_TO_STUDENT_PHONES", False):
        u = await find_user_by_login_phone(db, phone)
        if not u or not u.is_active or (u.role or "").strip() != "student":
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

    # فقط آخرین کد معتبر باشد؛ درخواست مجدد کدهای قبلی را باطل می‌کند (پیامک دیررس / چند کد)
    await db.execute(
        update(OTPCode)
        .where(and_(OTPCode.phone == phone, OTPCode.is_used.is_(False)))
        .values(is_used=True)
    )

    code = _generate_code()
    otp = OTPCode(
        id=uuid.uuid4(),
        phone=phone,
        code=hash_otp_code(code),
        expires_at=now + timedelta(seconds=OTP_EXPIRY_SECONDS),
    )
    db.add(otp)
    await db.commit()

    # ملی‌پیامک: ارسال OTP با متد SendOtp (فقط عدد کد؛ متن پیش‌فرض سامانه) — webservice-Otp.pdf
    sms_result = await send_otp_sms(phone, code)
    provider = (settings.SMS_PROVIDER or "log").lower()
    if (
        sms_result.get("success", False)
        and provider == "log"
        and getattr(settings, "SMS_SIMULATION_UI", False)
    ):
        body_text = sms_result.get("simulated_message") or _otp_login_sms_body_fa(code)
        sid = await sms_simulation.record_simulated_sms_in_request_session(db, phone, body_text, kind="otp")
        if sid:
            sms_result["simulated_sms_id"] = sid
            sms_result["simulated_message"] = body_text

    if not sms_result.get("success", False) and provider != "log":
        logger.warning(
            "OTP SMS send failed: phone=%s mellipayamak_path=%s raw_error=%s raw_response=%s",
            phone,
            sms_result.get("provider"),
            sms_result.get("error"),
            sms_result.get("response"),
        )
        if settings.OTP_SHOW_CODE_IN_UI:
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
        await db.execute(delete(OTPCode).where(OTPCode.id == otp.id))
        await db.commit()
        return {
            "success": False,
            "error": "ارسال پیامک ناموفق بود. شماره خط و اتصال سامانه را بررسی کنید یا بعداً تلاش کنید.",
        }

    await _invalidate_other_active_otps(db, phone, otp.id)
    await db.commit()

    result = {
        "success": True,
        "message": (
            "کد تأیید ارسال شد. اگر چند پیامک دارید، فقط **آخرین** کد را وارد کنید؛ "
            "پیامک‌های قبلی دیگر معتبر نیستند."
        ),
        "expires_in": OTP_EXPIRY_SECONDS,
    }
    # پاپ‌آپ تست: log (درخواست) یا mirror پس از ملی‌پیامک
    if getattr(settings, "SMS_SIMULATION_UI", False):
        sim_payload = sms_result.get("simulated_sms")
        if sim_payload:
            result["simulated_sms"] = sim_payload
        elif (settings.SMS_PROVIDER or "log").lower() == "log":
            msg = sms_result.get("simulated_message") or _otp_login_sms_body_fa(code)
            sim_id = sms_result.get("simulated_sms_id") or uuid.uuid4().hex
            result["simulated_sms"] = {
                "id": str(sim_id),
                "phone": phone,
                "message": msg,
                "kind": "otp",
                "created_at": now.isoformat(),
            }
    # نمایش کد روی وب (dev / تا زمان تکمیل پیامک واقعی) — با OTP_SHOW_CODE_IN_UI=false در production خاموش کنید.
    if settings.OTP_SHOW_CODE_IN_UI:
        result["dev_code"] = code
        result["dev_hint"] = (
            "این کد در کادرهای ورود کپی نمی‌شود؛ باید دستی وارد شود. برای ارسال واقعی پیامک: "
            "SMS_PROVIDER=mellipayamak و تنظیمات ملی‌پیامک در .env."
        )
    return result


async def verify_otp_code_only(db: AsyncSession, phone: str, code: str) -> dict:
    """تأیید کد پیامکی بدون صدور JWT (مثلاً امضای دیجیتال تعهدنامه در فرم مدارک)."""
    phone = normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", phone):
        return {"success": False, "error": "شماره موبایل نامعتبر است. فرمت صحیح: 09xxxxxxxxx"}
    now = datetime.now(timezone.utc)
    code_norm = normalize_otp_code(code)
    if len(code_norm) != 6:
        return {"success": False, "error": "کد تأیید باید ۶ رقم باشد."}

    active = await _fetch_active_otps(db, phone, now)
    if not active:
        return {"success": False, "error": "کد منقضی شده یا نامعتبر است. لطفاً دوباره درخواست دهید."}

    latest = active[0]
    if not _otp_matches(latest.code, code_norm):
        latest.attempts += 1
        if latest.attempts > OTP_MAX_ATTEMPTS:
            latest.is_used = True
        await db.commit()
        remaining = max(0, OTP_MAX_ATTEMPTS - latest.attempts)
        return {
            "success": False,
            "error": f"کد وارد شده صحیح نیست. {remaining} تلاش باقی‌مانده.",
        }

    latest.is_used = True
    for other in active:
        if other.id != latest.id:
            other.is_used = True
    await db.commit()
    return {"success": True, "verified": True}


async def verify_otp(db: AsyncSession, phone: str, code: str) -> dict:
    """Verify an OTP code and return a JWT token if valid."""
    phone = normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", phone):
        return {"success": False, "error": "شماره موبایل نامعتبر است. فرمت صحیح: 09xxxxxxxxx"}
    settings = get_settings()
    now = datetime.now(timezone.utc)
    code_norm = normalize_otp_code(code)
    if len(code_norm) != 6:
        return {"success": False, "error": "کد تأیید باید ۶ رقم باشد."}

    active = await _fetch_active_otps(db, phone, now)
    if not active:
        return {"success": False, "error": "کد منقضی شده یا نامعتبر است. لطفاً دوباره درخواست دهید."}

    latest = active[0]
    if not _otp_matches(latest.code, code_norm):
        latest.attempts += 1
        if latest.attempts > OTP_MAX_ATTEMPTS:
            latest.is_used = True
        await db.commit()
        remaining = max(0, OTP_MAX_ATTEMPTS - latest.attempts)
        stale_hint = (
            " اگر چند پیامک دریافت کرده‌اید، فقط کد **آخرین** پیامک را وارد کنید؛ "
            "کد پیامک‌های قبلی (حتی با تأخیر) دیگر قبول نمی‌شود."
        )
        return {
            "success": False,
            "error": f"کد وارد شده صحیح نیست.{stale_hint} {remaining} تلاش باقی‌مانده.",
        }

    otp = latest

    user = await find_user_by_login_phone(db, phone)
    if user is not None and not user.is_active:
        return {
            "success": False,
            "error": "حساب کاربری این شماره غیرفعال است. لطفاً با واحد آموزش تماس بگیرید.",
        }
    if user is None and getattr(settings, "OTP_RESTRICT_TO_STUDENT_PHONES", False):
        return {
            "success": False,
            "error": "حساب دانشجویی با این شماره ثبت نشده است.",
        }
    if user is None:
        username_taken = (
            await db.execute(select(User.id).where(User.username == phone).limit(1))
        ).scalar_one_or_none()
        if username_taken is not None:
            logger.error(
                "OTP verify: username=%s exists but phone not linked for login lookup",
                phone,
            )
            return {
                "success": False,
                "error": (
                    "پروندهٔ این شماره در سامانه ناقص ثبت شده است "
                    "(نام کاربری تکراری بدون شمارهٔ موبایل). لطفاً با پشتیبانی تماس بگیرید."
                ),
            }

    otp.is_used = True
    for other in active:
        if other.id != otp.id:
            other.is_used = True

    issued_portal_credentials = False
    try:
        issued_plain: str | None = None
        if not user:
            initial_plain = _generate_portal_password()
            user = User(
                id=uuid.uuid4(),
                username=phone,
                phone=phone,
                hashed_password=get_password_hash(initial_plain),
                portal_password_plain=None,
                full_name_fa="",
                role="student",
                is_active=True,
            )
            db.add(user)
            await db.flush()
            issued_portal_credentials = True
            issued_plain = initial_plain
        else:
            await _sync_user_phone_for_login(db, user, phone, commit=False)
            issued_portal_credentials, issued_plain = await _issue_student_portal_password_if_needed(
                db, user, phone, commit=False
            )

        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        logger.exception("OTP verify failed after code match for phone=%s", phone)
        return {
            "success": False,
            "error": "خطا در تکمیل ورود. لطفاً دوباره کد دریافت کنید یا با پشتیبانی تماس بگیرید.",
        }

    if issued_portal_credentials and issued_plain and getattr(settings, "STUDENT_FIRST_LOGIN_WELCOME_SMS", True):
        welcome_txt = _student_portal_welcome_sms_text(user.username, issued_plain)
        try:
            await send_sms(
                phone,
                welcome_txt,
                template_key="student_portal_welcome_credentials",
                context={
                    "username": user.username,
                    "password": issued_plain,
                },
            )
        except Exception:
            logger.warning("ارسال پیامک خوش‌آمد پس از OTP ناموفق بود", exc_info=True)

    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role}
    )

    has_student = (
        await db.execute(select(Student).where(Student.user_id == user.id).limit(1))
    ).scalars().first()
    is_new_student = user.role == "student" and has_student is None

    out = {
        "success": True,
        "access_token": access_token,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "full_name_fa": user.full_name_fa or "",
            "role": user.role,
            "phone": user.phone,
            "is_new": is_new_student,
        },
    }
    if user.role == "student" and issued_portal_credentials:
        out["welcome_message"] = _student_portal_welcome_ui_message()
    return out
