"""سرویس فرایند ۶۷ — خاتمه درس سوپرویژن زنده (حضور دوگانه، بسته ۱۸ جلسه، ماشه‌های per-student)."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student

logger = logging.getLogger(__name__)

PROCESS_CODE = "live_supervision_course_completion"
NORMAL_REQUIRED = 15
MIRROR_REQUIRED = 3
TOTAL_REQUIRED = 18


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_admission_cohort(student: Student) -> int:
    """سال ورود از student_code یا extra_data — عدد کوچکتر = ورودی قدیمی‌تر."""
    extra = _as_mapping(student.extra_data)
    cohort = extra.get("admission_cohort") or extra.get("entry_year") or extra.get("admission_year")
    if cohort is not None:
        try:
            return int(cohort)
        except (TypeError, ValueError):
            pass
    code = (student.student_code or "").strip()
    m = re.search(r"(\d{2,4})", code)
    if m:
        try:
            n = int(m.group(1))
            return n if n < 100 else n % 100
        except ValueError:
            pass
    if student.enrollment_date:
        return student.enrollment_date.year
    return 9999


def clinical_hours_for_student(student: Student) -> float:
    extra = _as_mapping(student.extra_data)
    try:
        return float(extra.get("clinical_hours") or 0)
    except (TypeError, ValueError):
        return 0.0


def live_supervision_bucket(lms: dict[str, Any], course_code: str) -> dict[str, Any]:
    root = _as_mapping(lms.get("live_supervision"))
    entry = _as_mapping(root.get(course_code) or root.get(str(course_code)))
    if not entry:
        entry = {
            "normal_count": 0,
            "mirror_count": 0,
            "calendar_sessions": 0,
            "absences": 0,
            "compensation_pending": 0,
            "compensation_paid": 0,
            "mirror_writes": [],
            "package_active": True,
            "session_log": [],
        }
    return entry


def ensure_live_supervision_progress(student: Student, course_code: str) -> dict[str, Any]:
    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    root = dict(_as_mapping(lms.get("live_supervision")))
    code = str(course_code or "").strip()
    bucket = live_supervision_bucket(lms, code)
    root[code] = bucket
    lms["live_supervision"] = root
    extra["lms"] = lms
    student.extra_data = extra
    flag_modified(student, "extra_data")
    return bucket


def sort_live_supervision_roster(roster: list[dict[str, Any]], students_by_id: dict[str, Student]) -> list[dict[str, Any]]:
    """اولویت: سال ورود پایین‌تر (قدیمی‌تر)، سپس ساعات بالینی بیشتر."""

    def sort_key(row: dict[str, Any]) -> tuple[int, float, str]:
        sid = str(row.get("student_id") or "")
        st = students_by_id.get(sid)
        cohort = parse_admission_cohort(st) if st else 9999
        hours = clinical_hours_for_student(st) if st else 0.0
        return (cohort, -hours, row.get("student_code") or sid)

    return sorted(list(roster), key=sort_key)


def roster_to_dual_attendance_rows(
    roster: list[dict[str, Any]],
    progress_by_student: Optional[dict[str, dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """ردیف‌های حضور دوگانه برای UI مدرس."""
    progress_by_student = progress_by_student or {}
    rows: list[dict[str, Any]] = []
    for entry in roster:
        sid = str(entry.get("student_id") or "")
        prog = progress_by_student.get(sid) or {}
        rows.append({
            "student_id": sid,
            "student_name": entry.get("name_fa") or entry.get("student_code") or sid,
            "role": entry.get("role") or "student",
            "normal_present": False,
            "mirror_present": False,
            "normal_count": int(prog.get("normal_count") or 0),
            "mirror_count": int(prog.get("mirror_count") or 0),
            "admission_cohort": prog.get("admission_cohort"),
        })
    return rows


async def load_students_map(db: AsyncSession, student_ids: list[str]) -> dict[str, Student]:
    if not student_ids:
        return {}
    uuids = []
    for sid in student_ids:
        try:
            uuids.append(uuid.UUID(str(sid)))
        except ValueError:
            continue
    if not uuids:
        return {}
    result = await db.execute(select(Student).where(Student.id.in_(uuids)))
    out: dict[str, Student] = {}
    for st in result.scalars().all():
        out[str(st.id)] = st
    return out


async def get_progress_for_course(
    db: AsyncSession,
    course_code: str,
    roster: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """خلاصه پیشرفت هر دانشجو برای API پنل مدرس."""
    ids = [str(r.get("student_id")) for r in roster if r.get("student_id")]
    students = await load_students_map(db, ids)
    sorted_roster = sort_live_supervision_roster(roster, students)
    rows: list[dict[str, Any]] = []
    for entry in sorted_roster:
        sid = str(entry.get("student_id") or "")
        st = students.get(sid)
        if not st:
            continue
        bucket = live_supervision_bucket(_as_mapping(st.extra_data).get("lms") or {}, course_code)
        normal = int(bucket.get("normal_count") or 0)
        mirror = int(bucket.get("mirror_count") or 0)
        rows.append({
            "student_id": sid,
            "student_name": entry.get("name_fa") or st.student_code or sid,
            "student_code": st.student_code,
            "admission_cohort": parse_admission_cohort(st),
            "clinical_hours": clinical_hours_for_student(st),
            "normal_count": normal,
            "mirror_count": mirror,
            "total_attendance": normal + mirror,
            "calendar_sessions": int(bucket.get("calendar_sessions") or 0),
            "absences": int(bucket.get("absences") or 0),
            "compensation_pending": int(bucket.get("compensation_pending") or 0),
            "compensation_paid": int(bucket.get("compensation_paid") or 0),
            "package_active": bucket.get("package_active", True),
            "is_complete": normal >= NORMAL_REQUIRED and mirror >= MIRROR_REQUIRED,
        })
    return rows


async def find_or_start_completion_instance(
    db: AsyncSession,
    student_id: uuid.UUID,
    course_code: str,
    actor_id: uuid.UUID,
) -> ProcessInstance | None:
    from app.core.engine import StateMachineEngine

    result = await db.execute(
        select(ProcessInstance).where(
            ProcessInstance.student_id == student_id,
            ProcessInstance.process_code == PROCESS_CODE,
            ProcessInstance.is_completed.is_(False),
        )
    )
    for inst in result.scalars().all():
        ctx = _as_mapping(inst.context_data)
        cc = str(ctx.get("course_code") or ctx.get("course_name") or "")
        if not cc or cc == course_code:
            return inst

    engine = StateMachineEngine(db)
    inst = await engine.start_process(
        process_code=PROCESS_CODE,
        student_id=student_id,
        actor_id=actor_id,
        actor_role="system",
        initial_context={
            "course_code": course_code,
            "course_name": course_code,
        },
    )
    return inst


async def _trigger_student_transition(
    db: AsyncSession,
    student_id: uuid.UUID,
    course_code: str,
    trigger_event: str,
    actor_id: uuid.UUID,
    payload: Optional[dict[str, Any]] = None,
) -> bool:
    from app.core.engine import StateMachineEngine

    inst = await find_or_start_completion_instance(db, student_id, course_code, actor_id)
    if not inst:
        return False
    engine = StateMachineEngine(db)
    result = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event=trigger_event,
        actor_id=actor_id,
        actor_role="system",
        payload=payload or {},
    )
    if not result.success:
        logger.info(
            "live_supervision transition skipped student=%s trigger=%s err=%s",
            student_id,
            trigger_event,
            result.error,
        )
        return False
    return True


async def record_dual_attendance(
    db: AsyncSession,
    *,
    course_code: str,
    session_date: str,
    attendance_rows: list[dict[str, Any]],
    actor_id: uuid.UUID,
    calendar_session_increment: bool = True,
) -> dict[str, Any]:
    """
    ثبت حضور دوگانه برای هر دانشجو؛ به‌روزرسانی LMS و ماشه‌های فرایند ۶۷.
    هر ردیف: student_id, normal_present (bool), mirror_present (bool), absent (bool optional).
    """
    code = str(course_code or "").strip()
    summary = {"updated": 0, "triggers": []}
    if not code or not attendance_rows:
        return summary

    ids = [str(r.get("student_id")) for r in attendance_rows if r.get("student_id")]
    students = await load_students_map(db, ids)

    for row in attendance_rows:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("student_id") or "")
        st = students.get(sid)
        if not st:
            continue

        normal_present = bool(row.get("normal_present"))
        mirror_present = bool(row.get("mirror_present"))
        is_absent = bool(row.get("absent")) or (not normal_present and not mirror_present)

        bucket = ensure_live_supervision_progress(st, code)
        if calendar_session_increment:
            bucket["calendar_sessions"] = int(bucket.get("calendar_sessions") or 0) + 1

        log = list(bucket.get("session_log") or [])
        log.append({
            "session_date": session_date,
            "normal_present": normal_present,
            "mirror_present": mirror_present,
            "absent": is_absent,
            "at": _utcnow_iso(),
        })
        bucket["session_log"] = log[-50:]

        if is_absent:
            bucket["absences"] = int(bucket.get("absences") or 0) + 1
        if normal_present:
            bucket["normal_count"] = int(bucket.get("normal_count") or 0) + 1
        if mirror_present:
            bucket["mirror_count"] = int(bucket.get("mirror_count") or 0) + 1
            bucket["last_mirror_at"] = _utcnow_iso()
            bucket["last_mirror_session_index"] = int(bucket.get("mirror_count") or 0)

        cal = int(bucket.get("calendar_sessions") or 0)
        if cal >= TOTAL_REQUIRED:
            absences = int(bucket.get("absences") or 0)
            pending = int(bucket.get("compensation_pending") or 0)
            if absences > pending:
                bucket["compensation_pending"] = absences - int(bucket.get("compensation_paid") or 0)

        extra = _as_mapping(st.extra_data)
        lms = _as_mapping(extra.get("lms"))
        root = dict(_as_mapping(lms.get("live_supervision")))
        root[code] = bucket
        lms["live_supervision"] = root
        extra["lms"] = lms
        st.extra_data = extra
        flag_modified(st, "extra_data")
        summary["updated"] += 1

        try:
            student_uuid = uuid.UUID(sid)
        except ValueError:
            continue

        normal = int(bucket.get("normal_count") or 0)
        mirror = int(bucket.get("mirror_count") or 0)
        total = normal + mirror

        if mirror_present and mirror <= MIRROR_REQUIRED:
            ok = await _trigger_student_transition(
                db,
                student_uuid,
                code,
                "mirror_attendance_recorded",
                actor_id,
                payload={
                    "mirror_session_index": mirror,
                    "mirror_session_date": session_date,
                    "days_since_mirror_session": 0,
                },
            )
            if ok:
                summary["triggers"].append({"student_id": sid, "event": "mirror_attendance_recorded"})

        if mirror_present and mirror == MIRROR_REQUIRED:
            ok = await _trigger_student_transition(
                db,
                student_uuid,
                code,
                "third_mirror_recorded",
                actor_id,
                payload={"days_since_third_mirror": 0, "third_mirror_at": _utcnow_iso()},
            )
            if ok:
                summary["triggers"].append({"student_id": sid, "event": "third_mirror_recorded"})

        if total >= TOTAL_REQUIRED and normal >= NORMAL_REQUIRED and mirror >= MIRROR_REQUIRED:
            ok = await _trigger_student_transition(
                db,
                student_uuid,
                code,
                "eighteenth_attendance_recorded",
                actor_id,
                payload={
                    "eighteenth_at": _utcnow_iso(),
                    "final_eval_sla_breach": False,
                    "live_supervision_normal_count": normal,
                    "live_supervision_mirror_count": mirror,
                },
            )
            if ok:
                summary["triggers"].append({"student_id": sid, "event": "eighteenth_attendance_recorded"})

    return summary


async def activate_compensation_payment(
    db: AsyncSession,
    student_id: uuid.UUID,
    course_code: str,
    sessions_count: int,
) -> dict[str, Any]:
    """فعال‌سازی لینک پرداخت جبرانی در LMS."""
    result = await db.execute(select(Student).where(Student.id == student_id))
    st = result.scalars().first()
    if not st:
        return {"ok": False, "error": "student_not_found"}
    bucket = ensure_live_supervision_progress(st, course_code)
    n = max(0, int(sessions_count))
    bucket["compensation_pending"] = n
    bucket["compensation_payment_url"] = f"/panel/student/payments?course={course_code}&sessions={n}"
    bucket["compensation_activated_at"] = _utcnow_iso()
    extra = _as_mapping(st.extra_data)
    lms = _as_mapping(extra.get("lms"))
    root = dict(_as_mapping(lms.get("live_supervision")))
    root[str(course_code)] = bucket
    lms["live_supervision"] = root
    extra["lms"] = lms
    st.extra_data = extra
    flag_modified(st, "extra_data")
    return {"ok": True, "compensation_pending": n, "payment_url": bucket.get("compensation_payment_url")}


async def mark_compensation_paid(
    db: AsyncSession,
    student_id: uuid.UUID,
    course_code: str,
    sessions_paid: int,
) -> None:
    result = await db.execute(select(Student).where(Student.id == student_id))
    st = result.scalars().first()
    if not st:
        return
    bucket = ensure_live_supervision_progress(st, course_code)
    paid = int(bucket.get("compensation_paid") or 0) + max(0, int(sessions_paid))
    bucket["compensation_paid"] = paid
    pending = int(bucket.get("compensation_pending") or 0)
    bucket["compensation_pending"] = max(0, pending - int(sessions_paid))
    bucket["package_active"] = True
    extra = _as_mapping(st.extra_data)
    lms = _as_mapping(extra.get("lms"))
    root = dict(_as_mapping(lms.get("live_supervision")))
    root[str(course_code)] = bucket
    lms["live_supervision"] = root
    extra["lms"] = lms
    st.extra_data = extra
    flag_modified(st, "extra_data")
