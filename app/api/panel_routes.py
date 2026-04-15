"""پنل نقش‌ها — صف اقدامات پیشنهادی برای UI و اتوماسیون."""

from fastapi import APIRouter, Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.meta.student_lifecycle_matrix import get_panel_action_queue_for_role
from app.models.operational_models import User
from app.services.nav_pending_counts import compute_nav_pending_counts

router = APIRouter(prefix="/api/panel", tags=["Panel"])


@router.get("/action-queue")
async def panel_action_queue(user: User = Depends(get_current_user)):
    """اقدامات منتظر انجام (الگوی نقش + فرایندهای رجیستری مرتبط) — نیاز به JWT."""
    return get_panel_action_queue_for_role(user.role)


@router.get("/nav-pending-counts")
async def panel_nav_pending_counts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    شمارش کارهای منتظر برای آیتم‌های منو (همان منطق پنل‌های نقش + تیکت‌های باز/در حال رسیدگی).
    """
    return await compute_nav_pending_counts(db, user)
