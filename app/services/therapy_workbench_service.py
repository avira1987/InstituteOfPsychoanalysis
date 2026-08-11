"""میزکار مقیاس‌پذیر درمان — خلاصه به‌ازای دانشجو و جلسات صفحه‌بندی‌شده."""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from typing import Any, Literal, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import AttendanceRecord, ProcessInstance, Student, TherapySession, User
from app.services.alocom_provision import (
    is_stub_therapy_meeting_url,
    is_tokenized_alocom_join_url,
)
from app.utils.shamsi_calendar_utils import tehran_today

logger = logging.getLogger(__name__)

RoleScope = Literal["therapist", "staff", "site_manager"]

DEFAULT_SESSION_PAST_DAYS = 7
DEFAULT_SESSION_FUTURE_DAYS = 14
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
STAFF_MAX_RANGE_DAYS = 31


def _host_meeting_url_for_workbench(s: TherapySession, viewer: User) -> Optional[str]:
    """لینک ورود میزبان برای درمانگر/ستاد؛ لینک ساختگی داخلی را پنهان کن."""
    meeting_url = s.meeting_url
    if viewer.role in ("therapist", "admin", "staff", "site_manager"):
        host = getattr(s, "host_meeting_url", None)
        if (host or "").strip():
            meeting_url = host
    url = (meeting_url or "").strip() or None
    if url and is_stub_therapy_meeting_url(url):
        return None
    return url


def _student_meeting_url_ready(s: TherapySession) -> bool:
    return bool(
        is_tokenized_alocom_join_url(s.meeting_url)
        or ((s.meeting_url or "").strip() and not is_stub_therapy_meeting_url(s.meeting_url))
    )


def _attendance_recording_flags(
    s: TherapySession,
    *,
    proc_state: Optional[str],
    recorded_status: Optional[str],
    today: date,
) -> tuple[bool, bool, bool, Optional[str]]:
    """Return (can_record_present, can_record_absent, can_record, block_reason)."""
    terminal_states = (
        "session_completed",
        "excused_absence",
        "unexcused_absence",
        "recording_closed",
        "auto_absence_unpaid",
    )
    if s.status == "cancelled":
        return False, False, False, "session_cancelled"
    if recorded_status:
        return False, False, False, "already_recorded"
    if proc_state in terminal_states:
        return False, False, False, proc_state

    session_ready = proc_state == "therapist_recording" or (
        proc_state == "session_scheduled" and s.session_date <= today
    )
    if not session_ready:
        return False, False, False, None

    paid = s.payment_status in ("paid", "waived")
    if paid:
        return True, True, True, None
    return False, True, True, "unpaid"


async def _students_for_scope(
    db: AsyncSession,
    user: User,
    role_scope: RoleScope,
    *,
    student_id: Optional[uuid.UUID] = None,
) -> list[Student]:
    if role_scope == "therapist":
        q = select(Student).where(
            Student.therapist_id == user.id,
            Student.therapy_started.is_(True),
        )
        if student_id:
            q = q.where(Student.id == student_id)
        return list((await db.execute(q.order_by(Student.student_code))).scalars().all())

    # staff / site_manager — فقط درمان فعال؛ فیلتر student_id اختیاری
    q = select(Student).where(Student.therapy_started.is_(True))
    if student_id:
        q = q.where(Student.id == student_id)
    return list((await db.execute(q.order_by(Student.student_code))).scalars().all())


async def _session_rows_for_students(
    db: AsyncSession,
    student_ids: list[uuid.UUID],
    *,
    from_date: date,
    to_date: date,
) -> list[TherapySession]:
    if not student_ids:
        return []
    q = (
        select(TherapySession)
        .where(
            TherapySession.student_id.in_(student_ids),
            TherapySession.session_date >= from_date,
            TherapySession.session_date <= to_date,
        )
        .order_by(TherapySession.session_date.asc(), TherapySession.session_starts_at.asc().nulls_last())
    )
    return list((await db.execute(q)).scalars().all())


async def _future_scheduled_exists(
    db: AsyncSession,
    student_ids: list[uuid.UUID],
    today: date,
) -> dict[uuid.UUID, bool]:
    if not student_ids:
        return {}
    q = (
        select(TherapySession.student_id, func.count(TherapySession.id))
        .where(
            TherapySession.student_id.in_(student_ids),
            TherapySession.status == "scheduled",
            TherapySession.session_date >= today,
        )
        .group_by(TherapySession.student_id)
    )
    rows = (await db.execute(q)).all()
    has = {sid: cnt > 0 for sid, cnt in rows}
    return {sid: has.get(sid, False) for sid in student_ids}


async def _attendance_maps_for_sessions(
    db: AsyncSession,
    sessions: list[TherapySession],
) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    """یک‌بار بارگذاری: recorded_status / proc_state / instance_id به‌ازای session_id."""
    recorded_by_session: dict[uuid.UUID, str] = {}
    proc_by_session: dict[uuid.UUID, str] = {}
    instance_by_session: dict[uuid.UUID, str] = {}
    if not sessions:
        return recorded_by_session, proc_by_session, instance_by_session

    session_ids = [s.id for s in sessions]
    student_ids = list({s.student_id for s in sessions})

    rec_stmt = (
        select(AttendanceRecord)
        .where(AttendanceRecord.session_id.in_(session_ids))
        .order_by(AttendanceRecord.created_at.desc())
    )
    for rec in (await db.execute(rec_stmt)).scalars().all():
        if rec.session_id not in recorded_by_session:
            recorded_by_session[rec.session_id] = rec.status

    inst_stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "attendance_tracking",
        ProcessInstance.student_id.in_(student_ids),
        ProcessInstance.is_cancelled.is_(False),
    )
    for inst in (await db.execute(inst_stmt)).scalars().all():
        ctx = inst.context_data if isinstance(inst.context_data, dict) else {}
        raw = ctx.get("therapy_session_id") or ctx.get("session_id")
        if not raw:
            continue
        try:
            sid = uuid.UUID(str(raw))
        except (TypeError, ValueError):
            continue
        if sid not in proc_by_session:
            proc_by_session[sid] = inst.current_state_code
            instance_by_session[sid] = str(inst.id)

    return recorded_by_session, proc_by_session, instance_by_session


async def _needs_recording_by_session(
    db: AsyncSession,
    sessions: list[TherapySession],
    today: date,
) -> dict[uuid.UUID, bool]:
    """برای هر جلسه مشخص می‌کند آیا نیاز به ثبت حضور دارد (بدون N+1)."""
    recorded_by_session, proc_by_session, _ = await _attendance_maps_for_sessions(db, sessions)
    out: dict[uuid.UUID, bool] = {}
    for s in sessions:
        recorded_status = recorded_by_session.get(s.id)
        proc_state = proc_by_session.get(s.id)
        _, _, can_record, _ = _attendance_recording_flags(
            s,
            proc_state=proc_state,
            recorded_status=recorded_status,
            today=today,
        )
        out[s.id] = bool(can_record and not recorded_status)
    return out


def _student_summary_row(
    student: Student,
    *,
    sessions: list[TherapySession],
    needs_rec_map: dict[uuid.UUID, bool],
    has_future: bool,
    today: date,
) -> dict[str, Any]:
    upcoming = [
        s for s in sessions
        if s.status == "scheduled" and s.session_date and s.session_date >= today
    ]
    needs_recording = sum(1 for s in sessions if needs_rec_map.get(s.id))
    unpaid_upcoming = sum(
        1 for s in upcoming
        if s.payment_status not in ("paid", "waived")
    )
    next_session = min(upcoming, key=lambda x: (x.session_date, x.session_starts_at or x.session_date), default=None)
    return {
        "student_id": str(student.id),
        "student_code": student.student_code,
        "course_type": student.course_type,
        "weekly_sessions": student.weekly_sessions,
        "upcoming_count": len(upcoming),
        "needs_recording": needs_recording,
        "unpaid_upcoming": unpaid_upcoming,
        "missing_future_schedule": not has_future,
        "next_session_date": next_session.session_date.isoformat() if next_session and next_session.session_date else None,
        "next_session_starts_at": (
            next_session.session_starts_at.isoformat()
            if next_session and getattr(next_session, "session_starts_at", None)
            else None
        ),
        "needs_action": needs_recording > 0 or not has_future or unpaid_upcoming > 0,
    }


async def get_workbench_summary(
    db: AsyncSession,
    user: User,
    *,
    role_scope: RoleScope = "therapist",
    q: Optional[str] = None,
    needs_action: Optional[bool] = None,
    filter_kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """خلاصه به‌ازای دانشجو — بدون side-effect بذر جلسه."""
    today = tehran_today()
    window_from = today - timedelta(days=DEFAULT_SESSION_PAST_DAYS)
    window_to = today + timedelta(days=DEFAULT_SESSION_FUTURE_DAYS)

    students = await _students_for_scope(db, user, role_scope)
    if q:
        q_norm = q.strip()
        students = [s for s in students if q_norm in (s.student_code or "")]

    student_ids = [s.id for s in students]
    sessions = await _session_rows_for_students(
        db, student_ids, from_date=window_from, to_date=window_to,
    )
    sessions_by_student: dict[uuid.UUID, list[TherapySession]] = {}
    for s in sessions:
        sessions_by_student.setdefault(s.student_id, []).append(s)

    has_future_map = await _future_scheduled_exists(db, student_ids, today)
    needs_rec_map = await _needs_recording_by_session(db, sessions, today)

    rows: list[dict[str, Any]] = []
    for student in students:
        st_sessions = sessions_by_student.get(student.id, [])
        row = _student_summary_row(
            student,
            sessions=st_sessions,
            needs_rec_map=needs_rec_map,
            has_future=has_future_map.get(student.id, False),
            today=today,
        )
        if filter_kind == "needs_action" and not row["needs_action"]:
            continue
        if filter_kind == "missing_future" and not row["missing_future_schedule"]:
            continue
        if filter_kind == "needs_recording" and row["needs_recording"] <= 0:
            continue
        if filter_kind == "today":
            has_today = any(
                s.session_date == today for s in st_sessions if s.status == "scheduled"
            )
            if not has_today and row["needs_recording"] <= 0:
                continue
        if filter_kind == "week":
            week_end = today + timedelta(days=7)
            has_week = any(
                s.session_date and today <= s.session_date <= week_end
                for s in st_sessions
                if s.status == "scheduled"
            )
            if not has_week and row["needs_recording"] <= 0:
                continue
        if needs_action is True and not row["needs_action"]:
            continue
        if needs_action is False and row["needs_action"]:
            continue
        rows.append(row)

    total = len(rows)
    page = rows[offset: offset + limit]
    totals = {
        "students": total,
        "needs_recording": sum(r["needs_recording"] for r in rows),
        "missing_future_schedule": sum(1 for r in rows if r["missing_future_schedule"]),
        "unpaid_upcoming": sum(r["unpaid_upcoming"] for r in rows),
        "upcoming_sessions": sum(r["upcoming_count"] for r in rows),
    }
    return {
        "role_scope": role_scope,
        "totals": totals,
        "students": page,
        "pagination": {"limit": limit, "offset": offset, "total": total},
    }


async def get_workbench_sessions(
    db: AsyncSession,
    user: User,
    *,
    role_scope: RoleScope = "therapist",
    student_id: uuid.UUID,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    status: Optional[str] = None,
    needs_recording: Optional[bool] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    include_attendance_flags: bool = True,
) -> dict[str, Any]:
    """جلسات یک دانشجو — بدون refresh الوکام."""
    today = tehran_today()
    from_d = from_date or (today - timedelta(days=DEFAULT_SESSION_PAST_DAYS))
    to_d = to_date or (today + timedelta(days=DEFAULT_SESSION_FUTURE_DAYS))

    if role_scope in ("staff", "site_manager"):
        span = (to_d - from_d).days
        if span > STAFF_MAX_RANGE_DAYS:
            raise ValueError(f"بازهٔ تاریخ برای staff حداکثر {STAFF_MAX_RANGE_DAYS} روز است.")

    students = await _students_for_scope(db, user, role_scope, student_id=student_id)
    if not students:
        raise PermissionError("دسترسی به این دانشجو مجاز نیست یا دانشجو یافت نشد.")
    student = students[0]

    page_size = min(max(1, page_size), MAX_PAGE_SIZE)
    page = max(1, page)

    base = select(TherapySession).where(
        TherapySession.student_id == student_id,
        TherapySession.session_date >= from_d,
        TherapySession.session_date <= to_d,
    )
    if status:
        base = base.where(TherapySession.status == status)

    count_q = select(func.count()).select_from(base.subquery())
    total = int((await db.execute(count_q)).scalar_one())

    q = (
        base.order_by(
            TherapySession.session_date.asc(),
            TherapySession.session_starts_at.asc().nulls_last(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    sessions = list((await db.execute(q)).scalars().all())

    recorded_by_session: dict[uuid.UUID, str] = {}
    proc_by_session: dict[uuid.UUID, str] = {}
    instance_by_session: dict[uuid.UUID, str] = {}
    needs_rec_map: dict[uuid.UUID, bool] = {}
    if include_attendance_flags and sessions:
        recorded_by_session, proc_by_session, instance_by_session = await _attendance_maps_for_sessions(
            db, sessions
        )
        for s in sessions:
            recorded_status = recorded_by_session.get(s.id)
            proc_state = proc_by_session.get(s.id)
            _, _, can_record, _ = _attendance_recording_flags(
                s,
                proc_state=proc_state,
                recorded_status=recorded_status,
                today=today,
            )
            needs_rec_map[s.id] = bool(can_record and not recorded_status)

    if needs_recording is True:
        sessions = [s for s in sessions if needs_rec_map.get(s.id)]
    elif needs_recording is False:
        sessions = [s for s in sessions if not needs_rec_map.get(s.id)]

    out_sessions: list[dict[str, Any]] = []
    for s in sessions:
        recorded_status = recorded_by_session.get(s.id)
        proc_state = proc_by_session.get(s.id)
        instance_id = instance_by_session.get(s.id)
        can_present, can_absent, can_record, block_reason = _attendance_recording_flags(
            s,
            proc_state=proc_state,
            recorded_status=recorded_status,
            today=today,
        )
        meeting_url = _host_meeting_url_for_workbench(s, user)
        out_sessions.append({
            "session_id": str(s.id),
            "student_id": str(s.student_id),
            "student_code": student.student_code,
            "session_date": s.session_date.isoformat() if s.session_date else "",
            "session_starts_at": s.session_starts_at.isoformat() if s.session_starts_at else None,
            "session_number": s.session_number,
            "status": s.status,
            "payment_status": s.payment_status,
            "attendance_process_state": proc_state,
            "attendance_instance_id": instance_id,
            "recorded_status": recorded_status,
            "can_record_present": can_present and not recorded_status,
            "can_record_absent": can_absent and not recorded_status,
            "can_record": can_record and not recorded_status,
            "record_block_reason": block_reason,
            "links_unlocked": bool(s.links_unlocked),
            "meeting_url": meeting_url,
            "meeting_provider": s.meeting_provider if meeting_url else None,
            "student_meeting_url_ready": _student_meeting_url_ready(s),
            "alocom_event_id": getattr(s, "alocom_event_id", None),
            "instructor_score": s.instructor_score,
            "instructor_comment": s.instructor_comment,
            "needs_recording": needs_rec_map.get(s.id, False),
        })

    return {
        "student_id": str(student_id),
        "student_code": student.student_code,
        "sessions": out_sessions,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
        },
        "date_range": {"from": from_d.isoformat(), "to": to_d.isoformat()},
    }


async def assert_can_repair_student(
    db: AsyncSession,
    user: User,
    student_id: uuid.UUID,
) -> Student:
    student = await db.get(Student, student_id)
    if not student:
        raise LookupError("دانشجو یافت نشد.")
    if user.role == "therapist":
        if student.therapist_id != user.id:
            raise PermissionError("این دانشجو به شما منتسب نیست.")
    elif user.role not in ("admin", "site_manager", "staff"):
        raise PermissionError("مجوز تعمیر تقویم ندارید.")
    return student
