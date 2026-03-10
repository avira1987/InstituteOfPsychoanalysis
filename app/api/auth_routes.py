"""Authentication API routes."""

import logging
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
import random
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

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
    challenge_id: str | None = None
    challenge_answer: str | None = None


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

        # نرمال‌سازی timezone برای جلوگیری از خطای naive/aware
        if challenge and challenge.expires_at is not None:
            expires_at = challenge.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        else:
            expires_at = None

        if (
            not challenge
            or challenge.is_used
            or not expires_at
            or expires_at < now
            or not verify_password(body.challenge_answer.strip(), challenge.answer_hash)
        ):
            raise HTTPException(status_code=400, detail="کد امنیتی نامعتبر است")

        challenge.is_used = True
        await db.commit()

        # سپس اعتبارسنجی نام کاربری/رمز عبور
        user = await authenticate_user(db, body.username, body.password)
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
        full_name_en=current_user.full_name_en,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        role=current_user.role,
        is_active=current_user.is_active,
    )


class UpdateProfileRequest(BaseModel):
    full_name_fa: str | None = None
    full_name_en: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str | None = None  # رمز جدید؛ در صورت ارسال باید با current_password تأیید شود
    current_password: str | None = None  # برای تغییر رمز الزامی است


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user's profile (name, email, phone, password)."""
    if data.full_name_fa is not None:
        current_user.full_name_fa = data.full_name_fa
    if data.full_name_en is not None:
        current_user.full_name_en = data.full_name_en
    if data.email is not None:
        current_user.email = data.email
    if data.phone is not None:
        current_user.phone = data.phone
    if data.password:
        if not data.current_password or not verify_password(data.current_password, current_user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="رمز عبور فعلی نادرست است")
        current_user.hashed_password = get_password_hash(data.password)
    await db.commit()
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        full_name_fa=current_user.full_name_fa,
        full_name_en=current_user.full_name_en,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        role=current_user.role,
        is_active=current_user.is_active,
    )


ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload profile picture for current user."""
    if file.content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فرمت مجاز: JPG، PNG، WebP یا GIF",
        )
    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حداکثر حجم فایل ۵ مگابایت است",
        )
    settings = get_settings()
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    avatars_dir = upload_root / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)
    ext = ".jpg"
    if file.content_type == "image/png":
        ext = ".png"
    elif file.content_type == "image/webp":
        ext = ".webp"
    elif file.content_type == "image/gif":
        ext = ".gif"
    filename = f"{current_user.id}{ext}"
    path = avatars_dir / filename
    path.write_bytes(content)
    current_user.avatar_url = f"/uploads/avatars/{filename}"
    await db.commit()
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        full_name_fa=current_user.full_name_fa,
        full_name_en=current_user.full_name_en,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        role=current_user.role,
        is_active=current_user.is_active,
    )


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
