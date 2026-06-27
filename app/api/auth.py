"""Authentication and RBAC middleware."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.operational_models import User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# ارقام فارسی/عربی → لاتین (ورود با کیبورد فارسی)
_LOGIN_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_login_field(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().translate(_LOGIN_DIGIT_MAP)


# ─── Schemas ────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    password: str
    full_name_fa: Optional[str] = None
    role: str = "student"
    email: Optional[str] = None
    phone: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    username: str
    full_name_fa: Optional[str] = None
    full_name_en: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_active: bool
    primary_site_admin: bool = False

    model_config = {"from_attributes": True}


def user_to_response(user: User) -> UserResponse:
    """JSON پروفایل کاربر؛ primary_site_admin فقط برای مدیر سیستم با نام کاربری تنظیم‌شده."""
    flag = user.role == "admin" and user.username == get_settings().PRIMARY_SITE_ADMIN_USERNAME
    return UserResponse(
        id=str(user.id),
        username=user.username,
        full_name_fa=user.full_name_fa,
        full_name_en=user.full_name_en,
        email=user.email,
        phone=user.phone,
        avatar_url=user.avatar_url,
        role=user.role,
        is_active=user.is_active,
        primary_site_admin=flag,
    )


# ─── Utility Functions ──────────────────────────────────────────

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError, Exception):
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ─── Dependency Functions ───────────────────────────────────────

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get the current user if authenticated, None otherwise."""
    if token is None:
        return None
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


def require_role(*roles: str):
    """Dependency factory that requires the user to have one of the specified roles."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized. Required: {', '.join(roles)}",
            )
        return current_user
    return role_checker


async def require_primary_site_admin(current_user: User = Depends(get_current_user)) -> User:
    """فقط مدیر سیستم با نام کاربری PRIMARY_SITE_ADMIN_USERNAME."""
    s = get_settings()
    if current_user.role != "admin" or current_user.username != s.PRIMARY_SITE_ADMIN_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط مدیر اصلی سامانه به این بخش دسترسی دارد.",
        )
    return current_user


async def require_admin_only(current_user: User = Depends(get_current_user)) -> User:
    """هر حساب با نقش admin (صندوق پیگیری سراسری، گزارش‌های مدیریتی، …)."""
    if (current_user.role or "").strip() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط مدیر سیستم به این بخش دسترسی دارد.",
        )
    return current_user


# ─── Auth Service ───────────────────────────────────────────────

async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[User]:
    """Authenticate a user by username and password."""
    from app.demo_role_users import resolve_portal_login_username

    resolved = resolve_portal_login_username(normalize_login_field(username))
    password = normalize_login_field(password)
    stmt = select(User).where(User.username == resolved)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """Create a new user."""
    user = User(
        id=uuid.uuid4(),
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        portal_password_plain=None,
        full_name_fa=user_data.full_name_fa,
        role=user_data.role,
        phone=user_data.phone,
    )
    db.add(user)
    return user
