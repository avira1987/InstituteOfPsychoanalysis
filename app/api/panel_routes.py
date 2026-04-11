"""پنل نقش‌ها — صف اقدامات پیشنهادی برای UI و اتوماسیون."""

from fastapi import APIRouter, Depends

from app.api.auth import get_current_user
from app.meta.student_lifecycle_matrix import get_panel_action_queue_for_role
from app.models.operational_models import User

router = APIRouter(prefix="/api/panel", tags=["Panel"])


@router.get("/action-queue")
async def panel_action_queue(user: User = Depends(get_current_user)):
    """اقدامات منتظر انجام (الگوی نقش + فرایندهای رجیستری مرتبط) — نیاز به JWT."""
    return get_panel_action_queue_for_role(user.role)
