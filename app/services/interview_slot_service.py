"""رزرو اسلات مصاحبه و اتصال به ترنزیشن فرایند ثبت‌نام."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.engine import StateMachineEngine, InvalidTransitionError
from app.models.operational_models import InterviewSlot, ProcessInstance, Student, User


def _slot_payload(slot: InterviewSlot) -> dict[str, Any]:
    st = slot.starts_at
    if st.tzinfo is None:
        st = st.replace(tzinfo=timezone.utc)
    interview_type = "online" if slot.mode == "online" else "in_person"
    loc = (slot.location_fa or "").strip() or ("لینک آنلاین" if slot.mode == "online" else "انستیتو")
    link = (slot.meeting_link or "").strip()
    return {
        "selected_timeslot": str(slot.id),
        "interview_date": st.date().isoformat(),
        "interview_time": st.strftime("%H:%M"),
        "interview_type": interview_type,
        "interview_location_or_link": link or loc,
        "notes": "رزرو از طریق اسلات سامانه",
    }


def _resolve_trigger(process_code: str, current_state: str) -> Optional[str]:
    if process_code == "introductory_course_registration" and current_state == "application_submitted":
        return "timeslot_selected"
    if process_code == "comprehensive_course_registration" and current_state == "interview_scheduled":
        return "interview_time_selected"
    return None


async def book_slot_for_registration(
    db: AsyncSession,
    *,
    user: User,
    instance_id: uuid.UUID,
    slot_id: uuid.UUID,
) -> dict[str, Any]:
    """یک اسلات را به نمونهٔ فرایند ثبت‌نام دانشجو وصل می‌کند و ترنزیشن را اجرا می‌کند."""
    stmt_st = select(Student).where(Student.user_id == user.id)
    student = (await db.execute(stmt_st)).scalars().first()
    if not student:
        return {"success": False, "error": "پروفایل دانشجویی یافت نشد."}

    stmt_i = (
        select(ProcessInstance)
        .where(ProcessInstance.id == instance_id)
        .options(selectinload(ProcessInstance.student))
    )
    instance = (await db.execute(stmt_i)).scalars().first()
    if not instance:
        return {"success": False, "error": "فرایند یافت نشد."}
    if instance.student_id != student.id:
        return {"success": False, "error": "این فرایند متعلق به شما نیست."}
    if instance.is_completed or instance.is_cancelled:
        return {"success": False, "error": "این فرایند دیگر فعال نیست."}

    trigger = _resolve_trigger(instance.process_code, instance.current_state_code)
    if not trigger:
        return {
            "success": False,
            "error": "در این مرحله امکان رزرو اسلات از سامانه پیش‌بینی نشده است.",
        }

    stmt_slot = select(InterviewSlot).where(InterviewSlot.id == slot_id).with_for_update()
    slot = (await db.execute(stmt_slot)).scalars().first()
    if not slot:
        return {"success": False, "error": "اسلات یافت نشد."}

    now = datetime.now(timezone.utc)
    if slot.ends_at <= now:
        return {"success": False, "error": "این زمان مصاحبه دیگر معتبر نیست."}
    if slot.assigned_student_id is not None:
        return {"success": False, "error": "این زمان قبلاً رزرو شده است."}

    ct = slot.course_type
    if ct:
        st_ct = (student.course_type or "").lower()
        if st_ct and ct != st_ct:
            return {"success": False, "error": "این اسلات برای نوع دورهٔ دیگری تعریف شده است."}

    payload = _slot_payload(slot)
    slot.assigned_student_id = student.id
    slot.assigned_instance_id = instance.id
    await db.flush()

    engine = StateMachineEngine(db)
    try:
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event=trigger,
            actor_id=user.id,
            actor_role=user.role or "student",
            payload=payload,
        )
    except InvalidTransitionError as e:
        slot.assigned_student_id = None
        slot.assigned_instance_id = None
        await db.flush()
        return {"success": False, "error": str(e)}

    if not result.success:
        slot.assigned_student_id = None
        slot.assigned_instance_id = None
        await db.flush()
        return {"success": False, "error": result.error or "انتقال فرایند انجام نشد."}

    await db.refresh(instance)
    await db.refresh(slot)
    return {
        "success": True,
        "instance_id": str(instance.id),
        "current_state": instance.current_state_code,
        "slot_id": str(slot.id),
    }
