"""API شیت وقت‌های آزاد درمانگران آموزشی."""

from __future__ import annotations

import logging
import uuid
from datetime import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_role
from app.database import get_db
from app.models.operational_models import EducationalTherapistSlot, Student, User
from app.services.educational_therapist_slot_service import (
    SLOT_MANAGE_ROLES,
    book_slots_for_student,
    create_slot,
    delete_slot,
    list_available_grouped_by_therapist,
    list_slots_for_manage,
    release_slots,
    slot_to_dict,
    update_slot,
)

router = APIRouter(prefix="/api/educational-therapist-slots", tags=["Educational therapist slots"])
logger = logging.getLogger(__name__)


def _can_manage_slots(user: User) -> bool:
    return (user.role or "").strip() in SLOT_MANAGE_ROLES


def _parse_time_hm(val: str) -> time:
    parts = (val or "").strip().split(":")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="فرمت ساعت نامعتبر است (HH:MM).")
    try:
        return time(int(parts[0]), int(parts[1]))
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail="فرمت ساعت نامعتبر است.") from e


class CreateSlotBody(BaseModel):
    therapist_user_id: str
    day_of_week: int = Field(ge=0, le=6)
    start_local_time: str
    end_local_time: str
    course_type: Optional[Literal["introductory", "comprehensive"]] = None
    label_fa: Optional[str] = None


class UpdateSlotBody(BaseModel):
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_local_time: Optional[str] = None
    end_local_time: Optional[str] = None
    course_type: Optional[Literal["introductory", "comprehensive", ""]] = None
    label_fa: Optional[str] = None


class BookSlotsBody(BaseModel):
    instance_id: str
    therapist_user_id: str
    slot_ids: list[str]
    weekly_sessions: Optional[int] = None


@router.get("/available")
async def get_available_slots(
    course_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "admin", "staff", "therapist", "site_manager")),
):
    """اسلات‌های آزاد گروه‌بندی‌شده بر درمانگر — برای انتخاب دانشجو."""
    ct = (course_type or "").strip() or None
    if current_user.role == "student":
        stmt = select(Student).where(Student.user_id == current_user.id)
        student = (await db.execute(stmt)).scalars().first()
        if student and student.course_type:
            ct = student.course_type
    return await list_available_grouped_by_therapist(db, course_type=ct)


@router.get("/manage")
async def manage_list_slots(
    include_booked: bool = True,
    therapist_user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_slots(current_user):
        raise HTTPException(status_code=403, detail="دسترسی مدیریت شیت وقت آزاد ندارید.")
    tid = None
    if therapist_user_id:
        try:
            tid = uuid.UUID(therapist_user_id)
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail="شناسهٔ درمانگر نامعتبر است.") from e
    slots = await list_slots_for_manage(db, include_booked=include_booked, therapist_user_id=tid)
    return {"slots": slots}


@router.post("/manage")
async def manage_create_slot(
    body: CreateSlotBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_slots(current_user):
        raise HTTPException(status_code=403, detail="دسترسی مدیریت شیت وقت آزاد ندارید.")
    try:
        tid = uuid.UUID(body.therapist_user_id)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail="شناسهٔ درمانگر نامعتبر است.") from e
    try:
        slot = await create_slot(
            db,
            therapist_user_id=tid,
            day_of_week=body.day_of_week,
            start_local_time=_parse_time_hm(body.start_local_time),
            end_local_time=_parse_time_hm(body.end_local_time),
            course_type=body.course_type,
            label_fa=body.label_fa,
            created_by=current_user.id,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"slot": slot_to_dict(slot)}


@router.patch("/manage/{slot_id}")
async def manage_update_slot(
    slot_id: str,
    body: UpdateSlotBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_slots(current_user):
        raise HTTPException(status_code=403, detail="دسترسی مدیریت شیت وقت آزاد ندارید.")
    try:
        sid = uuid.UUID(slot_id)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail="شناسهٔ اسلات نامعتبر است.") from e
    try:
        slot = await update_slot(
            db,
            sid,
            day_of_week=body.day_of_week,
            start_local_time=_parse_time_hm(body.start_local_time) if body.start_local_time else None,
            end_local_time=_parse_time_hm(body.end_local_time) if body.end_local_time else None,
            course_type=body.course_type if body.course_type is not None else None,
            label_fa=body.label_fa,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"slot": slot_to_dict(slot)}


@router.delete("/manage/{slot_id}")
async def manage_delete_slot(
    slot_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_slots(current_user):
        raise HTTPException(status_code=403, detail="دسترسی مدیریت شیت وقت آزاد ندارید.")
    try:
        sid = uuid.UUID(slot_id)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail="شناسهٔ اسلات نامعتبر است.") from e
    try:
        await delete_slot(db, sid)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.post("/manage/{slot_id}/release")
async def manage_release_slot(
    slot_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_manage_slots(current_user):
        raise HTTPException(status_code=403, detail="دسترسی مدیریت شیت وقت آزاد ندارید.")
    try:
        sid = uuid.UUID(slot_id)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail="شناسهٔ اسلات نامعتبر است.") from e
    n = await release_slots(db, slot_ids=[sid])
    await db.commit()
    return {"released": n}


@router.post("/book")
async def book_educational_therapist_slots(
    body: BookSlotsBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("student", "admin", "staff")),
):
    """رزرو اسلات‌های هفتگی برای فرایند انتخاب درمانگر."""
    try:
        instance_id = uuid.UUID(body.instance_id)
        therapist_user_id = uuid.UUID(body.therapist_user_id)
        slot_ids = [uuid.UUID(x) for x in body.slot_ids]
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail="شناسه‌های ورودی نامعتبر است.") from e

    from app.models.operational_models import ProcessInstance

    instance = await db.get(ProcessInstance, instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="نمونهٔ فرایند یافت نشد.")

    if current_user.role == "student":
        stmt = select(Student).where(Student.user_id == current_user.id)
        student = (await db.execute(stmt)).scalars().first()
        if not student or student.id != instance.student_id:
            raise HTTPException(status_code=403, detail="این فرایند متعلق به شما نیست.")

    student = await db.get(Student, instance.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="دانشجو یافت نشد.")

    course_type = str(student.course_type or "introductory")
    weekly = body.weekly_sessions
    if weekly is None:
        weekly = len(slot_ids)

    try:
        booked = await book_slots_for_student(
            db,
            slot_ids=slot_ids,
            therapist_user_id=therapist_user_id,
            student_id=student.id,
            instance_id=instance_id,
            course_type=course_type,
            weekly_sessions=weekly,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    from app.services.educational_therapist_slot_service import build_slot_summary_for_context

    return {"ok": True, **build_slot_summary_for_context(booked)}
