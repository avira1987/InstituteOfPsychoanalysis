"""API اسلات‌های مصاحبه — تعریف (staff / admin) و رزرو (دانشجو)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_role
from app.config import get_settings
from app.database import get_db
from app.models.operational_models import (
    InterviewSlot,
    InterviewSlotRecurringRule,
    ProcessInstance,
    Student,
    User,
)
from app.services.alocom_interview_provision import ensure_interview_slot_host_meeting_link
from app.services.interview_slot_service import (
    book_slot_for_registration,
    expire_interview_booking_payment_deadlines,
    maybe_provision_interview_slot_alocom_link,
    reschedule_booked_interview_slot,
)
from app.services.interview_slot_recurring_generation import (
    delete_unbooked_future_slots_generated_from_rule,
    generate_interview_slots_from_recurring_rules,
    normalize_rule_weekdays,
)

router = APIRouter(prefix="/api/interview-slots", tags=["Interview slots"])
logger = logging.getLogger(__name__)

# مسئول پذیر و مدیر داخلی (staff) + مدیر سیستم (admin)
SLOT_DEFINE_ROLES = ("staff", "admin")

# مشاهده/عملیات رزرو (بدون تعریف وقت جدید)
BOOKINGS_ROLES = ("interviewer", "admin", "staff", "site_manager", "deputy_education")

# فقط باز/بسته کردن ورود زودهنگام دانشجو روی اسلات رزروشده
BOOKING_SLOT_OPS_ROLES = BOOKINGS_ROLES


def _interviewer_owns_slot(user: User, slot: InterviewSlot) -> bool:
    uid = user.id
    if getattr(slot, "interviewer_user_id", None) == uid:
        return True
    return slot.created_by == uid and getattr(slot, "interviewer_user_id", None) is None


def _interviewer_can_view_booking(user: User, slot: InterviewSlot) -> bool:
    """مصاحبه‌گر: رزروهای اسلات خودش + اسلات‌های عمومی دفتر (بدون مصاحبه‌گر اختصاصی در رکورد)."""
    if _interviewer_owns_slot(user, slot):
        return True
    # اسلات تعریف‌شده توسط ادمین/پذیرش بدون ست کردن interviewer_user_id — رزرو باید برای مصاحبه‌گرها دیده شود.
    return getattr(slot, "interviewer_user_id", None) is None


def _can_define_interview_slots(user: User) -> bool:
    return user.role in SLOT_DEFINE_ROLES


def _can_reschedule_booked_slot(user: User, slot: InterviewSlot) -> bool:
    if user.role in SLOT_DEFINE_ROLES:
        return True
    if user.role == "interviewer":
        return _interviewer_can_view_booking(user, slot)
    return False


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _meeting_link_open_at(slot: InterviewSlot) -> Optional[datetime]:
    if slot.mode != "online" or not slot.starts_at:
        return None
    mins = max(0, int(getattr(get_settings(), "INTERVIEW_ONLINE_LINK_VISIBLE_MINUTES_BEFORE", 30)))
    st = slot.starts_at if slot.starts_at.tzinfo else slot.starts_at.replace(tzinfo=timezone.utc)
    return st - timedelta(minutes=mins)


def _meeting_link_for_viewer(slot: InterviewSlot, user: Optional[User]) -> str:
    """لینک ورود الوکام متناسب با نقش بیننده (participant برای دانشجو، teacher/host برای اپراتور)."""
    student_link = (slot.meeting_link or "").strip()
    host_link = (getattr(slot, "host_meeting_link", None) or "").strip()
    iv_link = (getattr(slot, "interviewer_meeting_link", None) or "").strip()

    if user and user.role == "student":
        return student_link

    if user and user.role == "interviewer" and slot.interviewer_user_id == user.id and iv_link:
        return iv_link

    if host_link and host_link != student_link:
        return host_link
    if iv_link:
        return iv_link
    if host_link:
        return host_link
    return student_link


def _is_meeting_link_visible_for_user(slot: InterviewSlot, user: Optional[User], now: datetime) -> bool:
    if slot.mode != "online":
        return True
    if not _meeting_link_for_viewer(slot, user):
        return False
    if not user:
        return False
    if user.role in ("admin", "staff", "site_manager", "deputy_education"):
        return True
    if user.role == "interviewer":
        open_at = _meeting_link_open_at(slot)
        if open_at is None:
            return True
        return now >= open_at
    if user.role == "student":
        if bool(getattr(slot, "student_join_open", False)):
            return True
        open_at = _meeting_link_open_at(slot)
        if open_at is None:
            return True
        return now >= open_at
    return False


async def _prepare_slot_meeting_links_for_staff(
    db: AsyncSession,
    slot: InterviewSlot,
    *,
    viewer: User,
    instance: Optional[ProcessInstance] = None,
    log_context: str = "slot list",
) -> None:
    """برای نمایش اپراتور: لینک الوکام را در صورت نیاز بسازد و لینک میزبان/مصاحبه‌گر را تضمین کند."""
    if not slot.assigned_student_id:
        return
    if instance is None and slot.assigned_instance_id:
        instance = await db.get(ProcessInstance, slot.assigned_instance_id)
    await maybe_provision_interview_slot_alocom_link(db, slot, instance=instance)
    if viewer.role != "student":
        try:
            await ensure_interview_slot_host_meeting_link(db, slot, viewer=viewer)
        except Exception:
            logger.exception(
                "ensure_interview_slot_host_meeting_link failed slot=%s in %s",
                slot.id,
                log_context,
            )


def _slot_to_dict(s: InterviewSlot, *, viewer: Optional[User] = None, now: Optional[datetime] = None, hide_link: bool = False) -> dict:
    show_link = False
    if not hide_link:
        show_link = _is_meeting_link_visible_for_user(s, viewer, now or datetime.now(timezone.utc))
    open_at = _meeting_link_open_at(s)
    return {
        "id": str(s.id),
        "starts_at": _iso(s.starts_at),
        "ends_at": _iso(s.ends_at),
        "booking_payment_deadline_at": _iso(getattr(s, "booking_payment_deadline_at", None)),
        "course_type": s.course_type,
        "mode": s.mode,
        "location_fa": s.location_fa,
        "meeting_link": (_meeting_link_for_viewer(s, viewer) if show_link else None),
        "meeting_link_open_at": _iso(open_at),
        "meeting_link_is_visible": bool(show_link),
        "student_join_open": bool(getattr(s, "student_join_open", False)),
        "alocom_event_id": getattr(s, "alocom_event_id", None) if show_link or (viewer and viewer.role in ("admin", "staff", "site_manager", "deputy_education")) else None,
        "label_fa": s.label_fa,
        "interviewer_user_id": str(s.interviewer_user_id) if getattr(s, "interviewer_user_id", None) else None,
        "assigned_student_id": str(s.assigned_student_id) if s.assigned_student_id else None,
        "assigned_instance_id": str(s.assigned_instance_id) if s.assigned_instance_id else None,
        "reminder_sent_at": _iso(s.reminder_sent_at),
        "created_at": _iso(s.created_at),
    }


class UpdateInterviewSlotBody(BaseModel):
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    course_type: Optional[Literal["introductory", "comprehensive"]] = None
    mode: Optional[Literal["in_person", "online"]] = None
    location_fa: Optional[str] = None
    meeting_link: Optional[str] = None
    label_fa: Optional[str] = None
    student_join_open: Optional[bool] = None


class CreateInterviewSlotBody(BaseModel):
    starts_at: datetime
    ends_at: datetime
    course_type: Optional[Literal["introductory", "comprehensive"]] = None
    mode: Literal["in_person", "online"] = "online"
    location_fa: Optional[str] = None
    meeting_link: Optional[str] = None
    label_fa: Optional[str] = None


class BookInterviewSlotBody(BaseModel):
    instance_id: str = Field(..., min_length=1)
    slot_id: str = Field(..., min_length=1)


class RescheduleInterviewSlotBody(BaseModel):
    starts_at: datetime
    ends_at: datetime


def _parse_hh_mm_value(raw: str) -> time:
    s = raw.strip()
    parts = s.split(":")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="زمان باید به شکل ساعت:دقیقه (مثل 09:30) باشد.")
    try:
        h, mi = int(parts[0]), int(parts[1])
    except ValueError as e:
        raise HTTPException(status_code=400, detail="زمان نامعتبر است.") from e
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise HTTPException(status_code=400, detail="ساعت یا دقیقه خارج از بازه است.")
    return time(h, mi)


def _validate_days_of_week(days: list[int]) -> list[int]:
    n = normalize_rule_weekdays(days)
    if not n:
        raise HTTPException(status_code=400, detail="حداقل یک روز هفته معتبر انتخاب کنید (۰=دوشنبه … ۶=یکشنبه).")
    return n


def _recurring_rule_to_dict(rule: InterviewSlotRecurringRule) -> dict:
    st = rule.start_local_time
    et = rule.end_local_time
    return {
        "id": str(rule.id),
        "interviewer_user_id": str(rule.interviewer_user_id),
        "days_of_week": list(rule.days_of_week or []),
        "start_local_time": st.strftime("%H:%M") if st else None,
        "end_local_time": et.strftime("%H:%M") if et else None,
        "course_type": rule.course_type,
        "mode": rule.mode,
        "location_fa": rule.location_fa,
        "meeting_link": rule.meeting_link,
        "label_fa": rule.label_fa,
        "is_active": bool(rule.is_active),
        "horizon_days": int(rule.horizon_days or 21),
        "created_at": _iso(rule.created_at),
        "updated_at": _iso(rule.updated_at),
    }


RECURRING_RULE_ROLES = SLOT_DEFINE_ROLES

# مالک الگوی تکراری: مصاحبه‌گر مقصد یا خود کارمند دفتر
RECURRING_RULE_OWNER_ROLES = frozenset({"interviewer", "staff"})


async def _resolve_recurring_owner_for_create(
    db: AsyncSession,
    *,
    actor: User,
    interviewer_user_id_body: Optional[str],
) -> uuid.UUID:
    if not _can_define_interview_slots(actor):
        raise HTTPException(status_code=403, detail="دسترسی مجاز نیست.")
    raw = (interviewer_user_id_body or "").strip()
    if not raw:
        return actor.id
    try:
        oid = uuid.UUID(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسه مالک الگو نامعتبر است.")
    tgt = await db.get(User, oid)
    if not tgt or not tgt.is_active:
        raise HTTPException(status_code=400, detail="کاربر انتخاب‌شده یافت نشد یا غیرفعال است.")
    role_n = (tgt.role or "").strip()
    if role_n not in RECURRING_RULE_OWNER_ROLES:
        raise HTTPException(
            status_code=400,
            detail="مالک الگو باید مصاحبه‌گر یا کارمند دفتر باشد.",
        )
    return oid


def _stmt_recurring_rule_for_mutation(rule_id: uuid.UUID, actor: User):
    return select(InterviewSlotRecurringRule).where(InterviewSlotRecurringRule.id == rule_id)


class CreateInterviewRecurringRuleBody(BaseModel):
    days_of_week: list[int] = Field(..., min_length=1)
    start_local_time: str = Field(..., min_length=4, max_length=8)
    end_local_time: str = Field(..., min_length=4, max_length=8)
    course_type: Optional[Literal["introductory", "comprehensive"]] = None
    mode: Literal["in_person", "online"] = "online"
    location_fa: Optional[str] = None
    meeting_link: Optional[str] = None
    label_fa: Optional[str] = None
    is_active: bool = True
    horizon_days: int = Field(21, ge=1, le=90)
    interviewer_user_id: Optional[str] = Field(
        None,
        description="فقط برای نقش ادمین؛ مصاحبه‌گر این فیلد را نادیده می‌گیرد.",
    )


class UpdateInterviewRecurringRuleBody(BaseModel):
    days_of_week: Optional[list[int]] = None
    start_local_time: Optional[str] = Field(None, min_length=4, max_length=8)
    end_local_time: Optional[str] = Field(None, min_length=4, max_length=8)
    course_type: Optional[Literal["introductory", "comprehensive"]] = None
    mode: Optional[Literal["in_person", "online"]] = None
    location_fa: Optional[str] = None
    meeting_link: Optional[str] = None
    label_fa: Optional[str] = None
    is_active: Optional[bool] = None
    horizon_days: Optional[int] = Field(None, ge=1, le=90)


@router.get("/recurring-rules")
async def list_interview_recurring_rules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*RECURRING_RULE_ROLES)),
):
    stmt = select(InterviewSlotRecurringRule).order_by(InterviewSlotRecurringRule.created_at)
    rows = list((await db.execute(stmt)).scalars().all())
    return {"rules": [_recurring_rule_to_dict(r) for r in rows]}


@router.get("/recurring-rules/candidate-owners")
async def list_recurring_rule_candidate_owners(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*SLOT_DEFINE_ROLES)),
):
    """کاربران فعالی که کارمند دفتر بتواند به‌عنوان مالک الگوی تکراری انتخاب کند."""
    stmt = (
        select(User)
        .where(
            User.is_active == True,
            User.role.in_(tuple(RECURRING_RULE_OWNER_ROLES)),
        )
        .order_by(User.role.asc(), User.full_name_fa.asc().nulls_last(), User.username.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return {
        "users": [
            {
                "id": str(u.id),
                "username": u.username,
                "full_name_fa": u.full_name_fa,
                "role": u.role,
            }
            for u in rows
        ],
    }


@router.post("/recurring-rules")
async def create_interview_recurring_rule(
    body: CreateInterviewRecurringRuleBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*RECURRING_RULE_ROLES)),
):
    now = datetime.now(timezone.utc)
    await expire_interview_booking_payment_deadlines(db, now=now)

    days = _validate_days_of_week(body.days_of_week)
    st = _parse_hh_mm_value(body.start_local_time)
    et = _parse_hh_mm_value(body.end_local_time)
    if et <= st:
        raise HTTPException(status_code=400, detail="ساعت پایان باید بعد از شروع همان روز باشد.")

    owner_id = await _resolve_recurring_owner_for_create(
        db, actor=user, interviewer_user_id_body=body.interviewer_user_id
    )

    rule = InterviewSlotRecurringRule(
        id=uuid.uuid4(),
        interviewer_user_id=owner_id,
        days_of_week=days,
        start_local_time=st,
        end_local_time=et,
        course_type=body.course_type,
        mode=body.mode,
        location_fa=(body.location_fa or "").strip() or None,
        meeting_link=(body.meeting_link or "").strip() or None,
        label_fa=(body.label_fa or "").strip() or None,
        is_active=body.is_active,
        horizon_days=body.horizon_days,
    )
    db.add(rule)
    await db.flush()

    summary = await generate_interview_slots_from_recurring_rules(db, now=now)
    await db.flush()
    return {"rule": _recurring_rule_to_dict(rule), "generation": summary}


@router.patch("/recurring-rules/{rule_id}")
async def update_interview_recurring_rule(
    rule_id: str,
    body: UpdateInterviewRecurringRuleBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*RECURRING_RULE_ROLES)),
):
    try:
        rid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسه نامعتبر")
    now = datetime.now(timezone.utc)
    await expire_interview_booking_payment_deadlines(db, now=now)

    stmt = _stmt_recurring_rule_for_mutation(rid, user)
    rule = (await db.execute(stmt)).scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="الگو یافت نشد")

    await delete_unbooked_future_slots_generated_from_rule(db, rule_id=rid)

    patch = body.model_dump(exclude_unset=True)
    if not patch:
        summary = await generate_interview_slots_from_recurring_rules(db, now=now)
        await db.flush()
        return {"rule": _recurring_rule_to_dict(rule), "generation": summary}

    if "days_of_week" in patch:
        rule.days_of_week = _validate_days_of_week(patch["days_of_week"])

    if "start_local_time" in patch or "end_local_time" in patch:
        ss = patch.get("start_local_time") or rule.start_local_time.strftime("%H:%M")
        ee = patch.get("end_local_time") or rule.end_local_time.strftime("%H:%M")
        st_t = _parse_hh_mm_value(ss)
        et_t = _parse_hh_mm_value(ee)
        if et_t <= st_t:
            raise HTTPException(status_code=400, detail="ساعت پایان باید بعد از شروع باشد.")
        rule.start_local_time = st_t
        rule.end_local_time = et_t

    if "course_type" in patch:
        rule.course_type = patch["course_type"]
    if "mode" in patch:
        if patch["mode"] is None:
            raise HTTPException(status_code=400, detail="نوع برگزاری نامعتبر است.")
        rule.mode = patch["mode"]
    if "location_fa" in patch:
        rule.location_fa = (patch["location_fa"] or "").strip() or None
    if "meeting_link" in patch:
        rule.meeting_link = (patch["meeting_link"] or "").strip() or None
    if "label_fa" in patch:
        rule.label_fa = (patch["label_fa"] or "").strip() or None
    if "is_active" in patch and patch["is_active"] is not None:
        rule.is_active = bool(patch["is_active"])
    if "horizon_days" in patch and patch["horizon_days"] is not None:
        rule.horizon_days = int(patch["horizon_days"])

    await db.flush()
    summary = await generate_interview_slots_from_recurring_rules(db, now=now)
    await db.flush()
    return {"rule": _recurring_rule_to_dict(rule), "generation": summary}


@router.delete("/recurring-rules/{rule_id}")
async def delete_interview_recurring_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*RECURRING_RULE_ROLES)),
):
    try:
        rid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسه نامعتبر")
    stmt = _stmt_recurring_rule_for_mutation(rid, user)
    rule = (await db.execute(stmt)).scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="الگو یافت نشد")
    await db.delete(rule)
    await db.flush()
    return {"success": True}


@router.get("/available")
async def list_available_slots(
    course_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    """اسلات‌های آینده بدون تخصیص؛ اختیاری فیلتر نوع دوره."""
    now = datetime.now(timezone.utc)
    await expire_interview_booking_payment_deadlines(db, now=now)
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
    return {"slots": [_slot_to_dict(s, viewer=user, now=now, hide_link=True) for s in rows]}


@router.get("/bookings")
async def list_booked_slots_with_students(
    include_past: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*BOOKINGS_ROLES)),
):
    """اسلات‌های رزروشده همراه اطلاعات دانشجو و نمونهٔ فرایند — برای مصاحبه‌گر و دفتر."""
    now = datetime.now(timezone.utc)
    await expire_interview_booking_payment_deadlines(db, now=now)
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
        if user.role == "interviewer" and not _interviewer_can_view_booking(user, slot):
            continue
        await _prepare_slot_meeting_links_for_staff(
            db, slot, viewer=user, instance=inst, log_context="bookings",
        )
        item = {
            "slot": _slot_to_dict(slot, viewer=user, now=now),
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
    user: User = Depends(require_role(*SLOT_DEFINE_ROLES)),
):
    """فهرست اسلات‌ها برای تعریف/مدیریت وقت توسط کارمند دفتر."""
    now = datetime.now(timezone.utc)
    await expire_interview_booking_payment_deadlines(db, now=now)
    stmt = select(InterviewSlot)
    if not include_past:
        stmt = stmt.where(InterviewSlot.ends_at >= now)
    stmt = stmt.order_by(InterviewSlot.starts_at)
    rows = (await db.execute(stmt)).scalars().all()
    out: list[dict] = []
    for s in rows:
        await _prepare_slot_meeting_links_for_staff(
            db, s, viewer=user, log_context="manage list",
        )
        out.append(_slot_to_dict(s, viewer=user, now=now))
    return {"slots": out}


@router.post("/manage")
async def create_slot(
    body: CreateInterviewSlotBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*SLOT_DEFINE_ROLES)),
):
    if body.ends_at <= body.starts_at:
        raise HTTPException(status_code=400, detail="زمان پایان باید بعد از شروع باشد.")
    now = datetime.now(timezone.utc)
    if body.ends_at <= now:
        raise HTTPException(status_code=400, detail="بازه باید در آینده باشد.")

    await expire_interview_booking_payment_deadlines(db, now=now)

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
        interviewer_user_id=None,
    )
    db.add(slot)
    await db.flush()
    return _slot_to_dict(slot, viewer=user)


def _normalize_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.patch("/manage/{slot_id}")
async def update_slot(
    slot_id: str,
    body: UpdateInterviewSlotBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*(SLOT_DEFINE_ROLES + BOOKING_SLOT_OPS_ROLES))),
):
    try:
        sid = uuid.UUID(slot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسه نامعتبر")
    stmt = select(InterviewSlot).where(InterviewSlot.id == sid)
    slot = (await db.execute(stmt)).scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="اسلات یافت نشد")

    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return _slot_to_dict(slot, viewer=user)

    define_fields = set(patch.keys()) - {"student_join_open"}
    if define_fields and not _can_define_interview_slots(user):
        raise HTTPException(
            status_code=403,
            detail="تعریف یا ویرایش زمان اسلات فقط برای مسئول پذیر، مدیر داخلی و مدیر سیستم مجاز است.",
        )
    if slot.assigned_student_id is not None and define_fields:
        raise HTTPException(status_code=400, detail="اسلات رزروشده قابل ویرایش نیست.")

    new_starts = _normalize_utc(patch["starts_at"]) if "starts_at" in patch else slot.starts_at
    new_ends = _normalize_utc(patch["ends_at"]) if "ends_at" in patch else slot.ends_at

    if "starts_at" in patch or "ends_at" in patch:
        if new_ends <= new_starts:
            raise HTTPException(status_code=400, detail="زمان پایان باید بعد از شروع باشد.")
        tnow = datetime.now(timezone.utc)
        if new_ends <= tnow:
            raise HTTPException(status_code=400, detail="بازه باید در آینده باشد.")
        slot.starts_at = new_starts
        slot.ends_at = new_ends

    if "course_type" in patch:
        slot.course_type = patch["course_type"]
    if "mode" in patch:
        if patch["mode"] is None:
            raise HTTPException(status_code=400, detail="نوع برگزاری نامعتبر است.")
        slot.mode = patch["mode"]
    if "location_fa" in patch:
        slot.location_fa = (patch["location_fa"] or "").strip() or None
    if "meeting_link" in patch:
        slot.meeting_link = (patch["meeting_link"] or "").strip() or None
    if "label_fa" in patch:
        slot.label_fa = (patch["label_fa"] or "").strip() or None
    if "student_join_open" in patch:
        slot.student_join_open = bool(patch["student_join_open"])
        if slot.student_join_open and slot.mode == "online" and slot.assigned_student_id:
            from app.services.interview_slot_service import maybe_provision_interview_slot_alocom_link

            await maybe_provision_interview_slot_alocom_link(
                db, slot, payment_confirmed=True
            )

    await db.flush()
    return _slot_to_dict(slot, viewer=user)


@router.patch("/manage/{slot_id}/reschedule")
async def reschedule_booked_slot(
    slot_id: str,
    body: RescheduleInterviewSlotBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*(SLOT_DEFINE_ROLES + ("interviewer",)))),
):
    try:
        sid = uuid.UUID(slot_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسه نامعتبر")
    stmt = select(InterviewSlot).where(InterviewSlot.id == sid).with_for_update()
    slot = (await db.execute(stmt)).scalars().first()
    if not slot:
        raise HTTPException(status_code=404, detail="اسلات یافت نشد")
    if not _can_reschedule_booked_slot(user, slot):
        raise HTTPException(status_code=403, detail="مجوز تغییر زمان این رزرو را ندارید.")

    out = await reschedule_booked_interview_slot(
        db,
        slot=slot,
        new_starts_at=body.starts_at,
        new_ends_at=body.ends_at,
    )
    if not out.get("success"):
        raise HTTPException(status_code=400, detail=out.get("error") or "تغییر زمان انجام نشد.")
    return {**out, "slot": _slot_to_dict(slot, viewer=user)}


@router.delete("/manage/{slot_id}")
async def delete_slot(
    slot_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*SLOT_DEFINE_ROLES)),
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


@router.get("/my-bookings")
async def list_my_booked_slots(
    include_past: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    """اسلات‌های رزروشدهٔ دانشجو — پس از پرداخت موفق با لینک الوکام."""
    now = datetime.now(timezone.utc)
    await expire_interview_booking_payment_deadlines(db, now=now)
    st = (await db.execute(select(Student).where(Student.user_id == user.id))).scalars().first()
    if not st:
        return {"bookings": []}
    stmt = select(InterviewSlot).where(
        InterviewSlot.assigned_student_id == st.id,
        # فقط پس از قطعی‌شدن پرداخت مصاحبه در پروفایل دانشجو نشان داده شود
        InterviewSlot.booking_payment_deadline_at.is_(None),
    )
    if not include_past:
        stmt = stmt.where(InterviewSlot.ends_at >= now)
    stmt = stmt.order_by(InterviewSlot.starts_at)
    rows = (await db.execute(stmt)).scalars().all()
    for slot in rows:
        await maybe_provision_interview_slot_alocom_link(
            db, slot, payment_confirmed=True
        )
    return {"bookings": [_slot_to_dict(slot, viewer=user, now=now) for slot in rows]}
