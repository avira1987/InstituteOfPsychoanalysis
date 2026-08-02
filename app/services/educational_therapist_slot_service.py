"""شیت وقت‌های آزاد درمانگران آموزشی — CRUD، رزرو و آزادسازی."""

from __future__ import annotations

import logging
import uuid
from datetime import time
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.operational_models import EducationalTherapistSlot, Student, User
from app.services.return_to_full_education_service import validate_weekly_sessions

logger = logging.getLogger(__name__)

DAY_LABELS_FA = (
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنج‌شنبه",
    "جمعه",
    "شنبه",
    "یکشنبه",
)

SLOT_MANAGE_ROLES = frozenset(
    {"admin", "staff", "site_manager", "therapy_education_coordinator", "deputy_education"}
)


def day_label_fa(day_of_week: int) -> str:
    if 0 <= day_of_week <= 6:
        return DAY_LABELS_FA[day_of_week]
    return str(day_of_week)


def _format_time(t: time) -> str:
    return t.strftime("%H:%M") if t else ""


def _parse_slot_ids(raw: Any) -> list[uuid.UUID]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    if not isinstance(raw, list):
        return []
    out: list[uuid.UUID] = []
    for item in raw:
        try:
            out.append(uuid.UUID(str(item)))
        except (TypeError, ValueError):
            continue
    return out


def _slot_matches_course(slot: EducationalTherapistSlot, course_type: str | None) -> bool:
    if not slot.course_type:
        return True
    if not course_type:
        return True
    return slot.course_type == course_type


def slot_to_dict(slot: EducationalTherapistSlot, *, therapist_name: str | None = None) -> dict[str, Any]:
    return {
        "id": str(slot.id),
        "therapist_user_id": str(slot.therapist_user_id),
        "therapist_name_fa": therapist_name,
        "day_of_week": slot.day_of_week,
        "day_label_fa": day_label_fa(slot.day_of_week),
        "start_local_time": _format_time(slot.start_local_time),
        "end_local_time": _format_time(slot.end_local_time),
        "course_type": slot.course_type,
        "label_fa": slot.label_fa,
        "status": slot.status,
        "assigned_student_id": str(slot.assigned_student_id) if slot.assigned_student_id else None,
        "assigned_instance_id": str(slot.assigned_instance_id) if slot.assigned_instance_id else None,
    }


async def list_slots_for_manage(
    db: AsyncSession,
    *,
    include_booked: bool = True,
    therapist_user_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(EducationalTherapistSlot, User.full_name_fa, User.full_name_en)
        .join(User, EducationalTherapistSlot.therapist_user_id == User.id)
        .order_by(
            User.full_name_fa.asc(),
            EducationalTherapistSlot.day_of_week.asc(),
            EducationalTherapistSlot.start_local_time.asc(),
        )
    )
    if not include_booked:
        stmt = stmt.where(EducationalTherapistSlot.status == "free")
    if therapist_user_id:
        stmt = stmt.where(EducationalTherapistSlot.therapist_user_id == therapist_user_id)
    rows = (await db.execute(stmt)).all()
    out: list[dict[str, Any]] = []
    for slot, name_fa, name_en in rows:
        label = (name_fa or name_en or "").strip() or str(slot.therapist_user_id)
        out.append(slot_to_dict(slot, therapist_name=label))
    return out


async def list_available_grouped_by_therapist(
    db: AsyncSession,
    *,
    course_type: str | None = None,
) -> dict[str, Any]:
    stmt = (
        select(EducationalTherapistSlot, User)
        .join(User, EducationalTherapistSlot.therapist_user_id == User.id)
        .where(
            EducationalTherapistSlot.status == "free",
            User.role == "therapist",
            User.is_active.is_(True),
        )
        .order_by(
            User.full_name_fa.asc(),
            EducationalTherapistSlot.day_of_week.asc(),
            EducationalTherapistSlot.start_local_time.asc(),
        )
    )
    rows = (await db.execute(stmt)).all()
    grouped: dict[str, dict[str, Any]] = {}
    for slot, user in rows:
        if not _slot_matches_course(slot, course_type):
            continue
        tid = str(user.id)
        if tid not in grouped:
            name = (user.full_name_fa or user.full_name_en or user.phone or tid).strip()
            grouped[tid] = {
                "id": tid,
                "label_fa": name,
                "slots": [],
            }
        grouped[tid]["slots"].append(slot_to_dict(slot, therapist_name=grouped[tid]["label_fa"]))
    therapists = [v for v in grouped.values() if v["slots"]]
    return {"therapists": therapists}


async def create_slot(
    db: AsyncSession,
    *,
    therapist_user_id: uuid.UUID,
    day_of_week: int,
    start_local_time: time,
    end_local_time: time,
    course_type: str | None = None,
    label_fa: str | None = None,
    created_by: uuid.UUID | None = None,
) -> EducationalTherapistSlot:
    if not (0 <= day_of_week <= 6):
        raise ValueError("روز هفته نامعتبر است.")
    if start_local_time >= end_local_time:
        raise ValueError("ساعت پایان باید بعد از ساعت شروع باشد.")
    user = await db.get(User, therapist_user_id)
    if not user or user.role != "therapist":
        raise ValueError("درمانگر آموزشی معتبر یافت نشد.")
    slot = EducationalTherapistSlot(
        id=uuid.uuid4(),
        therapist_user_id=therapist_user_id,
        day_of_week=day_of_week,
        start_local_time=start_local_time,
        end_local_time=end_local_time,
        course_type=course_type or None,
        label_fa=(label_fa or "").strip() or None,
        status="free",
        created_by=created_by,
    )
    db.add(slot)
    await db.flush()
    return slot


async def update_slot(
    db: AsyncSession,
    slot_id: uuid.UUID,
    *,
    day_of_week: int | None = None,
    start_local_time: time | None = None,
    end_local_time: time | None = None,
    course_type: str | None = None,
    label_fa: str | None = None,
) -> EducationalTherapistSlot:
    slot = await db.get(EducationalTherapistSlot, slot_id)
    if not slot:
        raise ValueError("اسلات یافت نشد.")
    if slot.status != "free":
        raise ValueError("فقط اسلات‌های آزاد قابل ویرایش هستند.")
    if day_of_week is not None:
        if not (0 <= day_of_week <= 6):
            raise ValueError("روز هفته نامعتبر است.")
        slot.day_of_week = day_of_week
    if start_local_time is not None:
        slot.start_local_time = start_local_time
    if end_local_time is not None:
        slot.end_local_time = end_local_time
    if slot.start_local_time >= slot.end_local_time:
        raise ValueError("ساعت پایان باید بعد از ساعت شروع باشد.")
    if course_type is not None:
        slot.course_type = course_type or None
    if label_fa is not None:
        slot.label_fa = (label_fa or "").strip() or None
    await db.flush()
    return slot


async def delete_slot(db: AsyncSession, slot_id: uuid.UUID) -> None:
    slot = await db.get(EducationalTherapistSlot, slot_id)
    if not slot:
        raise ValueError("اسلات یافت نشد.")
    if slot.status != "free":
        raise ValueError("فقط اسلات‌های آزاد قابل حذف هستند.")
    await db.delete(slot)
    await db.flush()


async def release_slots(
    db: AsyncSession,
    *,
    student_id: uuid.UUID | None = None,
    instance_id: uuid.UUID | None = None,
    slot_ids: list[uuid.UUID] | None = None,
    therapist_user_id: uuid.UUID | None = None,
) -> int:
    stmt = select(EducationalTherapistSlot).where(EducationalTherapistSlot.status == "booked")
    if slot_ids:
        stmt = stmt.where(EducationalTherapistSlot.id.in_(slot_ids))
    else:
        filters = []
        if student_id:
            filters.append(EducationalTherapistSlot.assigned_student_id == student_id)
        if instance_id:
            filters.append(EducationalTherapistSlot.assigned_instance_id == instance_id)
        if therapist_user_id:
            filters.append(EducationalTherapistSlot.therapist_user_id == therapist_user_id)
        if not filters:
            return 0
        stmt = stmt.where(or_(*filters))
    rows = (await db.execute(stmt)).scalars().all()
    for slot in rows:
        slot.status = "free"
        slot.assigned_student_id = None
        slot.assigned_instance_id = None
    if rows:
        await db.flush()
    return len(rows)


async def book_slots_for_student(
    db: AsyncSession,
    *,
    slot_ids: list[uuid.UUID],
    therapist_user_id: uuid.UUID,
    student_id: uuid.UUID,
    instance_id: uuid.UUID,
    course_type: str,
    weekly_sessions: int,
) -> list[EducationalTherapistSlot]:
    err = validate_weekly_sessions(course_type, weekly_sessions)
    if err:
        raise ValueError(err)
    if len(slot_ids) != weekly_sessions:
        raise ValueError(
            f"تعداد اسلات انتخابی ({len(slot_ids)}) با تعداد جلسات هفتگی ({weekly_sessions}) هم‌خوان نیست."
        )
    if not slot_ids:
        raise ValueError("حداقل یک اسلات هفتگی انتخاب کنید.")

    stmt = (
        select(EducationalTherapistSlot)
        .where(EducationalTherapistSlot.id.in_(slot_ids))
        .options(selectinload(EducationalTherapistSlot.therapist))
    )
    slots = (await db.execute(stmt)).scalars().all()
    if len(slots) != len(slot_ids):
        raise ValueError("برخی از اسلات‌های انتخابی یافت نشدند.")

    therapist_ids = {s.therapist_user_id for s in slots}
    if len(therapist_ids) != 1 or therapist_user_id not in therapist_ids:
        raise ValueError("همهٔ اسلات‌ها باید متعلق به یک درمانگر باشند.")

    for slot in slots:
        if slot.status != "free":
            raise ValueError(f"اسلات {day_label_fa(slot.day_of_week)} {_format_time(slot.start_local_time)} دیگر آزاد نیست.")
        if not _slot_matches_course(slot, course_type):
            raise ValueError("اسلات انتخابی با نوع دورهٔ شما سازگار نیست.")

    for slot in slots:
        slot.status = "booked"
        slot.assigned_student_id = student_id
        slot.assigned_instance_id = instance_id
    await db.flush()
    return slots


async def book_slots_from_context(
    db: AsyncSession,
    *,
    instance_id: uuid.UUID,
    student_id: uuid.UUID,
    context: dict[str, Any],
    therapist_id_key: str = "therapist_id",
    slot_ids_key: str = "slot_ids",
    weekly_sessions_key: str = "weekly_sessions",
) -> str:
    """رزرو اسلات‌ها از context فرم — برای اکشن‌های فرایند."""
    slot_ids = _parse_slot_ids(context.get(slot_ids_key))
    if not slot_ids:
        return "skip_no_slot_ids"

    tid_raw = context.get(therapist_id_key) or context.get("new_therapist_id")
    if not tid_raw:
        raise ValueError("درمانگر انتخاب نشده است.")
    try:
        therapist_user_id = uuid.UUID(str(tid_raw))
    except (TypeError, ValueError) as e:
        raise ValueError("شناسهٔ درمانگر نامعتبر است.") from e

    student = await db.get(Student, student_id)
    if not student:
        raise ValueError("دانشجو یافت نشد.")
    course_type = str(student.course_type or "introductory")
    try:
        weekly = int(context.get(weekly_sessions_key) or len(slot_ids))
    except (TypeError, ValueError):
        weekly = len(slot_ids)

    booked = await book_slots_for_student(
        db,
        slot_ids=slot_ids,
        therapist_user_id=therapist_user_id,
        student_id=student_id,
        instance_id=instance_id,
        course_type=course_type,
        weekly_sessions=weekly,
    )
    return f"booked_slots={len(booked)}"


def build_slot_summary_for_context(slots: list[EducationalTherapistSlot]) -> dict[str, Any]:
    return {
        "slot_ids": [str(s.id) for s in slots],
        "selected_slots_summary_fa": [
            f"{day_label_fa(s.day_of_week)} {_format_time(s.start_local_time)}–{_format_time(s.end_local_time)}"
            for s in slots
        ],
    }
