"""Authentication API routes."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
import random
from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger(__name__)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.api.auth import (
    Token,
    UserCreate,
    UserResponse,
    authenticate_user,
    create_user,
    create_access_token,
    get_password_hash,
    get_current_user,
    require_role,
    verify_password,
)
from pydantic import BaseModel
from app.models.operational_models import User, LoginChallenge

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str
    security_answer: str | None = None  # پاسخ سوال امنیتی (در صورت تنظیم)
    challenge_id: str | None = None
    challenge_answer: str | None = None


class SecurityQuestionPreviewRequest(BaseModel):
    username: str


class SecurityQuestionPreviewResponse(BaseModel):
    has_security_question: bool
    question: str | None = None


class LoginChallengeResponse(BaseModel):
    challenge_id: str
    question: str


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and get an access token."""
    if not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user = await authenticate_user(db, form_data.username, form_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token = create_access_token(
            data={"sub": str(user.id), "username": user.username, "role": user.role}
        )
        return Token(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login-challenge", response_model=LoginChallengeResponse)
async def login_challenge(
    db: AsyncSession = Depends(get_db),
):
    """
    تولید یک سوال ساده برای جلوگیری از ربات در ورود با رمز عبور.
    مثال: «حاصل ۷ + ۴ چند می‌شود؟»
    """
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    question = f"حاصل {a} + {b} چند می‌شود؟"
    answer = str(a + b)

    challenge = LoginChallenge(
        question=question,
        answer_hash=get_password_hash(answer),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(challenge)
    await db.flush()
    await db.commit()

    return LoginChallengeResponse(
        challenge_id=str(challenge.id),
        question=question,
    )


@router.post("/security-question-preview", response_model=SecurityQuestionPreviewResponse)
async def security_question_preview(
    body: SecurityQuestionPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    برگرداندن سوال امنیتی (بدون پاسخ) برای فرم ورود.

    برای جلوگیری از نشت اطلاعات، اگر کاربر وجود نداشته باشد یا سوالی تنظیم نشده باشد،
    همیشه پاسخ «has_security_question = False» برگردانده می‌شود.
    """
    stmt = select(User).where(User.username == body.username)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not user.security_question:
        return SecurityQuestionPreviewResponse(has_security_question=False, question=None)
    return SecurityQuestionPreviewResponse(
        has_security_question=True,
        question=user.security_question,
    )


@router.post("/login-json", response_model=Token)
async def login_json(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with JSON body (alternative to form for debugging)."""
    if not body.username or not body.password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    try:
        # اول چالش ضدربات را بررسی کن
        if not body.challenge_id or not body.challenge_answer:
            raise HTTPException(status_code=400, detail="کد امنیتی الزامی است")

        try:
            challenge_uuid = uuid.UUID(body.challenge_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="کد امنیتی نامعتبر است")

        stmt = select(LoginChallenge).where(LoginChallenge.id == challenge_uuid)
        result = await db.execute(stmt)
        challenge = result.scalars().first()
        now = datetime.now(timezone.utc)

        if (
            not challenge
            or challenge.is_used
            or challenge.expires_at < now
            or not verify_password(body.challenge_answer.strip(), challenge.answer_hash)
        ):
            raise HTTPException(status_code=400, detail="کد امنیتی نامعتبر است")

        challenge.is_used = True
        await db.commit()

        # سپس اعتبارسنجی نام کاربری/رمز عبور (و در صورت وجود، سوال امنیتی کاربر)
        user = await authenticate_user(db, body.username, body.password, body.security_answer)
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect username or password")
        access_token = create_access_token(
            data={"sub": str(user.id), "username": user.username, "role": user.role}
        )
        return Token(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Login error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Register a new user (admin only)."""
    user = await create_user(db, user_data)
    await db.flush()
    return UserResponse(
        id=str(user.id),
        username=user.username,
        full_name_fa=user.full_name_fa,
        role=user.role,
        is_active=user.is_active,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        full_name_fa=current_user.full_name_fa,
        role=current_user.role,
        is_active=current_user.is_active,
    )


class SetSecurityQuestionBody(BaseModel):
    question: str
    answer: str


@router.post("/set-security-question")
async def set_security_question(
    body: SetSecurityQuestionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """تنظیم سوال و پاسخ امنیتی برای ورود با رمز عبور."""
    if not body.question.strip() or not body.answer.strip():
        raise HTTPException(status_code=400, detail="سوال و پاسخ امنیتی الزامی است")
    current_user.security_question = body.question.strip()
    current_user.security_answer_hash = get_password_hash(body.answer.strip())
    await db.commit()
    return {"success": True, "message": "سوال امنیتی ذخیره شد."}


class OTPRequestBody(BaseModel):
    phone: str

class OTPVerifyBody(BaseModel):
    phone: str
    code: str


@router.post("/otp/request")
async def otp_request(body: OTPRequestBody, db: AsyncSession = Depends(get_db)):
    """Send a one-time password to the given phone number."""
    from app.services.otp_service import request_otp as do_request
    result = await do_request(db, body.phone)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/otp/verify")
async def otp_verify(body: OTPVerifyBody, db: AsyncSession = Depends(get_db)):
    """Verify OTP code and return JWT token."""
    from app.services.otp_service import verify_otp as do_verify
    result = await do_verify(db, body.phone, body.code)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/create-admin")
async def create_admin_user(db: AsyncSession = Depends(get_db)):
    """Create or reset admin user (admin/admin123). Only available when DEBUG=true."""
    if not get_settings().DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    result = await db.execute(select(User).where(User.username == "admin"))
    admin = result.scalars().first()
    if admin:
        admin.hashed_password = get_password_hash("admin123")
        admin.is_active = True
        admin.email = admin.email or "admin@anistito.ir"
        admin.full_name_fa = admin.full_name_fa or "مدیر سیستم"
        await db.commit()
        return {"status": "updated", "message": "Admin password reset to admin123"}
    admin = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@anistito.ir",
        hashed_password=get_password_hash("admin123"),
        full_name_fa="مدیر سیستم",
        role="admin",
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    return {"status": "created", "message": "Admin user created: username=admin, password=admin123"}
