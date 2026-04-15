"""Operator API: provision Alocom class for a therapy session."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_role
from app.config import get_settings
from app.database import get_db
from app.models.operational_models import TherapySession, User
from app.services.alocom_client import AlocomAPIError
from app.services.alocom_provision import provision_therapy_session_alocom

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/alocom", tags=["Alocom"])


def _can_access_session(user: User, session: TherapySession) -> bool:
    if user.role in ("admin", "staff"):
        return True
    if user.role == "therapist" and session.therapist_id == user.id:
        return True
    return False


class AlocomProvisionBody(BaseModel):
    agent_service_id: int = Field(..., ge=1)
    title: Optional[str] = Field(None, max_length=500)
    duration_minutes: Optional[int] = Field(None, ge=1, le=24 * 60)
    start_by_admin: int = Field(1, ge=0, le=1)
    fetch_student_event_link: bool = True


@router.post("/therapy-sessions/{session_id}/provision")
async def provision_therapy_session(
    session_id: str,
    body: AlocomProvisionBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff", "therapist")),
):
    settings = get_settings()
    if not settings.ALOCOM_ENABLED:
        raise HTTPException(status_code=503, detail="یکپارچه‌سازی الوکام غیرفعال است (ALOCOM_ENABLED=false).")
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسهٔ جلسه نامعتبر است.")
    r = await db.execute(select(TherapySession).where(TherapySession.id == sid))
    session = r.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="جلسه یافت نشد.")
    if not _can_access_session(current_user, session):
        raise HTTPException(status_code=403, detail="دسترسی به این جلسه ندارید.")

    title = body.title or "کلاس آنلاین"
    try:
        detail = await provision_therapy_session_alocom(
            db,
            session=session,
            agent_service_id=body.agent_service_id,
            title=title,
            duration_minutes=body.duration_minutes,
            start_by_admin=body.start_by_admin,
            fetch_student_event_link=body.fetch_student_event_link,
        )
    except AlocomAPIError as e:
        logger.warning("Alocom provision failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e) or "خطای وب‌سرویس الوکام")

    return {"ok": True, **detail}
