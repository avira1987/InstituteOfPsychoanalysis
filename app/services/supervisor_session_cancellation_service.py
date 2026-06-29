"""محاسبات و دادهٔ UI برای فرایند ۲۶ — کنسل جلسه سوپرویژن توسط سوپروایزر."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, Student, User


def _parse_date(raw: Any) -> Optional[date]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _session_time_from_ctx(ctx: dict) -> str:
    for key in (
        "session_time",
        "supervision_session_time",
        "preferred_time_hhmm",
        "proposed_time",
    ):
        v = ctx.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return "—"


def _session_paid_from_ctx(ctx: dict) -> Optional[bool]:
    for key in ("supervision_session_paid", "session_paid"):
        v = ctx.get(key)
        if v is not None:
            return bool(v)
    return None


async def _student_display_name(db: AsyncSession, student: Student) -> str:
    if student.user_id:
        user = await db.get(User, student.user_id)
        if user and user.full_name_fa:
            return user.full_name_fa
    return student.student_code or str(student.id)


async def get_supervisor_sessions_next_4_weeks(
    db: AsyncSession,
    supervisor_user_id: Optional[uuid.UUID],
    student_id: uuid.UUID,
    *,
    display_weeks: int = 4,
) -> list[dict[str, Any]]:
    """جلسات سوپرویژن برنامه‌ریزی‌شده در N هفتهٔ آینده (از نمونه‌های supervision_50h_completion)."""
    today = datetime.now(timezone.utc).date()
    end = today + timedelta(weeks=display_weeks)

    stmt = (
        select(Student)
        .where(Student.id == student_id)
        .options(selectinload(Student.user))
    )
    student = (await db.execute(stmt)).scalars().first()
    if not student:
        return []

    if supervisor_user_id and student.supervisor_id and student.supervisor_id != supervisor_user_id:
        return []

    student_name = await _student_display_name(db, student)

    inst_stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == "supervision_50h_completion",
        ProcessInstance.current_state_code == "session_scheduled",
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
    )
    instances = list((await db.execute(inst_stmt)).scalars().all())

    options: list[dict[str, Any]] = []
    for inst in instances:
        ctx = StateMachineEngine._as_mapping(inst.context_data)
        sd = _parse_date(ctx.get("session_date") or ctx.get("supervision_session_date"))
        if not sd or sd < today or sd > end:
            continue
        time_str = _session_time_from_ctx(ctx)
        paid = _session_paid_from_ctx(ctx)
        options.append(
            {
                "value": str(inst.id),
                "label_fa": (
                    f"جلسه مورخ {sd.isoformat()} ساعت {time_str} — دانشجو: {student_name}"
                ),
                "session_date": sd.isoformat(),
                "session_time": time_str,
                "student_name": student_name,
                "paid": paid if paid is not None else False,
                "supervision_50h_instance_id": str(inst.id),
            }
        )

    options.sort(key=lambda x: (x.get("session_date") or "", x.get("session_time") or ""))
    return options


async def resolve_selected_supervision_session(
    db: AsyncSession,
    student_id: uuid.UUID,
    selected_session_raw: Any,
) -> Optional[dict[str, Any]]:
    """جزئیات جلسهٔ انتخاب‌شده از شناسهٔ نمونهٔ supervision_50h_completion."""
    if selected_session_raw is None or selected_session_raw == "":
        return None
    try:
        sid = uuid.UUID(str(selected_session_raw).strip())
    except (TypeError, ValueError):
        return None

    inst = await db.get(ProcessInstance, sid)
    if (
        not inst
        or inst.student_id != student_id
        or inst.process_code != "supervision_50h_completion"
    ):
        return None

    ctx = StateMachineEngine._as_mapping(inst.context_data)
    sd = _parse_date(ctx.get("session_date") or ctx.get("supervision_session_date"))
    paid = _session_paid_from_ctx(ctx)
    return {
        "selected_session": str(inst.id),
        "selected_session_date": sd.isoformat() if sd else None,
        "selected_session_time": _session_time_from_ctx(ctx),
        "supervision_50h_instance_id": str(inst.id),
        "supervision_session_paid": paid if paid is not None else False,
        "session_paid": paid if paid is not None else False,
        "selected_sessions_count": 1,
    }


async def build_supervisor_cancellation_context(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    supervisor_user_id: Optional[uuid.UUID] = None,
    display_weeks: int = 4,
) -> dict[str, Any]:
    """دادهٔ نمایشی فرایند ۲۶ برای status/forms."""
    out: dict[str, Any] = {}
    student = await db.get(Student, instance.student_id)
    sup_id = supervisor_user_id
    if student and student.supervisor_id:
        sup_id = student.supervisor_id

    sessions = await get_supervisor_sessions_next_4_weeks(
        db,
        sup_id,
        instance.student_id,
        display_weeks=display_weeks,
    )
    out["supervisor_sessions_next_4_weeks"] = sessions
    out["display_weeks_ahead"] = display_weeks

    merged = StateMachineEngine._as_mapping(instance.context_data)
    selected_raw = merged.get("selected_session")
    if selected_raw:
        detail = await resolve_selected_supervision_session(
            db, instance.student_id, selected_raw
        )
        if detail:
            out.update(detail)

    for key in (
        "proposed_date",
        "proposed_time",
        "makeup_option",
        "student_response",
        "counter_proposal_text",
    ):
        if merged.get(key) not in (None, ""):
            out[key] = merged[key]

    if out.get("proposed_date") and out.get("proposed_time"):
        out["makeup_proposed_summary_fa"] = (
            f"تاریخ {out['proposed_date']} ساعت {out['proposed_time']}"
        )

    return out


async def validate_supervisor_session_selection(
    db: AsyncSession,
    student_id: uuid.UUID,
    selected_session_raw: Any,
    *,
    supervisor_user_id: Optional[uuid.UUID] = None,
    display_weeks: int = 4,
) -> Optional[str]:
    if selected_session_raw is None or str(selected_session_raw).strip() == "":
        return "یک جلسه را برای لغو انتخاب کنید."

    detail = await resolve_selected_supervision_session(db, student_id, selected_session_raw)
    if not detail:
        return "جلسهٔ انتخاب‌شده یافت نشد یا متعلق به این دانشجو نیست."

    allowed = await get_supervisor_sessions_next_4_weeks(
        db,
        supervisor_user_id,
        student_id,
        display_weeks=display_weeks,
    )
    allowed_ids = {str(x["value"]) for x in allowed}
    if str(selected_session_raw) not in allowed_ids:
        return "فقط جلسات برنامه‌ریزی‌شده در ۴ هفتهٔ آینده قابل انتخاب هستند."

    return None


async def validate_supervisor_makeup_time(
    proposed_date: Any,
    proposed_time: Any,
) -> Optional[str]:
    if not proposed_date or not str(proposed_date).strip():
        return "تاریخ جلسه جبرانی الزامی است."
    if not proposed_time or not str(proposed_time).strip():
        return "ساعت جلسه جبرانی الزامی است."
    if _parse_date(proposed_date) is None:
        return "تاریخ جلسه جبرانی نامعتبر است."
    return None
