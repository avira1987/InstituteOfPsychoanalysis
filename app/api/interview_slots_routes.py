"""API اسلات‌های مصاحبه — تعریف (کارمند/مدیر سایت) و رزرو (دانشجو)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_role
from app.database import get_db
from app.models.operational_models import InterviewSlot, ProcessInstance, Student, User
from app.services.interview_slot_service import book_slot_for_registration

router = APIRouter(prefix="/api/interview-slots", tags=["Interview slots"])

MANAGE_ROLES = ("admin", "staff", "site_manager", "deputy_education")
BOOKINGS_ROLES = ("interviewer", "admin", "staff", "site_manager", "deputy_education")


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _slot_to_dict(s: InterviewSlot) -> dict:
    return {
        "id": str(s.id),
        "starts_at": _iso(s.starts_at),
        "ends_at": _iso(s.ends_at),
        "course_type": s.course_type,
        "mode": s.mode,
        "location_fa": s.location_fa,
        "meeting_link": s.meeting_link,
        "label_fa": s.label_fa,
        "assigned_student_id": str(s.assigned_student_id) if s.assigned_student_id else None,
        "assigned_instance_id": str(s.assigned_instance_id) if s.assigned_instance_id else None,
        "reminder_sent_at": _iso(s.reminder_sent_at),
        "created_at": _iso(s.created_at),
    }


class CreateInterviewSlotBody(BaseModel):
    starts_at: datetime
    ends_at: datetime
    course_type: Optional[Literal["introductory", "comprehensive"]] = None
    mode: Literal["in_person", "online"] = "in_person"
    location_fa: Optional[str] = None
    meeting_link: Optional[str] = None
    label_fa: Optional[str] = None


class BookInterviewSlotBody(BaseModel):
    instance_id: str = Field(..., min_length=1)
    slot_id: str = Field(..., min_length=1)


@router.get("/available")
async def list_available_slots(
    course_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    """اسلات‌های آینده بدون تخصیص؛ اختیاری فیلتر نوع دوره."""
    now = datetime.now(timezone.utc)
    stmt = select(InterviewSlot).where(
        InterviewSlot.starts_at > now,
        InterviewSlot.assigned_student_id.is_(None),
    )
    if course_type in ("introductory", "comprehensive"):
        stmt = stmt.where(
            or_(
                InterviewSlot.course_type.is_(None),
                InterviewSlot.course_type == course_type,
            )
        )
    stmt = stmt.order_by(InterviewSlot.starts_at)
    rows = (await db.execute(stmt)).scalars().all()
    return {"slots": [_slot_to_dict(s) for s in rows]}


@router.get("/bookings")
async def list_booked_slots_with_students(
    include_past: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*BOOKINGS_ROLES)),
):
    """اسلات‌های رزروشده همراه اطلاعات دانشجو و نمونهٔ فرایند — برای مصاحبه‌گر و دفتر."""
    now = datetime.now(timezone.utc)
    stmt = (
        select(InterviewSlot, Student, User, ProcessInstance)
        .join(Student, InterviewSlot.assigned_student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .outerjoin(ProcessInstance, InterviewSlot.assigned_instance_id == ProcessInstance.id)
        .where(InterviewSlot.assigned_student_id.isnot(None))
    )
    if not include_past:
        stmt = stmt.where(InterviewSlot.ends_at >= now)
    stmt = stmt.order_by(InterviewSlot.starts_at)
    rows = (await db.execute(stmt)).all()
    out: list[dict] = []
    for slot, student, u, inst in rows:
        item = {
            "slot": _slot_to_dict(slot),
            "student": {
                "id": str(student.id),
                "student_code": student.student_code,
                "course_type": student.course_type,
                "full_name_fa": (u.full_name_fa or "").strip() or None,
                "phone": (u.phone or "").strip() or None,
                "email": (u.email or "").strip() or None,
            },
            "instance": None
            if not inst
            else {
                "id": str(inst.id),
                "process_code": inst.process_code,
                "current_state": inst.current_state_code,
            },
        }
        out.append(item)
    return {"bookings": out}


@router.get("/manage")
async def list_slots_manage(
    include_past: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*MANAGE_ROLES)),
):
    """فهرست همهٔ اسلات‌ها برای پنل کارمند."""
    now = datetime.now(timezone.utc)
    stmt = select(InterviewSlot)
    if not include_past:
        stmt = stmt.where(InterviewSlot.ends_at >= now)
    stmt = stmt.order_by(InterviewSlot.starts_at)
    rows = (await db.execute(stmt)).scalars().all()
    return {"slots": [_slot_to_dict(s) for s in rows]}


@router.post("/manage")
async def create_slot(
    body: CreateInterviewSlotBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*MANAGE_ROLES)),
):
    if body.ends_at <= body.starts_at:
        raise HTTPException(status_code=400, detail="زمان پایان باید بعد از شروع باشد.")
    now = datetime.now(timezone.utc)
    if body.ends_at <= now:
        raise HTTPException(status_code=400, detail="بازه باید در آینده باشد.")

    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=body.starts_at if body.starts_at.tzinfo else body.starts_at.replace(tzinfo=timezone.utc),
        ends_at=body.ends_at if body.ends_at.tzinfo else body.ends_at.replace(tzinfo=timezone.utc),
        course_type=body.course_type,
        mode=body.mode,
        location_fa=(body.location_fa or "").strip() or None,
        meeting_link=(body.meeting_link or "").strip() or None,
        label_fa=(body.label_fa or "").strip() or None,
        created_by=user.id,
    )
    db.add(slot)
    await db.flush()
    return _slot_to_dict(slot)


@router.delete("/manage/{slot_id}")
async def delete_slot(
    slot_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*MANAGE_ROLES)),
):
    try:
        sid = uuid.UUID(slot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسه نامعتبر")
    stmt = select(InterviewSlot).where(InterviewSlot.id == sid)
    slot = (await db.execute(stmt)).scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="اسلات یافت نشد")
    if slot.assigned_student_id is not None:
        raise HTTPException(status_code=400, detail="اسلات رزروشده قابل حذف نیست.")
    await db.delete(slot)
    return {"success": True}


@router.post("/book")
async def book_slot(
    body: BookInterviewSlotBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    try:
        iid = uuid.UUID(body.instance_id)
        sid = uuid.UUID(body.slot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسه نامعتبر")
    out = await book_slot_for_registration(db, user=user, instance_id=iid, slot_id=sid)
    if not out.get("success"):
        raise HTTPException(status_code=400, detail=out.get("error") or "رزرو انجام نشد")
    return out
