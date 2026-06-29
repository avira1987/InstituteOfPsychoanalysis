"""محاسبات و دادهٔ UI برای فرایند ۵۶ — کنسل جلسات کلاس‌های درسی."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, Student, User
from app.services.instructor_course_roster_service import (
    assigned_course_codes_for_user,
    get_course_roster,
    user_may_access_course,
)
from app.utils.date_utils import (
    add_minutes_to_hhmm,
    default_term_start,
    friday_of_term_week,
)

DEFAULT_SESSION_DURATION_MIN = 90

_ORDINAL_LABELS_FA = {
    1: "اول",
    2: "دوم",
    3: "سوم",
    4: "چهارم",
}


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


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


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_key(course_code: str, session_number: Any, session_date: Any) -> str:
    sd = _parse_date(session_date)
    date_part = sd.isoformat() if sd else str(session_date or "")
    return f"{course_code}|{session_number}|{date_part}"


def parse_session_key(raw: Any) -> Optional[dict[str, str]]:
    if raw is None or str(raw).strip() == "":
        return None
    parts = str(raw).split("|", 2)
    if len(parts) < 3:
        return None
    return {
        "course_code": parts[0],
        "session_number": parts[1],
        "session_date": parts[2],
    }


def _course_label_from_assignment(row: dict[str, Any]) -> str:
    return str(
        row.get("course_name")
        or row.get("course_code")
        or row.get("code")
        or ""
    ).strip()


async def list_all_term_courses(db: AsyncSession) -> list[dict[str, Any]]:
    """همهٔ دروس انتساب‌یافته در ترم — از پروفایل همهٔ مدرسین/کمک‌مدرسین."""
    stmt = select(User).where(User.role.in_(("instructor", "teaching_assistant")))
    users = list((await db.execute(stmt)).scalars().all())
    courses: dict[str, dict[str, Any]] = {}
    for user in users:
        for row in list_assignable_courses(user):
            code = row.get("value")
            if code and code not in courses:
                courses[str(code)] = row
    return sorted(courses.values(), key=lambda x: x.get("label_fa") or "")


def list_assignable_courses(user: User, *, all_term: bool = False) -> list[dict[str, Any]]:
    """دروس قابل انتخاب برای کنسلی — مدرس یا همهٔ ترم برای کمیته."""
    role = (user.role or "").strip()
    meta = _as_mapping(user.profile_meta)
    items = meta.get("semester_course_assignments") or []
    if not isinstance(items, list):
        items = []

    courses: dict[str, dict[str, Any]] = {}

    if all_term or role in (
        "admin",
        "staff",
        "scientific_officer_course_committee",
        "course_committee_executive",
        "deputy_education",
    ):
        for row in items:
            if not isinstance(row, dict):
                continue
            code = _course_label_from_assignment(row)
            if not code:
                continue
            courses[code] = {
                "value": code,
                "label_fa": code,
                "day": row.get("day") or "",
                "time": row.get("time") or "",
                "term_label_fa": row.get("term_label_fa") or "",
            }
    elif role in ("instructor", "teaching_assistant"):
        allowed = assigned_course_codes_for_user(user)
        for row in items:
            if not isinstance(row, dict):
                continue
            code = _course_label_from_assignment(row)
            if code not in allowed:
                continue
            courses[code] = {
                "value": code,
                "label_fa": code,
                "day": row.get("day") or "",
                "time": row.get("time") or "",
                "term_label_fa": row.get("term_label_fa") or "",
            }
        for code in sorted(allowed):
            if code not in courses:
                courses[code] = {"value": code, "label_fa": code, "day": "", "time": ""}
    else:
        for code in sorted(assigned_course_codes_for_user(user)):
            courses[code] = {"value": code, "label_fa": code, "day": "", "time": ""}

    return sorted(courses.values(), key=lambda x: x.get("label_fa") or "")


async def _resolve_term_start(db: AsyncSession, student: Optional[Student] = None) -> date:
    from app.services.institute_calendar_service import get_active_calendar

    cal = await get_active_calendar(db)
    if cal and cal.term_start_date:
        return cal.term_start_date
    if student:
        extra = _as_mapping(student.extra_data)
        raw = extra.get("term_start_date")
        if raw:
            parsed = _parse_date(raw)
            if parsed:
                return parsed
    return default_term_start()


def _session_status_fa(sess: dict[str, Any], today: date) -> str:
    if sess.get("cancelled") is True or str(sess.get("status") or "").lower() == "cancelled":
        return "کنسل‌شده"
    if sess.get("attendance_locked") is True:
        return "قفل"
    sd = _parse_date(sess.get("session_date") or sess.get("date"))
    if sd and sd < today:
        return "گذشته"
    return "قابل کنسلی"


def _is_cancellable(sess: dict[str, Any], today: date) -> bool:
    if sess.get("cancelled") is True or str(sess.get("status") or "").lower() == "cancelled":
        return False
    if sess.get("attendance_locked") is True:
        return False
    if sess.get("is_makeup") is True:
        return False
    return True


async def aggregate_course_sessions(
    db: AsyncSession,
    course_code: str,
    *,
    include_past: bool = True,
) -> list[dict[str, Any]]:
    """تجمیع جلسات درس از lms.course_sessions دانشجویان ثبت‌نام‌شده."""
    code = str(course_code or "").strip()
    if not code:
        return []

    today = datetime.now(timezone.utc).date()
    roster = await get_course_roster(db, code)
    seen: dict[str, dict[str, Any]] = {}

    for entry in roster:
        if entry.get("role") == "teaching_assistant":
            continue
        sid = entry.get("student_id")
        if not sid or str(sid).startswith("ta:"):
            continue
        try:
            student = await db.get(Student, uuid.UUID(str(sid)))
        except (TypeError, ValueError):
            continue
        if not student:
            continue
        extra = _as_mapping(student.extra_data)
        lms = _as_mapping(extra.get("lms"))
        sessions = lms.get("course_sessions") or []
        if not isinstance(sessions, list):
            continue
        for sess in sessions:
            if not isinstance(sess, dict):
                continue
            sess_course = str(sess.get("course_id") or sess.get("course_code") or "")
            if sess_course and sess_course != code:
                continue
            sn = sess.get("session_index") or sess.get("session_number")
            sd_raw = sess.get("session_date") or sess.get("date")
            sd = _parse_date(sd_raw)
            if not include_past and sd and sd < today:
                continue
            key = session_key(code, sn, sd_raw)
            if key in seen:
                continue
            time_str = str(sess.get("session_time") or sess.get("start_time") or "").strip()
            status_fa = _session_status_fa(sess, today)
            cancellable = _is_cancellable(sess, today)
            seen[key] = {
                "value": key,
                "session_key": key,
                "label_fa": (
                    f"جلسه {sn or '—'} — {sd.isoformat() if sd else sd_raw or '—'}"
                    f"{f' ساعت {time_str}' if time_str else ''}"
                ),
                "session_number": sn,
                "session_date": sd.isoformat() if sd else str(sd_raw or ""),
                "session_time": time_str,
                "status_fa": status_fa,
                "cancellable": cancellable,
                "cancelled": sess.get("cancelled") is True,
            }

    result = list(seen.values())
    result.sort(key=lambda x: (x.get("session_date") or "", str(x.get("session_number") or "")))
    return result


async def count_course_cancellations_this_term(
    db: AsyncSession,
    course_code: str,
    term_start: date,
) -> int:
    """تعداد کنسلی‌های ثبت‌شده برای درس در ترم جاری."""
    code = str(course_code or "").strip()
    count = 0

    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "class_session_cancellation",
        ProcessInstance.is_completed.is_(True),
        ProcessInstance.is_cancelled.is_(False),
    )
    instances = list((await db.execute(stmt)).scalars().all())
    for inst in instances:
        ctx = StateMachineEngine._as_mapping(inst.context_data)
        lesson = str(ctx.get("lesson_id") or ctx.get("course_code") or "")
        if lesson != code:
            continue
        applied = ctx.get("cancellation_applied_at") or ctx.get("submitted_at")
        if applied:
            count += 1

    roster = await get_course_roster(db, code)
    cancelled_keys: set[str] = set()
    for entry in roster:
        sid = entry.get("student_id")
        if not sid or str(sid).startswith("ta:"):
            continue
        try:
            student = await db.get(Student, uuid.UUID(str(sid)))
        except (TypeError, ValueError):
            continue
        if not student:
            continue
        lms = _as_mapping(_as_mapping(student.extra_data).get("lms"))
        for sess in lms.get("course_sessions") or []:
            if not isinstance(sess, dict):
                continue
            if sess.get("cancelled") is True and not sess.get("is_makeup"):
                sc = str(sess.get("course_id") or sess.get("course_code") or code)
                if sc != code:
                    continue
                sd = sess.get("session_date") or sess.get("date")
                sn = sess.get("session_index") or sess.get("session_number")
                cancelled_keys.add(session_key(code, sn, sd))

    return max(count, len(cancelled_keys))


def compute_makeup_datetime(
    term_start: date,
    ordinal: int,
    usual_time: str,
    *,
    session_duration_min: int = DEFAULT_SESSION_DURATION_MIN,
) -> tuple[date, str, str]:
    """
    محاسبه تاریخ و ساعت جبرانی بر اساس شماره کنسلی ترم.
    Returns: (makeup_date, makeup_time, term_week_makeup_label)
    """
    ord_n = max(1, min(ordinal, 4))
    usual = str(usual_time or "10:00").strip() or "10:00"

    if ord_n in (1, 2):
        friday = friday_of_term_week(term_start, 15)
        week_label = "هفته ۱۵"
    else:
        friday = friday_of_term_week(term_start, 16)
        week_label = "هفته ۱۶"

    if ord_n in (1, 3):
        makeup_time = usual
    else:
        makeup_time = add_minutes_to_hhmm(usual, session_duration_min)

    ordinal_label = _ORDINAL_LABELS_FA.get(ord_n, str(ord_n))
    summary = f"کنسلی {ordinal_label} — جمعه {week_label} — {friday.isoformat()} ساعت {makeup_time}"
    return friday, makeup_time, summary


def _usual_time_for_course(user: User, course_code: str, assignment_rows: list[dict]) -> str:
    for row in assignment_rows:
        if not isinstance(row, dict):
            continue
        if _course_label_from_assignment(row) == course_code:
            t = row.get("time")
            if t:
                return str(t).strip()
    return "10:00"


async def build_class_session_cancellation_context(
    db: AsyncSession,
    user: Optional[User],
    instance_ctx: dict[str, Any],
    *,
    form_values: Optional[dict[str, Any]] = None,
    all_term: bool = False,
    student: Optional[Student] = None,
) -> dict[str, Any]:
    """Enrichment برای UI و prefill فرم کنسلی کلاس."""
    merged = {**_as_mapping(instance_ctx), **_as_mapping(form_values)}
    out: dict[str, Any] = {}

    if user:
        if all_term:
            courses = await list_all_term_courses(db)
        else:
            courses = list_assignable_courses(user, all_term=False)
        out["assignable_courses"] = courses
        meta = _as_mapping(user.profile_meta)
        assignments = meta.get("semester_course_assignments") or []
    elif merged.get("assignable_courses"):
        courses = merged["assignable_courses"]
        out["assignable_courses"] = courses
        assignments = []
    else:
        courses = []
        assignments = []

    lesson_id = str(merged.get("lesson_id") or merged.get("course_code") or "").strip()
    session_raw = merged.get("session_to_cancel")

    term_start = await _resolve_term_start(db, student)

    if lesson_id:
        sessions = await aggregate_course_sessions(db, lesson_id)
        out["upcoming_cancellable_sessions"] = sessions
        out["cancellable_sessions"] = [s for s in sessions if s.get("cancellable")]

        ordinal = await count_course_cancellations_this_term(db, lesson_id, term_start) + 1
        out["cancellation_ordinal"] = ordinal
        out["cancellation_ordinal_fa"] = _ORDINAL_LABELS_FA.get(ordinal, str(ordinal))

        usual_time = str(merged.get("usual_class_time") or "").strip()
        if not usual_time and user:
            usual_time = _usual_time_for_course(user, lesson_id, assignments)
        if not usual_time:
            usual_time = "10:00"
        out["usual_class_time"] = usual_time

        makeup_date, makeup_time, summary = compute_makeup_datetime(
            term_start, ordinal, usual_time
        )
        out["makeup_date"] = makeup_date.isoformat()
        out["makeup_time"] = makeup_time
        out["makeup_summary_fa"] = summary
        out["term_week_makeup_label"] = (
            "هفته ۱۵" if ordinal <= 2 else "هفته ۱۶"
        )

        if session_raw:
            parsed = parse_session_key(session_raw)
            if parsed:
                out["selected_session"] = parsed
                for s in sessions:
                    if s.get("value") == str(session_raw):
                        out["selected_session_detail"] = s
                        break
    elif courses:
        out["assignable_courses"] = courses

    if merged.get("violation_pending"):
        out["violation_pending"] = True
        out["violation_hint_fa"] = (
            "تخلف نظارت ۲ ساعته ثبت شده است. در اسرع وقت کنسلی و جبرانی را تأیید کنید."
        )

    return out


async def preview_cancellation(
    db: AsyncSession,
    user: User,
    course_code: str,
    session_key_raw: Optional[str] = None,
    *,
    all_term: bool = False,
) -> dict[str, Any]:
    """پیش‌نمایش زنده برای API panel."""
    ctx = {"lesson_id": course_code}
    if session_key_raw:
        ctx["session_to_cancel"] = session_key_raw
    return await build_class_session_cancellation_context(
        db, user, ctx, form_values=ctx, all_term=all_term
    )


async def validate_cancellation_form(
    db: AsyncSession,
    user: User,
    lesson_id: str,
    session_to_cancel: Any,
    *,
    all_term: bool = False,
) -> Optional[str]:
    code = str(lesson_id or "").strip()
    if not code:
        return "نام درس را انتخاب کنید."
    if user and not all_term and not user_may_access_course(user, code):
        role = (user.role or "").strip()
        if role not in ("admin", "staff", "scientific_officer_course_committee", "course_committee_executive"):
            return "این درس به شما انتساب داده نشده است."
    if not session_to_cancel or str(session_to_cancel).strip() == "":
        return "جلسه جهت کنسلی را انتخاب کنید."
    parsed = parse_session_key(session_to_cancel)
    if not parsed:
        return "جلسه انتخاب‌شده نامعتبر است."
    sessions = await aggregate_course_sessions(db, code)
    allowed = {s["value"] for s in sessions if s.get("cancellable")}
    if str(session_to_cancel) not in allowed:
        return "این جلسه قابل کنسلی نیست (قفل، کنسل‌شده، یا گذشته)."
    return None


def _update_sessions_for_student(
    lms: dict[str, Any],
    course_code: str,
    session_number: Any,
    session_date: str,
    makeup_row: dict[str, Any],
) -> bool:
    """Mark session cancelled and append makeup in course_sessions."""
    sessions = list(lms.get("course_sessions") or [])
    if not isinstance(sessions, list):
        sessions = []
    updated = False
    now_iso = _utcnow_iso()

    for sess in sessions:
        if not isinstance(sess, dict):
            continue
        sc = str(sess.get("course_id") or sess.get("course_code") or "")
        if sc and sc != course_code:
            continue
        sn = sess.get("session_index") or sess.get("session_number")
        sd = str(sess.get("session_date") or sess.get("date") or "")[:10]
        if str(sn) == str(session_number) and sd == str(session_date)[:10]:
            sess["cancelled"] = True
            sess["status"] = "cancelled"
            sess["attendance_locked"] = True
            sess["cancelled_at"] = now_iso
            updated = True

    makeup_exists = any(
        isinstance(s, dict)
        and s.get("is_makeup") is True
        and str(s.get("makeup_for_session") or "") == session_key(course_code, session_number, session_date)
        for s in sessions
    )
    if not makeup_exists:
        sessions.append(makeup_row)
        updated = True

    if updated:
        lms["course_sessions"] = sessions
    return updated


async def apply_class_cancellation(
    db: AsyncSession,
    instance: ProcessInstance,
    actor_id: Any,
) -> dict[str, Any]:
    """اعمال کنسلی: قفل جلسه اصلی + ثبت جبرانی در LMS همهٔ دانشجویان."""
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    lesson_id = str(ctx.get("lesson_id") or ctx.get("course_code") or "").strip()
    session_raw = ctx.get("session_to_cancel")
    makeup_date = str(ctx.get("makeup_date") or "").strip()
    makeup_time = str(ctx.get("makeup_time") or "").strip()

    if not lesson_id or not session_raw or not makeup_date or not makeup_time:
        raise ValueError("درس، جلسه، و زمان جبرانی الزامی است.")

    parsed = parse_session_key(session_raw)
    if not parsed:
        raise ValueError("جلسه انتخاب‌شده نامعتبر است.")

    session_number = parsed["session_number"]
    session_date = parsed["session_date"]
    now_iso = _utcnow_iso()

    makeup_row = {
        "course_id": lesson_id,
        "course_code": lesson_id,
        "session_index": f"makeup_{session_number}",
        "session_number": f"makeup_{session_number}",
        "session_date": makeup_date,
        "date": makeup_date,
        "session_time": makeup_time,
        "start_time": makeup_time,
        "is_makeup": True,
        "makeup_for_session": session_key(lesson_id, session_number, session_date),
        "makeup_for_session_number": session_number,
        "makeup_for_session_date": session_date,
        "created_at": now_iso,
        "status": "scheduled",
    }

    roster = await get_course_roster(db, lesson_id)
    students_updated = 0

    for entry in roster:
        if entry.get("role") == "teaching_assistant":
            continue
        sid = entry.get("student_id")
        if not sid or str(sid).startswith("ta:"):
            continue
        try:
            student = await db.get(Student, uuid.UUID(str(sid)))
        except (TypeError, ValueError):
            continue
        if not student:
            continue
        extra = _as_mapping(student.extra_data)
        lms = _as_mapping(extra.get("lms"))
        if _update_sessions_for_student(
            lms, lesson_id, session_number, session_date, dict(makeup_row)
        ):
            extra["lms"] = lms
            student.extra_data = extra
            flag_modified(student, "extra_data")
            students_updated += 1

    if actor_id:
        try:
            actor = await db.get(User, uuid.UUID(str(actor_id)))
            if actor:
                meta = _as_mapping(actor.profile_meta)
                history = list(meta.get("class_cancellation_history") or [])
                history.append({
                    "course_code": lesson_id,
                    "session_number": session_number,
                    "session_date": session_date,
                    "makeup_date": makeup_date,
                    "makeup_time": makeup_time,
                    "at": now_iso,
                    "instance_id": str(instance.id),
                })
                meta["class_cancellation_history"] = history
                meta["class_cancellation_count"] = int(meta.get("class_cancellation_count") or 0) + 1
                actor.profile_meta = meta
                flag_modified(actor, "profile_meta")
        except (TypeError, ValueError):
            pass

    result = {
        "course_code": lesson_id,
        "cancelled_session": {
            "session_number": session_number,
            "session_date": session_date,
        },
        "makeup_session": {
            "session_date": makeup_date,
            "session_time": makeup_time,
        },
        "students_updated": students_updated,
        "cancellation_applied_at": now_iso,
        "sms_pending": True,
    }

    ctx.update(result)
    instance.context_data = ctx
    flag_modified(instance, "context_data")

    return result
