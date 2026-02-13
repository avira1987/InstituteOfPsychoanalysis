"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import (
    Token, UserCreate, UserResponse,
    authenticate_user, create_user, create_access_token,
    get_current_user, require_role,
)
from app.models.operational_models import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and get an access token."""
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
