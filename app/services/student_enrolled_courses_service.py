"""دروس ثبت‌نام‌شده دانشجو + غنی‌سازی داشبورد مدرس."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.models.operational_models import Student, User
from app.services.instructor_course_roster_service import (
    get_course_roster,
    user_may_access_course,
)
from app.services.installment_access import student_course_join_fields


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _is_external_meeting_url(url: Any) -> bool:
    s = str(url or "").strip()
    if not s:
        return False
    if s.startswith("/panel/") or s.startswith("/online/"):
        return False
    return s.startswith("http://") or s.startswith("https://")


def _course_codes_from_enrolled(lms: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    for c in lms.get("enrolled_courses") or []:
        if isinstance(c, dict):
            code = str(c.get("code") or c.get("course_code") or "").strip()
        else:
            code = str(c or "").strip()
        if code and code not in codes:
            codes.append(code)
    return codes


def _attendance_summary(entry: dict[str, Any]) -> dict[str, Any]:
    sessions = [s for s in (entry.get("sessions") or []) if isinstance(s, dict)]
    present = sum(1 for s in sessions if str(s.get("status") or "").lower() == "present")
    absent = sum(
        1
        for s in sessions
        if str(s.get("status") or "").lower() in ("absent", "غایب", "absent_unexcused")
    )
    try:
        absence_count = int(entry.get("absence_count") or absent)
    except (TypeError, ValueError):
        absence_count = absent
    return {
        "sessions_recorded": len(sessions),
        "present_count": present,
        "absent_count": absent,
        "absence_count": absence_count,
        "sessions": [
            {
                "session_number": s.get("session_number"),
                "date": s.get("date") or s.get("session_date"),
                "status": s.get("status"),
            }
            for s in sessions
        ],
    }


async def list_student_enrolled_courses(
    db: AsyncSession,
    student: Student,
) -> dict[str, Any]:
    from app.services.institute_calendar_service import get_active_calendar
    from app.services.term_course_offering_service import get_offering_by_code

    extra = StateMachineEngine._as_mapping(student.extra_data)
    lms = StateMachineEngine._as_mapping(extra.get("lms"))
    cal = await get_active_calendar(db)
    term_code = cal.term_code if cal else None
    meta = StateMachineEngine._as_mapping(lms.get("course_link_meta"))
    lesson_att = StateMachineEngine._as_mapping(lms.get("lesson_attendance"))
    course_sessions = [
        s for s in (lms.get("course_sessions") or []) if isinstance(s, dict)
    ]

    items: list[dict[str, Any]] = []
    for code in _course_codes_from_enrolled(lms):
        offering = await get_offering_by_code(db, code, term_code=term_code)
        row_meta = meta.get(code) if isinstance(meta.get(code), dict) else {}
        portal = StateMachineEngine._as_mapping(lms.get("portal_course_links"))
        links = StateMachineEngine._as_mapping(lms.get("course_links"))
        meeting = ""
        if offering and getattr(offering, "online_meeting_url", None):
            meeting = str(offering.online_meeting_url or "").strip()
        if not _is_external_meeting_url(meeting):
            meeting = str(row_meta.get("online_meeting_url") or "").strip()
        if not _is_external_meeting_url(meeting):
            for candidate in (portal.get(code), links.get(code)):
                if _is_external_meeting_url(candidate):
                    meeting = str(candidate).strip()
                    break
        if not _is_external_meeting_url(meeting):
            meeting = ""

        att_entry = lesson_att.get(code) or lesson_att.get(str(code)) or {}
        if not isinstance(att_entry, dict):
            att_entry = {}
        summary = _attendance_summary(att_entry)
        upcoming = [
            s
            for s in course_sessions
            if str(s.get("course_id") or s.get("course_code") or "") == code
            and str(s.get("status") or "scheduled").lower() == "scheduled"
        ]
        upcoming.sort(key=lambda s: str(s.get("session_date") or s.get("date") or ""))
        next_session = upcoming[0] if upcoming else None

        join_fields = student_course_join_fields(
            course_code=code,
            has_external_url=_is_external_meeting_url(meeting),
        )
        items.append({
            "course_code": code,
            "course_name_fa": (
                (offering.course_name_fa if offering else None)
                or row_meta.get("course_name_fa")
                or code
            ),
            "day": (offering.day if offering else None) or row_meta.get("day"),
            "time_text": (
                (offering.time_text if offering else None)
                or row_meta.get("time_text")
            ),
            "classroom_location": (
                (offering.classroom_location if offering else None)
                or row_meta.get("classroom_location")
            ),
            "instructor_name": (
                (offering.instructor_name if offering else None)
                or row_meta.get("instructor_name")
            ),
            "teaching_assistant_name": (
                (offering.teaching_assistant_name if offering else None)
                or row_meta.get("teaching_assistant_name")
            ),
            **join_fields,
            "schedule_missing": offering is None and not row_meta,
            "attendance": summary,
            "next_session_date": (
                (next_session or {}).get("session_date")
                or (next_session or {}).get("date")
            ),
            "scheduled_sessions_count": len(
                [
                    s
                    for s in course_sessions
                    if str(s.get("course_id") or s.get("course_code") or "") == code
                ]
            ),
        })

    return {"courses": items, "term_code": term_code}


async def resolve_student_course_join_url(
    db: AsyncSession,
    student: Student,
    course_code: str,
) -> str:
    """URL واقعی کلاس برای redirect پس از احراز هویت — لینک خام در لیست دانشجو نیست."""
    from app.services.institute_calendar_service import get_active_calendar
    from app.services.term_course_offering_service import get_offering_by_code

    code = str(course_code or "").strip()
    if not code:
        raise LookupError("course_code required")
    extra = StateMachineEngine._as_mapping(student.extra_data)
    lms = StateMachineEngine._as_mapping(extra.get("lms"))
    enrolled = _course_codes_from_enrolled(lms)
    portal = StateMachineEngine._as_mapping(lms.get("portal_course_links"))
    links = StateMachineEngine._as_mapping(lms.get("course_links"))
    meta = StateMachineEngine._as_mapping(lms.get("course_link_meta"))
    if code not in enrolled and code not in portal and code not in links and code not in meta:
        raise LookupError("not enrolled")

    cal = await get_active_calendar(db)
    term_code = cal.term_code if cal else None
    offering = await get_offering_by_code(db, code, term_code=term_code)
    meeting = ""
    if offering and getattr(offering, "online_meeting_url", None):
        meeting = str(offering.online_meeting_url or "").strip()
    if not _is_external_meeting_url(meeting):
        row_meta = meta.get(code) if isinstance(meta.get(code), dict) else {}
        meeting = str(row_meta.get("online_meeting_url") or "").strip()
    if not _is_external_meeting_url(meeting):
        for candidate in (portal.get(code), links.get(code)):
            if _is_external_meeting_url(candidate):
                meeting = str(candidate).strip()
                break
    if not _is_external_meeting_url(meeting):
        raise LookupError("meeting url missing")
    return meeting


async def update_offering_meeting_link(
    db: AsyncSession,
    user: User,
    course_code: str,
    *,
    online_meeting_url: Optional[str] = None,
    host_meeting_url: Optional[str] = None,
) -> dict[str, Any]:
    from sqlalchemy import select

    from app.services.institute_calendar_service import get_active_calendar
    from app.services.term_course_offering_service import get_offering_by_code

    code = str(course_code or "").strip()
    if not code:
        raise ValueError("course_code required")
    if not user_may_access_course(user, code):
        raise PermissionError("course not assigned")

    cal = await get_active_calendar(db)
    term_code = cal.term_code if cal else None
    offering = await get_offering_by_code(db, code, term_code=term_code)
    if not offering:
        raise LookupError("offering not found")

    if online_meeting_url is not None:
        url = str(online_meeting_url or "").strip() or None
        if url and not _is_external_meeting_url(url):
            raise ValueError("online_meeting_url must be http(s)")
        offering.online_meeting_url = url
    if host_meeting_url is not None:
        hurl = str(host_meeting_url or "").strip() or None
        if hurl and not _is_external_meeting_url(hurl):
            raise ValueError("host_meeting_url must be http(s)")
        offering.host_meeting_url = hurl

    student_url = offering.online_meeting_url
    students = (await db.execute(select(Student))).scalars().all()
    for st in students:
        extra = _as_mapping(st.extra_data)
        lms = _as_mapping(extra.get("lms"))
        enrolled = _course_codes_from_enrolled(lms)
        if code not in enrolled:
            continue
        links = dict(lms.get("course_links") or {})
        portal = dict(lms.get("portal_course_links") or {})
        meta = dict(lms.get("course_link_meta") or {})
        if student_url:
            links[code] = student_url
            portal[code] = student_url
        row = dict(meta.get(code) or {})
        row["online_meeting_url"] = student_url
        row["url"] = student_url or row.get("url")
        meta[code] = row
        lms["course_links"] = links
        lms["portal_course_links"] = portal
        lms["course_link_meta"] = meta
        extra["lms"] = lms
        st.extra_data = extra
        flag_modified(st, "extra_data")

    await db.flush()
    return {
        "course_code": code,
        "online_meeting_url": offering.online_meeting_url,
        "host_meeting_url": offering.host_meeting_url,
    }


async def enrich_semester_courses_for_user(
    db: AsyncSession,
    user: User,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from app.services.course_session_calendar_service import (
        build_course_sessions_for_offering,
    )
    from app.services.institute_calendar_service import get_active_calendar
    from app.services.term_course_offering_service import get_offering_by_code
    from datetime import timedelta

    cal = await get_active_calendar(db)
    term_code = cal.term_code if cal else None
    term_start = cal.term_start_date if cal else None
    term_end = (
        cal.term_end_date
        if cal and cal.term_end_date
        else (term_start + timedelta(days=16 * 7) if term_start else None)
    )

    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        code = str(
            row.get("course_code") or row.get("code") or row.get("course_name") or ""
        ).strip()
        if not code:
            out.append(row)
            continue
        offering = await get_offering_by_code(db, code, term_code=term_code)
        roster = await get_course_roster(db, code) if user_may_access_course(user, code) else []
        student_roster = [r for r in roster if r.get("role") != "teaching_assistant"]
        sessions: list[dict[str, Any]] = []
        if offering and term_start and term_end:
            sessions = build_course_sessions_for_offering(
                offering, term_start=term_start, term_end=term_end
            )
        row.update({
            "course_code": code,
            "course_name": row.get("course_name") or (offering.course_name_fa if offering else code),
            "day": row.get("day") or (offering.day if offering else None),
            "time": row.get("time") or row.get("time_text") or (offering.time_text if offering else None),
            "time_text": row.get("time_text") or (offering.time_text if offering else None),
            "classroom_location": (
                row.get("classroom_location")
                or (offering.classroom_location if offering else None)
            ),
            "online_meeting_url": getattr(offering, "online_meeting_url", None) if offering else None,
            "host_meeting_url": getattr(offering, "host_meeting_url", None) if offering else None,
            "roster_count": len(student_roster),
            "scheduled_sessions": [
                {
                    "session_number": s.get("session_number"),
                    "session_date": s.get("session_date"),
                    "session_time": s.get("session_time"),
                }
                for s in sessions
            ],
        })
        out.append(row)
    return out
