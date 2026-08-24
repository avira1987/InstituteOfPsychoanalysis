"""تولید تقویم جلسات کلاس از روز هفتهٔ offering و بازهٔ تقویم آموزشی."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import Student, TermCourseOffering

# Python weekday(): Monday=0 … Sunday=6
# تقویم ایران: شنبه=Saturday=5
_FA_WEEKDAY = {
    "شنبه": 5,
    "يكشنبه": 6,
    "یکشنبه": 6,
    "دوشنبه": 0,
    "سه‌شنبه": 1,
    "سه شنبه": 1,
    "سهشنبه": 1,
    "چهارشنبه": 2,
    "چهار شنبه": 2,
    "پنجشنبه": 3,
    "پنج‌شنبه": 3,
    "پنج شنبه": 3,
    "جمعه": 4,
}


def parse_fa_weekday(day: Any) -> Optional[int]:
    """برگرداندن weekday پایتون (Mon=0) از نام روز فارسی؛ در غیر این صورت None."""
    if day is None:
        return None
    raw = str(day).strip()
    if not raw:
        return None
    # normalize Arabic yeh/kaf variants
    raw = raw.replace("ي", "ی").replace("ك", "ک").replace("‌", "").replace(" ", "")
    for key, val in _FA_WEEKDAY.items():
        nk = key.replace("‌", "").replace(" ", "").replace("ي", "ی")
        if raw == nk or raw.startswith(nk):
            return val
    return None


def parse_time_text(time_text: Any) -> tuple[int, int]:
    """ساعت شروع از time_text مثل '۱۰:۰۰' یا '10:00-12:00' → (hour, minute)."""
    if time_text is None:
        return (10, 0)
    s = str(time_text).strip()
    if not s:
        return (10, 0)
    # Persian digits → Latin
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    s = s.translate(trans)
    m = re.search(r"(\d{1,2})\s*[:：]\s*(\d{1,2})", s)
    if m:
        h = max(0, min(23, int(m.group(1))))
        mi = max(0, min(59, int(m.group(2))))
        return (h, mi)
    m2 = re.search(r"(\d{1,2})", s)
    if m2:
        return (max(0, min(23, int(m2.group(1)))), 0)
    return (10, 0)


def iter_session_dates(
    *,
    weekday: int,
    term_start: date,
    term_end: date,
) -> list[date]:
    """همهٔ تاریخ‌های آن weekday بین start و end (شامل دو سر)."""
    if term_end < term_start:
        return []
    # advance to first matching weekday
    delta = (weekday - term_start.weekday()) % 7
    cur = term_start + timedelta(days=delta)
    out: list[date] = []
    while cur <= term_end:
        out.append(cur)
        cur += timedelta(days=7)
    return out


def build_course_sessions_for_offering(
    offering: TermCourseOffering,
    *,
    term_start: date,
    term_end: date,
) -> list[dict[str, Any]]:
    """لیست course_sessions برای یک offering."""
    weekday = parse_fa_weekday(offering.day)
    if weekday is None:
        return []
    hour, minute = parse_time_text(offering.time_text)
    time_str = f"{hour:02d}:{minute:02d}"
    code = str(offering.course_code or "").strip()
    sessions: list[dict[str, Any]] = []
    for i, d in enumerate(iter_session_dates(weekday=weekday, term_start=term_start, term_end=term_end), start=1):
        sessions.append({
            "course_id": code,
            "course_code": code,
            "session_index": i,
            "session_number": i,
            "session_date": d.isoformat(),
            "date": d.isoformat(),
            "session_time": time_str,
            "time_text": offering.time_text,
            "day": offering.day,
            "status": "scheduled",
        })
    return sessions


def merge_course_sessions(
    existing: list[Any],
    new_sessions: list[dict[str, Any]],
    *,
    course_code: str,
) -> list[dict[str, Any]]:
    """جلسات سایر دروس را نگه می‌دارد؛ جلسات این درس را با new_sessions جایگزین می‌کند
    مگر آنکه قبلاً لغو/جبرانی شده باشند."""
    code = str(course_code or "").strip()
    kept: list[dict[str, Any]] = []
    preserved_by_date: dict[str, dict[str, Any]] = {}
    for row in existing if isinstance(existing, list) else []:
        if not isinstance(row, dict):
            continue
        row_code = str(row.get("course_id") or row.get("course_code") or "").strip()
        if row_code != code:
            kept.append(row)
            continue
        status = str(row.get("status") or "").lower()
        if status in ("cancelled", "makeup", "rescheduled") or row.get("cancelled") is True:
            d = str(row.get("session_date") or row.get("date") or "")
            if d:
                preserved_by_date[d] = row
            else:
                kept.append(row)
    for sess in new_sessions:
        d = str(sess.get("session_date") or sess.get("date") or "")
        if d and d in preserved_by_date:
            kept.append(preserved_by_date.pop(d))
        else:
            kept.append(sess)
    kept.extend(preserved_by_date.values())
    kept.sort(key=lambda r: str(r.get("session_date") or r.get("date") or ""))
    return kept


def _course_codes(raw: Any) -> list[str]:
    out: list[str] = []
    for c in raw if isinstance(raw, (list, tuple)) else []:
        if isinstance(c, dict):
            code = str(c.get("code") or c.get("course_code") or "").strip()
        else:
            code = str(c or "").strip()
        if code and code not in out:
            out.append(code)
    return out


async def seed_course_sessions_for_student(
    db: AsyncSession,
    student: Student,
    *,
    course_codes: Optional[list[str]] = None,
    term_code: Optional[str] = None,
) -> int:
    """برای دروس ثبت‌نام‌شده، lms.course_sessions را از offering + تقویم فعال می‌سازد."""
    from app.services.institute_calendar_service import get_active_calendar
    from app.services.term_course_offering_service import get_offering_by_code

    cal = await get_active_calendar(db)
    if not cal or not cal.term_start_date:
        return 0
    term_start = cal.term_start_date
    term_end = cal.term_end_date or (term_start + timedelta(days=16 * 7))
    tc = term_code or cal.term_code

    extra = dict(student.extra_data or {})
    lms = dict(extra.get("lms") or {})
    codes = course_codes or _course_codes(lms.get("enrolled_courses"))
    if not codes:
        return 0

    existing = list(lms.get("course_sessions") or [])
    added = 0
    for code in codes:
        offering = await get_offering_by_code(db, code, term_code=tc)
        if not offering:
            continue
        built = build_course_sessions_for_offering(
            offering, term_start=term_start, term_end=term_end
        )
        if not built:
            continue
        existing = merge_course_sessions(existing, built, course_code=code)
        added += len(built)
    lms["course_sessions"] = existing
    lms["course_sessions_seeded_at"] = datetime.now(timezone.utc).isoformat()
    extra["lms"] = lms
    student.extra_data = extra
    flag_modified(student, "extra_data")
    return added


def session_attendance_already_recorded(
    lms: dict[str, Any],
    course_code: str,
    session_date: str,
) -> bool:
    """آیا برای این درس+تاریخ در lesson_attendance قبلاً حضور ثبت شده؟"""
    code = str(course_code or "").strip()
    target = str(session_date or "").strip()[:10]
    if not code or not target:
        return False
    lesson_att = lms.get("lesson_attendance") or {}
    if not isinstance(lesson_att, dict):
        return False
    entry = lesson_att.get(code) or lesson_att.get(str(code)) or {}
    if not isinstance(entry, dict):
        return False
    for sess in entry.get("sessions") or []:
        if not isinstance(sess, dict):
            continue
        d = str(sess.get("date") or sess.get("session_date") or "").strip()[:10]
        if d == target:
            return True
    return False
