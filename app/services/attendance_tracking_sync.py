"""هم‌ترازی نمونه‌های فرایند attendance_tracking با جلسات درمان (TherapySession)."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, Student, TherapySession, User
from app.services.process_service import ProcessService

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _ctx(inst: ProcessInstance) -> dict[str, Any]:
    return dict(StateMachineEngine._as_mapping(inst.context_data))


async def is_student_on_educational_leave(db: AsyncSession, student_id: uuid.UUID) -> bool:
    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == "educational_leave",
        ProcessInstance.current_state_code.in_(["on_leave", "return_reminder_sent"]),
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    r = await db.execute(stmt)
    return r.scalars().first() is not None


async def build_attendance_context_from_session(
    db: AsyncSession,
    session: TherapySession,
) -> dict[str, Any]:
    student = await db.get(Student, session.student_id)
    on_leave = await is_student_on_educational_leave(db, session.student_id)
    ws = int(student.weekly_sessions) if student and student.weekly_sessions else 1
    return {
        "therapy_session_id": str(session.id),
        "session_id": str(session.id),
        "session_date": session.session_date.isoformat(),
        "record_date": session.session_date.isoformat(),
        "session_paid": session.payment_status in ("paid", "waived"),
        "session_cancelled": session.status == "cancelled",
        "student_on_leave": on_leave,
        "weekly_sessions": ws,
    }


async def find_attendance_instance_for_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    include_completed: bool = False,
) -> Optional[ProcessInstance]:
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "attendance_tracking",
        ProcessInstance.is_cancelled == False,
    )
    if not include_completed:
        stmt = stmt.where(ProcessInstance.is_completed == False)
    r = await db.execute(stmt)
    sid_s = str(session_id)
    for inst in r.scalars().all():
        ctx = _ctx(inst)
        if str(ctx.get("therapy_session_id") or ctx.get("session_id") or "") == sid_s:
            return inst
    return None


async def merge_context_into_instance(inst: ProcessInstance, new_data: dict[str, Any]) -> None:
    cur = _ctx(inst)
    cur.update(new_data)
    inst.context_data = cur
    flag_modified(inst, "context_data")


async def ensure_attendance_instance_for_session(
    db: AsyncSession,
    session: TherapySession,
) -> Optional[ProcessInstance]:
    """برای هر جلسهٔ برنامه‌ریزی‌شده یک نمونه attendance_tracking بساز (اگر نباشد)."""
    if session.status not in ("scheduled", "completed", "cancelled"):
        return None
    existing = await find_attendance_instance_for_session(db, session.id, include_completed=True)
    if existing:
        if existing.is_completed or existing.is_cancelled:
            return existing
        ctx = await build_attendance_context_from_session(db, session)
        await merge_context_into_instance(existing, ctx)
        return existing

    ctx = await build_attendance_context_from_session(db, session)
    svc = ProcessService(db)
    inst = await svc.start_process_for_student(
        process_code="attendance_tracking",
        student_id=session.student_id,
        actor_id=SYSTEM_ACTOR_ID,
        actor_role="system",
        initial_context=ctx,
    )
    return inst


async def cancel_attendance_instances_for_therapy_session_ids(
    db: AsyncSession,
    session_ids: list[uuid.UUID],
) -> int:
    """هنگام حذف/بازتولید جلسات، نمونه‌های باز را لغو کن."""
    n = 0
    for sid in session_ids:
        inst = await find_attendance_instance_for_session(db, sid, include_completed=True)
        if inst and not inst.is_completed and not inst.is_cancelled:
            inst.is_cancelled = True
            n += 1
    return n


async def refresh_attendance_instance_from_db(db: AsyncSession, inst: ProcessInstance) -> None:
    ctx0 = _ctx(inst)
    raw = ctx0.get("therapy_session_id") or ctx0.get("session_id")
    if not raw:
        return
    try:
        sid = uuid.UUID(str(raw))
    except (TypeError, ValueError):
        return
    ts = await db.get(TherapySession, sid)
    if not ts:
        return
    merged = await build_attendance_context_from_session(db, ts)
    await merge_context_into_instance(inst, merged)


async def sync_all_open_attendance_instances_from_sessions(db: AsyncSession) -> int:
    """پیش از تریگر تقویم، context همهٔ نمونه‌های باز را با DB هم‌تراز کن."""
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "attendance_tracking",
        ProcessInstance.is_completed == False,
        ProcessInstance.is_cancelled == False,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for inst in rows:
        try:
            await refresh_attendance_instance_from_db(db, inst)
        except Exception:
            logger.exception("refresh attendance instance %s failed", inst.id)
    return len(rows)


async def apply_therapy_attendance_via_process(
    db: AsyncSession,
    session: TherapySession,
    attendance_status: str,
    therapist_user: User,
) -> tuple[bool, Optional[str]]:
    """
    ثبت حضور/غیاب از مسیر ماشین حالت attendance_tracking (بدون رکورد تکراری در لایهٔ سرویس).
    attendance_status: present | absent_excused | absent_unexcused
    """
    inst = await find_attendance_instance_for_session(db, session.id)
    if not inst:
        return False, "no_attendance_process"

    await refresh_attendance_instance_from_db(db, inst)
    await db.refresh(inst)

    engine = StateMachineEngine(db)
    actor_id = therapist_user.id
    role = actor_role_for_therapy_attendance(therapist_user)

    today = datetime.now(timezone.utc).date()

    async def advance_scheduled_if_due() -> Optional[str]:
        await db.refresh(inst)
        if inst.current_state_code != "session_scheduled":
            return None
        sd = session.session_date
        if sd > today:
            return "session_day_not_reached"
        r = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="session_time_reached",
            actor_id=SYSTEM_ACTOR_ID,
            actor_role="system",
            payload={},
        )
        await db.flush()
        if not r.success:
            return r.error or "session_time_reached_failed"
        return None

    err = await advance_scheduled_if_due()
    if err:
        return False, err

    await db.refresh(inst)
    st = inst.current_state_code

    if st == "recording_closed":
        return True, None
    if st == "auto_absence_unpaid":
        return False, "unpaid_session_branch"
    if st not in ("therapist_recording",):
        if st == "session_scheduled":
            return False, "still_scheduled"
        return False, f"unexpected_state:{st}"

    if attendance_status == "present":
        r = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="student_present",
            actor_id=actor_id,
            actor_role=role,
            payload={},
        )
        if not r.success:
            return False, r.error or "student_present_failed"
        return True, None

    if attendance_status in ("absent_excused", "absent_unexcused"):
        r1 = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="student_absent",
            actor_id=actor_id,
            actor_role=role,
            payload={},
        )
        if not r1.success:
            return False, r1.error or "student_absent_failed"
        await db.refresh(inst)
        if inst.current_state_code != "absence_recorded":
            return False, "expected_absence_recorded"

        excused = attendance_status == "absent_excused"
        payload2 = {"absence_excused": excused, "absence_type": "student"}
        trigger = "absence_excused" if excused else "absence_unexcused"
        r2 = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event=trigger,
            actor_id=actor_id,
            actor_role=role,
            payload=payload2,
        )
        if not r2.success:
            return False, r2.error or "absence_finalize_failed"
        return True, None

    return False, "bad_attendance_status"


def actor_role_for_therapy_attendance(user: User) -> str:
    """ترنزیشن‌های attendance نقش therapist می‌خواهند؛ کارمندان مؤثر مانند درمانگر."""
    ur = (user.role or "").strip()
    if ur in ("admin", "staff", "therapist"):
        return "therapist"
    return ur or "therapist"
