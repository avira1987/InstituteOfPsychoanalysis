"""Therapy session URLs and instructor feedback — therapist + student + staff."""

import uuid
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user, require_role
from app.core.user_roles import user_has_role
from app.models.operational_models import User, Student, TherapySession, AttendanceRecord, ProcessInstance, FinancialRecord
from app.services.alocom_provision import (
    ensure_therapy_session_alocom_links,
    is_stub_therapy_meeting_url,
    is_tokenized_alocom_join_url,
    refresh_therapy_session_alocom_links,
)
from app.services.attendance_service import AttendanceService
from app.services.attendance_tracking_sync import (
    apply_therapy_attendance_via_process,
    find_attendance_instance_for_session,
    refresh_attendance_instance_from_db,
)


async def _list_therapy_sessions_for_therapist(
    db: AsyncSession,
    therapist_user_id,
    *,
    order_upcoming_first: bool = True,
) -> list[TherapySession]:
    """جلسات این درمانگر: روی خود جلسه یا از طریق student.therapist_id.

    اگر therapist_id جلسه خالی باشد ولی دانشجو به این درمانگر وصل باشد، مقدار را پر می‌کند
    تا در تب جلسات آنلاین و میزکار حضور/غیاب دیده شود.
    """
    q = (
        select(TherapySession)
        .outerjoin(Student, TherapySession.student_id == Student.id)
        .where(
            or_(
                TherapySession.therapist_id == therapist_user_id,
                Student.therapist_id == therapist_user_id,
            )
        )
    )
    if order_upcoming_first:
        q = q.order_by(
            TherapySession.session_date.asc(),
            TherapySession.session_starts_at.asc().nulls_last(),
        )
    else:
        q = q.order_by(TherapySession.session_date.desc())

    rows = list((await db.execute(q)).scalars().unique().all())
    dirty = False
    for s in rows:
        if s.therapist_id is None:
            s.therapist_id = therapist_user_id
            dirty = True
    if dirty:
        await db.flush()
    return rows

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/therapy-sessions", tags=["TherapySessions"])


def _can_write_session(user: User, session: TherapySession) -> bool:
    if user_has_role(user, "staff", admin_bypass=True):
        return True
    if user_has_role(user, "therapist", admin_bypass=False) and session.therapist_id == user.id:
        return True
    return False


class TherapySessionOut(BaseModel):
    id: str
    student_id: str
    therapist_id: Optional[str]
    student_code: Optional[str] = None
    student_meeting_url_ready: bool = False
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


def _host_meeting_url_for_viewer(s: TherapySession, viewer: Optional[User] = None) -> Optional[str]:
    meeting_url = s.meeting_url
    if viewer and viewer.role in ("therapist", "admin", "staff"):
        host = getattr(s, "host_meeting_url", None)
        if (host or "").strip():
            meeting_url = host
    url = (meeting_url or "").strip() or None
    # لینک ساختگی داخلی را به‌عنوان لینک ورود نشان نده
    if url and is_stub_therapy_meeting_url(url):
        return None
    return url


def _to_out(
    s: TherapySession,
    *,
    viewer: Optional[User] = None,
    student_code: Optional[str] = None,
) -> dict:
    starts = s.session_starts_at.isoformat() if getattr(s, "session_starts_at", None) else None
    meeting_url = _host_meeting_url_for_viewer(s, viewer)
    student_link_ready = bool(is_tokenized_alocom_join_url(s.meeting_url) or (
        (s.meeting_url or "").strip() and not is_stub_therapy_meeting_url(s.meeting_url)
    ))
    return {
        "id": str(s.id),
        "student_id": str(s.student_id),
        "therapist_id": str(s.therapist_id) if s.therapist_id else None,
        "student_code": student_code,
        "student_meeting_url_ready": student_link_ready,
        "session_date": s.session_date.isoformat() if s.session_date else "",
        "session_number": s.session_number,
        "status": s.status,
        "payment_status": s.payment_status,
        "meeting_url": meeting_url,
        "meeting_provider": s.meeting_provider if meeting_url else None,
        "links_unlocked": bool(s.links_unlocked),
        "instructor_score": s.instructor_score,
        "instructor_comment": s.instructor_comment,
        "notes": s.notes,
        "alocom_event_id": getattr(s, "alocom_event_id", None),
        "session_starts_at": starts,
    }


def _attendance_recording_flags(
    s: TherapySession,
    *,
    proc_state: Optional[str],
    recorded_status: Optional[str],
    today,
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
    # SOP: unpaid — Present grayed, Absent allowed
    return False, True, True, "unpaid"


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

    if st.therapy_started:
        try:
            from app.services.therapy_session_schedule import repair_student_therapy_continuity

            repair = await repair_student_therapy_continuity(db, st.id)
            if (repair.get("seed") or {}).get("created") or (repair.get("session_payment") or {}).get("started"):
                await db.commit()
        except Exception:
            logger.exception("repair_student_therapy_continuity on /me failed student=%s", st.id)

    q = select(TherapySession).where(TherapySession.student_id == st.id).order_by(TherapySession.session_date.desc())
    r2 = await db.execute(q)
    rows = r2.scalars().all()
    out = []
    for s in rows:
        if s.meeting_provider == "alocom" and s.links_unlocked:
            try:
                await refresh_therapy_session_alocom_links(db, s)
            except Exception:
                logger.exception("refresh_therapy_session_alocom_links failed session=%s", s.id)
        d = _to_out(s, viewer=current_user)
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
    """Therapist: sessions assigned to this user (upcoming-first order).

    Admin sees all sessions of students with therapy started (oversight).
    """
    if user_has_role(current_user, "admin", admin_bypass=False):
        q = (
            select(TherapySession)
            .join(Student, TherapySession.student_id == Student.id)
            .where(Student.therapy_started.is_(True))
            .order_by(
                TherapySession.session_date.asc(),
                TherapySession.session_starts_at.asc().nulls_last(),
            )
        )
        rows = list((await db.execute(q)).scalars().unique().all())
    else:
        rows = await _list_therapy_sessions_for_therapist(
            db, current_user.id, order_upcoming_first=True
        )
    if not rows:
        return []

    student_ids = {s.student_id for s in rows}
    st_rows = await db.execute(select(Student).where(Student.id.in_(student_ids)))
    students_by_id = {st.id: st for st in st_rows.scalars().all()}

    out = []
    for s in rows:
        try:
            await ensure_therapy_session_alocom_links(db, s)
        except Exception:
            logger.exception("ensure therapy alocom link failed session=%s", s.id)
        if s.meeting_provider == "alocom":
            try:
                await refresh_therapy_session_alocom_links(db, s)
            except Exception:
                logger.exception("refresh therapist therapy link failed session=%s", s.id)
        st = students_by_id.get(s.student_id)
        out.append(
            _to_out(
                s,
                viewer=current_user,
                student_code=st.student_code if st else None,
            )
        )
    return out


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


@router.get("/attendance-workbench")
async def attendance_workbench(
    needs_recording_only: bool = False,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("therapist", "admin", "staff")),
):
    """Therapist workbench for process #6 (attendance_tracking): sessions + process state."""
    from datetime import date as date_type, timedelta

    from app.utils.shamsi_calendar_utils import parse_iso_date, tehran_today

    today = tehran_today()
    from_d = parse_iso_date(from_date) if from_date else today - timedelta(days=7)
    to_d = parse_iso_date(to_date) if to_date else today + timedelta(days=14)
    limit = min(max(1, limit), 200)
    offset = max(0, offset)

    if user_has_role(current_user, "therapist", admin_bypass=False):
        sessions = await _list_therapy_sessions_for_therapist(
            db, current_user.id, order_upcoming_first=False
        )
        sessions = [
            s for s in sessions
            if s.session_date and from_d <= s.session_date <= to_d
        ]
    else:
        span = (to_d - from_d).days
        if span > 31:
            raise HTTPException(
                status_code=400,
                detail="برای staff بازهٔ تاریخ حداکثر ۳۱ روز است.",
            )
        q = (
            select(TherapySession)
            .where(
                TherapySession.session_date >= from_d,
                TherapySession.session_date <= to_d,
            )
            .order_by(TherapySession.session_date.desc())
        )
        sessions = list((await db.execute(q)).scalars().all())
    if not sessions:
        return {"stats": {"needs_recording": 0, "recorded": 0, "closed": 0}, "sessions": []}

    student_ids = {s.student_id for s in sessions}
    st_rows = await db.execute(select(Student).where(Student.id.in_(student_ids)))
    students_by_id = {st.id: st for st in st_rows.scalars().all()}

    needs_recording = 0
    recorded = 0
    closed = 0
    out_sessions: list[dict] = []

    for s in sessions:
        st = students_by_id.get(s.student_id)
        inst = await find_attendance_instance_for_session(db, s.id, include_completed=True)
        proc_state = inst.current_state_code if inst else None
        instance_id = str(inst.id) if inst else None

        if inst and not inst.is_completed and not inst.is_cancelled:
            await refresh_attendance_instance_from_db(db, inst)
            proc_state = inst.current_state_code

        rec_stmt = (
            select(AttendanceRecord)
            .where(AttendanceRecord.session_id == s.id)
            .order_by(AttendanceRecord.created_at.desc())
            .limit(1)
        )
        rec_r = await db.execute(rec_stmt)
        last_rec = rec_r.scalars().first()
        recorded_status = last_rec.status if last_rec else None

        if s.meeting_provider == "alocom":
            try:
                await refresh_therapy_session_alocom_links(db, s)
            except Exception:
                logger.exception("refresh workbench therapy link failed session=%s", s.id)
        else:
            try:
                await ensure_therapy_session_alocom_links(db, s)
            except Exception:
                logger.exception("ensure workbench therapy alocom link failed session=%s", s.id)

        can_record_present, can_record_absent, can_record, block_reason = _attendance_recording_flags(
            s,
            proc_state=proc_state,
            recorded_status=recorded_status,
            today=today,
        )
        host_url = _host_meeting_url_for_viewer(s, current_user)

        if can_record and not recorded_status:
            needs_recording += 1
        elif recorded_status or proc_state in ("session_completed", "excused_absence", "unexcused_absence"):
            recorded += 1
        elif block_reason in ("session_cancelled", "recording_closed", "auto_absence_unpaid"):
            closed += 1

        out_sessions.append({
            "session_id": str(s.id),
            "student_id": str(s.student_id),
            "student_code": st.student_code if st else None,
            "session_date": s.session_date.isoformat() if s.session_date else "",
            "session_starts_at": s.session_starts_at.isoformat() if s.session_starts_at else None,
            "session_number": s.session_number,
            "status": s.status,
            "payment_status": s.payment_status,
            "attendance_process_state": proc_state,
            "attendance_instance_id": instance_id,
            "recorded_status": recorded_status,
            "can_record_present": can_record_present and not recorded_status,
            "can_record_absent": can_record_absent and not recorded_status,
            "can_record": can_record and not recorded_status,
            "record_block_reason": block_reason,
            "meeting_url": host_url,
            "meeting_provider": s.meeting_provider if host_url else None,
            "links_unlocked": bool(s.links_unlocked),
            "student_meeting_url_ready": bool(
                (s.meeting_url or "").strip() and not is_stub_therapy_meeting_url(s.meeting_url)
            ),
            "alocom_event_id": getattr(s, "alocom_event_id", None),
            "instructor_score": s.instructor_score,
            "instructor_comment": s.instructor_comment,
        })

    if needs_recording_only:
        out_sessions = [row for row in out_sessions if row["can_record"]]

    total_sessions = len(out_sessions)
    out_sessions = out_sessions[offset: offset + limit]

    return {
        "stats": {
            "needs_recording": needs_recording,
            "recorded": recorded,
            "closed": closed,
        },
        "sessions": out_sessions,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total_sessions,
        },
        "date_range": {"from": from_d.isoformat(), "to": to_d.isoformat()},
    }


@router.get("/me/therapy-progress")
async def my_therapy_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student dashboard for process #6: therapy hours + recent session attendance."""
    stmt = select(Student).where(Student.user_id == current_user.id)
    r = await db.execute(stmt)
    st = r.scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="Student profile not found")

    att_svc = AttendanceService(db)
    metrics = await att_svc.get_therapy_completion_metrics(st.id)
    summary = await att_svc.get_attendance_summary(st.id)

    q = (
        select(TherapySession)
        .where(TherapySession.student_id == st.id)
        .order_by(TherapySession.session_date.desc())
        .limit(12)
    )
    sess_rows = list((await db.execute(q)).scalars().all())
    recent: list[dict] = []
    for s in sess_rows:
        rec_stmt = (
            select(AttendanceRecord)
            .where(AttendanceRecord.session_id == s.id)
            .order_by(AttendanceRecord.created_at.desc())
            .limit(1)
        )
        rec_r = await db.execute(rec_stmt)
        last_rec = rec_r.scalars().first()
        recent.append({
            "session_id": str(s.id),
            "session_date": s.session_date.isoformat() if s.session_date else "",
            "status": s.status,
            "payment_status": s.payment_status,
            "attendance_status": last_rec.status if last_rec else None,
        })

    hours = float(metrics.get("therapy_hours_2x") or 0)
    return {
        "therapy_started": bool(st.therapy_started),
        "weekly_sessions": st.weekly_sessions,
        "therapy_hours_2x": hours,
        "goal_hours": 250,
        "clinical_hours": float(metrics.get("clinical_hours") or 0),
        "supervision_hours": float(metrics.get("supervision_hours") or 0),
        "attendance_summary": summary,
        "recent_sessions": recent,
    }


_FEE_SCENARIO_FA: dict[str, str] = {
    "scenario_1_credit_returned": "بازگشت اعتبار",
    "scenario_2_no_action": "بدون اقدام مالی",
    "scenario_3_forfeited": "مصادره هزینه",
    "scenario_4_debt_created": "ایجاد بدهی",
    "excluded": "خارج از شمول",
    "triggered": "در حال بررسی",
}


@router.get("/me/fee-determination-summary")
async def my_fee_determination_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """داشبورد دانشجو برای فرایند #۷ (تعیین تکلیف هزینه جلسه).

    سهمیه غیبت سالانه = ceil(weekly_sessions × 3)؛ به‌علاوه ۴ سناریو نتیجه‌ای که
    به‌صورت خودکار توسط fee_determination ثبت شده‌اند.
    """
    r = await db.execute(select(Student).where(Student.user_id == current_user.id))
    st = r.scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="Student profile not found")

    att_svc = AttendanceService(db)
    quota_info = await att_svc.check_quota_exceeded(st.id)

    from app.services.payment_service import LEDGER_THERAPY, PaymentService

    pay = PaymentService(db)
    therapy_wallet = await pay.get_student_balance(st.id, category=LEDGER_THERAPY)

    inst_stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.process_code == "fee_determination",
            ProcessInstance.student_id == st.id,
        )
        .order_by(ProcessInstance.started_at.desc())
        .limit(50)
    )
    instances = list((await db.execute(inst_stmt)).scalars().all())
    inst_ids = [inst.id for inst in instances]
    ledger_by_ref: dict[str, list[FinancialRecord]] = {}
    if inst_ids:
        rec_rows = (
            await db.execute(
                select(FinancialRecord).where(
                    FinancialRecord.student_id == st.id,
                    FinancialRecord.reference_id.in_(inst_ids),
                )
            )
        ).scalars().all()
        for rec in rec_rows:
            ledger_by_ref.setdefault(str(rec.reference_id), []).append(rec)

    scenario_counts: dict[str, int] = {}
    outcomes: list[dict] = []
    credit_returned = 0
    forfeited = 0
    debt_created = 0
    last_fee_amount = None
    last_fee_record_type = None
    for inst in instances:
        ctx = inst.context_data or {}
        state = inst.current_state_code
        recs = ledger_by_ref.get(str(inst.id)) or []
        rec = recs[0] if recs else None
        amount = None
        record_type = None
        if rec is not None:
            amount = float(rec.amount)
            record_type = rec.record_type
        elif ctx.get("fee_ledger_amount") is not None:
            try:
                amount = float(ctx.get("fee_ledger_amount"))
            except (TypeError, ValueError):
                amount = None
            record_type = ctx.get("fee_ledger_record_type")
        if inst.is_completed:
            scenario_counts[state] = scenario_counts.get(state, 0) + 1
            if state == "scenario_1_credit_returned":
                credit_returned += 1
            elif state == "scenario_3_forfeited":
                forfeited += 1
            elif state == "scenario_4_debt_created":
                debt_created += 1
            if last_fee_amount is None and amount is not None:
                last_fee_amount = amount
                last_fee_record_type = record_type
        outcomes.append({
            "instance_id": str(inst.id),
            "state": state,
            "state_fa": _FEE_SCENARIO_FA.get(state, state),
            "is_completed": bool(inst.is_completed),
            "is_cancelled": bool(inst.is_cancelled),
            "session_date": ctx.get("session_date"),
            "session_paid": ctx.get("session_paid"),
            "summary_fa": ctx.get("ui_completion_summary_fa"),
            "amount_toman": amount,
            "record_type": record_type,
            "started_at": inst.started_at.isoformat() if inst.started_at else None,
            "completed_at": inst.completed_at.isoformat() if inst.completed_at else None,
        })

    return {
        "weekly_sessions": st.weekly_sessions,
        "absence_quota": quota_info["quota"],
        "absences_used": quota_info["absences"],
        "remaining_quota": quota_info["remaining"],
        "quota_exceeded": quota_info["exceeded"],
        "therapy_wallet_balance_toman": float(therapy_wallet.get("balance") or 0),
        "last_fee_amount_toman": last_fee_amount,
        "last_fee_record_type": last_fee_record_type,
        "credit_returned_count": credit_returned,
        "forfeited_count": forfeited,
        "debt_created_count": debt_created,
        "scenario_counts": scenario_counts,
        "outcomes": outcomes,
    }


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

    meeting_url_set = "meeting_url" in data
    links_unlocked_set = "links_unlocked" in data
    for k, v in data.items():
        setattr(s, k, v)
    if links_unlocked_set and s.links_unlocked:
        if s.payment_status not in ("paid", "waived"):
            raise HTTPException(
                status_code=409,
                detail="لینک دانشجو پس از پرداخت یا معافیت قابل فعال‌سازی است.",
            )
        if not (s.meeting_url or "").strip():
            raise HTTPException(
                status_code=409,
                detail="ابتدا لینک جلسه (الوکام یا دستی) باید ساخته شود.",
            )
    if meeting_url_set and (s.meeting_url or "").strip():
        if s.payment_status in ("paid", "waived") and "links_unlocked" not in data:
            s.links_unlocked = True
    await db.flush()
    await db.refresh(s)
    logger.info(
        "therapy_session_updated session_id=%s user_id=%s fields=%s",
        session_id,
        str(current_user.id),
        list(body.model_dump(exclude_unset=True).keys()),
    )
    return _to_out(s, viewer=current_user)
