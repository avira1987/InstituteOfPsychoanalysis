"""محاسبات و دادهٔ UI برای فرایند ۲۵ — کنسل جلسات سوپرویژن توسط دانشجو."""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, Student, User
from app.services.supervisor_session_cancellation_service import (
    _parse_date,
    _session_paid_from_ctx,
    _session_time_from_ctx,
)


def _iso_week_key(d: date) -> tuple[int, int]:
    iso = d.isocalendar()
    return (iso.year, iso.week)


def parse_supervision_instance_id_list(raw) -> list[uuid.UUID]:
    from app.services.action_handler import parse_therapy_session_id_list

    return parse_therapy_session_id_list(raw)


async def _supervisor_display_name(db: AsyncSession, supervisor_user_id: Optional[uuid.UUID]) -> str:
    if not supervisor_user_id:
        return "سوپروایزر"
    user = await db.get(User, supervisor_user_id)
    if user and user.full_name_fa:
        return user.full_name_fa
    return "سوپروایزر"


async def _active_supervisor_ids(db: AsyncSession, student: Student) -> list[tuple[str, uuid.UUID]]:
    """(label, user_id) — سوپروایزر اصلی و در صورت وجود دومین سوپروایزر فعال."""
    out: list[tuple[str, uuid.UUID]] = []
    extra = StateMachineEngine._as_mapping(student.extra_data)
    if student.supervisor_id:
        name = await _supervisor_display_name(db, student.supervisor_id)
        out.append((name, student.supervisor_id))
    second_raw = extra.get("second_supervisor_id") or extra.get("secondary_supervisor_id")
    if second_raw:
        try:
            sid = uuid.UUID(str(second_raw))
        except (TypeError, ValueError):
            sid = None
        if sid and sid not in {x[1] for x in out}:
            name = await _supervisor_display_name(db, sid)
            out.append((name, sid))
    supervisors = extra.get("active_supervisors") or extra.get("supervisors")
    if isinstance(supervisors, list):
        for i, item in enumerate(supervisors):
            if isinstance(item, dict):
                uid_raw = item.get("user_id") or item.get("supervisor_id") or item.get("id")
                label = item.get("name_fa") or item.get("name") or f"سوپروایزر {i + 1}"
            else:
                uid_raw = item
                label = f"سوپروایزر {i + 1}"
            if not uid_raw:
                continue
            try:
                uid = uuid.UUID(str(uid_raw))
            except (TypeError, ValueError):
                continue
            if uid in {x[1] for x in out}:
                continue
            if not isinstance(label, str) or label.startswith("سوپروایزر "):
                label = await _supervisor_display_name(db, uid)
            out.append((label, uid))
    return out


async def _session_counts(db: AsyncSession, student_id: uuid.UUID) -> tuple[int, int]:
    """(completed_sessions, cancelled_sessions) — مبنای درصد کنسلی سوپرویژن."""
    student = await db.get(Student, student_id)
    extra = StateMachineEngine._as_mapping(student.extra_data) if student else {}
    lms = StateMachineEngine._as_mapping(extra.get("lms"))

    completed_hours = max(
        float(extra.get("supervision_hours") or 0),
        int(lms.get("total_hours") or 0),
    )

    stmt_done = select(ProcessInstance.id).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == "supervision_50h_completion",
        ProcessInstance.current_state_code == "session_completed",
    )
    completed_instances = len(list((await db.execute(stmt_done)).scalars().all()))
    completed = max(int(completed_hours), completed_instances)

    cancelled = int(extra.get("supervision_cancelled_sessions_count") or 0)
    stmt_cancel = select(ProcessInstance).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == "supervision_50h_completion",
        ProcessInstance.current_state_code == "recording_closed",
    )
    for inst in (await db.execute(stmt_cancel)).scalars().all():
        ctx = StateMachineEngine._as_mapping(inst.context_data)
        if ctx.get("cancelled_by") == "student" or "student_supervision_cancellation" in str(
            ctx.get("cancellation_tag") or ""
        ):
            cancelled += 1

    return completed, cancelled


def compute_cancellation_percent(completed: int, cancelled: int) -> float:
    total = completed + cancelled
    if total <= 0:
        return 0.0
    return round((cancelled / total) * 100.0, 2)


def compute_percent_after(completed: int, cancelled: int, additional: int) -> float:
    return compute_cancellation_percent(completed, cancelled + max(0, additional))


async def get_supervision_cancellation_stats(
    db: AsyncSession,
    student_id: uuid.UUID,
    additional_cancellations: int = 0,
) -> dict[str, Any]:
    completed, cancelled = await _session_counts(db, student_id)
    percent_now = compute_cancellation_percent(completed, cancelled)
    percent_after = compute_percent_after(completed, cancelled, additional_cancellations)
    total_base = completed + cancelled + max(0, additional_cancellations)
    allowed_cap = math.ceil(total_base * 0.12) if total_base > 0 else 0
    return {
        "completed_sessions": completed,
        "cancelled_sessions": cancelled,
        "supervision_hours_base": completed,
        "cancellation_percent_now": percent_now,
        "cancellation_percent_after": percent_after,
        "allowed_cancellation_cap_count": allowed_cap,
        "warning_threshold_percent": 10,
        "max_threshold_percent": 12,
    }


def _weeks_empty_after_selection(
    sessions_by_week: dict[tuple[int, int], list[dict]],
    selected_ids: set[str],
) -> set[tuple[int, int]]:
    empty: set[tuple[int, int]] = set()
    for wk, items in sessions_by_week.items():
        if not items:
            continue
        all_cancelled = all(
            it.get("status") == "cancelled" or str(it["id"]) in selected_ids for it in items
        )
        if all_cancelled:
            empty.add(wk)
    return empty


def _max_consecutive_weeks(weeks: set[tuple[int, int]]) -> int:
    if not weeks:
        return 0
    sorted_weeks = sorted(weeks)
    best = 1
    run = 1
    for i in range(1, len(sorted_weeks)):
        py, pw = sorted_weeks[i - 1]
        cy, cw = sorted_weeks[i]
        if (cy == py and cw == pw + 1) or (cy == py + 1 and pw >= 52 and cw == 1):
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


async def would_exceed_consecutive_cancel_weeks(
    db: AsyncSession,
    student_id: uuid.UUID,
    selected_ids: list[uuid.UUID],
    *,
    lookback_weeks: int = 8,
    lookahead_weeks: int = 4,
) -> bool:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(weeks=lookback_weeks)
    end = today + timedelta(weeks=lookahead_weeks)

    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == "supervision_50h_completion",
        ProcessInstance.is_cancelled.is_(False),
    )
    rows = list((await db.execute(stmt)).scalars().all())
    sel = {str(x) for x in selected_ids}

    by_week: dict[tuple[int, int], list[dict]] = {}
    for inst in rows:
        ctx = StateMachineEngine._as_mapping(inst.context_data)
        sd = _parse_date(ctx.get("session_date") or ctx.get("supervision_session_date"))
        if not sd or sd < start or sd > end:
            continue
        wk = _iso_week_key(sd)
        status = "cancelled" if inst.current_state_code == "recording_closed" else "scheduled"
        by_week.setdefault(wk, []).append({"id": str(inst.id), "status": status})

    empty = _weeks_empty_after_selection(by_week, sel)
    return _max_consecutive_weeks(empty) > 3


async def get_upcoming_supervision_cancellation_sessions(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    display_weeks: int = 3,
) -> list[dict[str, Any]]:
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

    supervisors = await _active_supervisor_ids(db, student)
    sup_map = {str(uid): label for label, uid in supervisors}

    inst_stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == "supervision_50h_completion",
        ProcessInstance.current_state_code.in_(("session_scheduled", "supervisor_recording")),
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
        sup_id = str(ctx.get("supervisor_id") or student.supervisor_id or "")
        sup_name = sup_map.get(sup_id) or await _supervisor_display_name(
            db, uuid.UUID(sup_id) if sup_id else None
        )
        week_offset = max(0, (sd - today).days // 7)
        week_label = {0: "هفته آینده", 1: "دو هفته آینده", 2: "سه هفته آینده"}.get(
            week_offset, f"هفته +{week_offset + 1}"
        )
        options.append(
            {
                "value": str(inst.id),
                "label_fa": f"{sd.isoformat()} ساعت {time_str} — {sup_name}",
                "session_date": sd.isoformat(),
                "session_time": time_str,
                "supervisor_id": sup_id or None,
                "supervisor_name_fa": sup_name,
                "week_label_fa": week_label,
                "paid": paid if paid is not None else False,
                "supervision_50h_instance_id": str(inst.id),
            }
        )

    options.sort(key=lambda x: (x.get("session_date") or "", x.get("session_time") or ""))
    return options


async def build_student_supervision_cancellation_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    selected_sessions_raw=None,
    display_weeks: int = 3,
) -> dict[str, Any]:
    selected_ids = parse_supervision_instance_id_list(selected_sessions_raw)
    stats = await get_supervision_cancellation_stats(db, student_id, len(selected_ids))
    upcoming = await get_upcoming_supervision_cancellation_sessions(
        db, student_id, display_weeks=display_weeks
    )

    student = await db.get(Student, student_id)
    supervisors = await _active_supervisor_ids(db, student) if student else []
    supervisor_groups: list[dict[str, Any]] = []
    for label, uid in supervisors:
        sid = str(uid)
        sessions = [s for s in upcoming if str(s.get("supervisor_id") or "") == sid]
        if not sessions and len(supervisors) == 1:
            sessions = list(upcoming)
        supervisor_groups.append(
            {
                "supervisor_id": sid,
                "supervisor_name_fa": label,
                "sessions": sessions,
            }
        )
    if not supervisor_groups and upcoming:
        supervisor_groups = [
            {"supervisor_id": None, "supervisor_name_fa": "سوپرویژن", "sessions": upcoming}
        ]

    would_exceed = False
    if selected_ids:
        would_exceed = await would_exceed_consecutive_cancel_weeks(db, student_id, selected_ids)

    consecutive_block_message_fa = (
        "دانشجوی گرامی، شما مجاز به کنسل کردن جلسات سوپرویژن به صورت بیش از "
        "۳ هفته متوالی نیستید و باید برای این کار فرایند «وقفه در سوپرویژن فردی توسط دانشجو» را اجرا کنید."
    )
    violation_warning_fa = (
        "دانشجوی محترم، با کنسل کردن جلسات فوق، تعداد کنسلی‌های سوپرویژن شما از ابتدا "
        "تا به حال به بیشتر از ۱۲ درصد که غیرمجاز است افزایش پیدا خواهد کرد. در صورت ثبت "
        "این جلسات کنسلی جدید، شما مرتکب تخلف می‌شوید و به کمیته نظارت گزارش داده خواهد شد."
    )
    status_fa = (
        f"وضعیت غیبت‌های شما: تعداد کل جلسات حضور یافته تا کنون: {stats['completed_sessions']} — "
        f"تعداد جلسات کنسل‌شده مجاز (۱۲٪): {stats['allowed_cancellation_cap_count']} — "
        f"تعداد جلسات کنسل‌شده شما: {stats['cancelled_sessions']}"
    )

    percent_after = float(stats["cancellation_percent_after"])
    return {
        **stats,
        "upcoming_cancellation_sessions": upcoming,
        "supervision_cancellation_groups": supervisor_groups,
        "active_supervisor_count": len(supervisors) or 1,
        "would_exceed_consecutive_weeks": would_exceed,
        "consecutive_block_message_fa": consecutive_block_message_fa,
        "violation_warning_message_fa": violation_warning_fa,
        "cancellation_status_summary_fa": status_fa,
        "requires_violation_ack": percent_after > 12,
        "requires_warning_notice": 10 <= percent_after <= 12,
        "display_weeks_ahead": display_weeks,
    }


async def validate_student_supervision_cancellation_selection(
    db: AsyncSession,
    student_id: uuid.UUID,
    selected_sessions_raw,
    *,
    require_violation_ack: bool = False,
    violation_ack: bool = False,
) -> Optional[str]:
    selected_ids = parse_supervision_instance_id_list(selected_sessions_raw)
    if not selected_ids:
        return "حداقل یک جلسه را برای کنسل انتخاب کنید."

    today = datetime.now(timezone.utc).date()
    end = today + timedelta(weeks=3)
    allowed = await get_upcoming_supervision_cancellation_sessions(db, student_id, display_weeks=3)
    allowed_ids = {str(x["value"]) for x in allowed}

    for sid in selected_ids:
        if str(sid) not in allowed_ids:
            inst = await db.get(ProcessInstance, sid)
            if (
                not inst
                or inst.student_id != student_id
                or inst.process_code != "supervision_50h_completion"
            ):
                return "یکی از جلسات انتخاب‌شده یافت نشد یا متعلق به شما نیست."
            ctx = StateMachineEngine._as_mapping(inst.context_data)
            sd = _parse_date(ctx.get("session_date") or ctx.get("supervision_session_date"))
            if not sd or sd < today or sd > end:
                return "فقط جلسات ۳ هفتهٔ آینده در این فرایند قابل انتخاب هستند."
            if inst.current_state_code not in ("session_scheduled", "supervisor_recording"):
                return "فقط جلسات «برنامه‌ریزی‌شده» قابل کنسل هستند."

    if await would_exceed_consecutive_cancel_weeks(db, student_id, selected_ids):
        return (
            "انتخاب شما منجر به کنسل بیش از ۳ هفته متوالی می‌شود. "
            "برای وقفهٔ طولانی‌تر از فرایند «وقفه در سوپرویژن فردی توسط دانشجو» استفاده کنید."
        )

    stats = await get_supervision_cancellation_stats(db, student_id, len(selected_ids))
    if float(stats["cancellation_percent_after"]) > 12 and require_violation_ack and not violation_ack:
        return "برای ثبت کنسلی بالای ۱۲٪، تأیید هشدار تخلف در فرم الزامی است."

    return None
