"""Authentication API routes."""

import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger(__name__)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.api.auth import (
    Token, UserCreate, UserResponse,
    authenticate_user, create_user, create_access_token,
    get_password_hash,
    get_current_user, require_role,
)
from pydantic import BaseModel
from app.models.operational_models import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


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


@router.post("/login-json", response_model=Token)
async def login_json(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with JSON body (alternative to form for debugging)."""
    if not body.username or not body.password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    try:
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
        role=current_user.role,
        is_active=current_user.is_active,
    )


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
