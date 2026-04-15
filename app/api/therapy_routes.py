"""Therapy session URLs and instructor feedback — therapist + student + staff."""

import uuid
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user, require_role
from app.models.operational_models import User, Student, TherapySession
from app.services.attendance_service import AttendanceService
from app.services.attendance_tracking_sync import apply_therapy_attendance_via_process

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/therapy-sessions", tags=["TherapySessions"])


def _can_write_session(user: User, session: TherapySession) -> bool:
    if user.role in ("admin", "staff"):
        return True
    if user.role == "therapist" and session.therapist_id == user.id:
        return True
    return False


class TherapySessionOut(BaseModel):
    id: str
    student_id: str
    therapist_id: Optional[str]
    session_date: str
    session_number: Optional[int]
    status: str
    payment_status: str
    meeting_url: Optional[str]
    meeting_provider: Optional[str]
    links_unlocked: bool
    instructor_score: Optional[float]
    instructor_comment: Optional[str]
    notes: Optional[str]
    alocom_event_id: Optional[str] = None
    session_starts_at: Optional[str] = None


class TherapySessionPatch(BaseModel):
    meeting_url: Optional[str] = None
    meeting_provider: Optional[str] = Field(
        None,
        description="manual | skyroom | voicoom | alocom",
    )
    instructor_score: Optional[float] = None
    instructor_comment: Optional[str] = None
    links_unlocked: Optional[bool] = None
    attendance_status: Optional[Literal["present", "absent_excused", "absent_unexcused"]] = Field(
        None,
        description="ثبت حضور/غیاب و هم‌ترازی وضعیت جلسه",
    )


def _to_out(s: TherapySession) -> dict:
    starts = s.session_starts_at.isoformat() if getattr(s, "session_starts_at", None) else None
    return {
        "id": str(s.id),
        "student_id": str(s.student_id),
        "therapist_id": str(s.therapist_id) if s.therapist_id else None,
        "session_date": s.session_date.isoformat() if s.session_date else "",
        "session_number": s.session_number,
        "status": s.status,
        "payment_status": s.payment_status,
        "meeting_url": s.meeting_url,
        "meeting_provider": s.meeting_provider,
        "links_unlocked": bool(s.links_unlocked),
        "instructor_score": s.instructor_score,
        "instructor_comment": s.instructor_comment,
        "notes": s.notes,
        "alocom_event_id": getattr(s, "alocom_event_id", None),
        "session_starts_at": starts,
    }


@router.get("/me", response_model=list[TherapySessionOut])
async def list_my_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student: own sessions; meeting URL visible only when links_unlocked."""
    stmt = select(Student).where(Student.user_id == current_user.id)
    r = await db.execute(stmt)
    st = r.scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="Student profile not found")
    q = select(TherapySession).where(TherapySession.student_id == st.id).order_by(TherapySession.session_date.desc())
    r2 = await db.execute(q)
    rows = r2.scalars().all()
    out = []
    for s in rows:
        d = _to_out(s)
        if not s.links_unlocked:
            d["meeting_url"] = None
            d["meeting_provider"] = None
            d["alocom_event_id"] = None
        out.append(d)
    return out


@router.get("/for-therapist", response_model=list[TherapySessionOut])
async def list_for_therapist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("therapist", "admin")),
):
    """Therapist: sessions assigned to this user."""
    q = (
        select(TherapySession)
        .where(TherapySession.therapist_id == current_user.id)
        .order_by(TherapySession.session_date.desc())
    )
    r = await db.execute(q)
    return [_to_out(s) for s in r.scalars().all()]


@router.get("/for-student/{student_id}", response_model=list[TherapySessionOut])
async def list_for_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Staff/Admin: all therapy sessions for a student (for class link / Alocom)."""
    try:
        sid = uuid.UUID(student_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسهٔ دانشجو نامعتبر است.")
    q = (
        select(TherapySession)
        .where(TherapySession.student_id == sid)
        .order_by(TherapySession.session_date.desc())
    )
    r = await db.execute(q)
    return [_to_out(s) for s in r.scalars().all()]


@router.patch("/{session_id}", response_model=TherapySessionOut)
async def patch_session(
    session_id: str,
    body: TherapySessionPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("therapist", "admin", "staff")),
):
    sid = uuid.UUID(session_id)
    r = await db.execute(select(TherapySession).where(TherapySession.id == sid))
    s = r.scalars().first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if not _can_write_session(current_user, s):
        raise HTTPException(status_code=403, detail="Not your session")

    data = body.model_dump(exclude_unset=True)
    attendance_status = data.pop("attendance_status", None)

    if attendance_status:
        ok, err = await apply_therapy_attendance_via_process(
            db, s, attendance_status, current_user
        )
        if err == "no_attendance_process":
            att = AttendanceService(db)
            await att.record_attendance(
                student_id=s.student_id,
                session_id=s.id,
                record_date=s.session_date,
                status=attendance_status,
                absence_type=None,
                notes=None,
            )
        elif not ok:
            raise HTTPException(
                status_code=409,
                detail=err or "ثبت حضور از طریق فرایند حضور و غیاب ممکن نشد.",
            )

    for k, v in data.items():
        setattr(s, k, v)
    await db.flush()
    await db.refresh(s)
    logger.info(
        "therapy_session_updated session_id=%s user_id=%s fields=%s",
        session_id,
        str(current_user.id),
        list(body.model_dump(exclude_unset=True).keys()),
    )
    return _to_out(s)
