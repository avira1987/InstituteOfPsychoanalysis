"""سرویس فرایند ۵۴ — حضور و غیاب در تمامی کلاس‌ها."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import Student

_ABSENT_STATUSES = frozenset({"absent", "غایب", "absent_unexcused"})


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_absent_status(status: Any) -> bool:
    return str(status or "").lower() in _ABSENT_STATUSES


def infer_course_type(course_code: str, course_type: Optional[str] = None) -> str:
    """نوع درس: standard | article_writing | live_supervision."""
    ct = str(course_type or "").lower().strip()
    if ct in ("live_supervision", "article_writing"):
        return ct
    code = str(course_code or "")
    code_l = code.lower()
    if "live_supervision" in code_l or "سوپرویژن زنده" in code:
        return "live_supervision"
    if "article" in code_l or "مقاله" in code:
        return "article_writing"
    return "standard"


def _course_matches_row(course_row: Any, course_code: str) -> bool:
    if not isinstance(course_row, dict):
        return str(course_row) == course_code
    ccode = str(course_row.get("code") or course_row.get("course_code") or "")
    cname = str(course_row.get("course_name") or course_row.get("name_fa") or "")
    return ccode == course_code or cname == course_code


def _apply_incomplete_to_enrolled(lms: dict[str, Any], course_code: str) -> None:
    enrolled = list(lms.get("enrolled_courses") or [])
    if not enrolled:
        return
    updated: list[Any] = []
    for row in enrolled:
        if _course_matches_row(row, course_code) and isinstance(row, dict):
            updated.append({
                **row,
                "incomplete": True,
                "status": "I",
                "status_fa": "Incomplete / قفل",
                "grades_locked": True,
                "grade_locked": True,
            })
        else:
            updated.append(row)
    lms["enrolled_courses"] = updated


async def apply_session_attendance(
    db: AsyncSession,
    course_code: str,
    session_date: str,
    rows: list[dict[str, Any]],
    *,
    course_type: Optional[str] = None,
    actor_id: Any = None,
    session_number: Optional[int] = None,
) -> dict[str, Any]:
    """
    ثبت حضور/غیاب جلسه برای هر فرد در rows.
    per-course absence_count و sessions در lms.lesson_attendance به‌روز می‌شود.
    """
    code = str(course_code or "").strip()
    ct = infer_course_type(code, course_type)
    now_iso = _utcnow_iso()

    summary: dict[str, Any] = {
        "course_code": code,
        "session_date": session_date,
        "course_type": ct,
        "recorded_at": now_iso,
        "actor_id": str(actor_id) if actor_id else None,
        "updated": 0,
        "present": 0,
        "absent": 0,
        "incomplete_triggered": [],
        "article_violation_triggered": [],
        "per_student": {},
    }

    if not code or not rows:
        return summary

    for row in rows:
        if not isinstance(row, dict):
            continue
        sid_raw = row.get("student_id")
        if not sid_raw:
            continue
        try:
            sid = uuid.UUID(str(sid_raw))
        except (ValueError, TypeError):
            continue

        result = await db.execute(select(Student).where(Student.id == sid))
        student = result.scalar_one_or_none()
        if not student:
            continue

        absent = is_absent_status(row.get("status")) or row.get("absent") is True

        extra = _as_mapping(student.extra_data)
        lms = _as_mapping(extra.get("lms"))
        lesson_att = dict(_as_mapping(lms.get("lesson_attendance")))
        entry = dict(_as_mapping(lesson_att.get(code) or lesson_att.get(str(code))))
        if not entry:
            entry = {
                "course_code": code,
                "students": [],
                "sessions": [],
                "absence_count": 0,
            }

        sessions = list(entry.get("sessions") or [])
        sess_num = session_number if session_number is not None else len(sessions) + 1
        sessions.append({
            "session_number": sess_num,
            "date": session_date,
            "status": "absent" if absent else "present",
            "recorded_at": now_iso,
        })
        entry["sessions"] = sessions

        absence_count = int(entry.get("absence_count") or 0)
        if absent and ct != "live_supervision":
            absence_count += 1
            entry["absence_count"] = absence_count
            extra["class_absence_count"] = int(extra.get("class_absence_count") or 0) + 1
            lms["absence_count"] = extra["class_absence_count"]

        if ct == "standard" and absence_count >= 5:
            _apply_incomplete_to_enrolled(lms, code)
            summary["incomplete_triggered"].append(str(sid))
        elif ct == "article_writing" and absence_count >= 5:
            entry["article_violation_pending"] = True
            summary["article_violation_triggered"].append(str(sid))

        lesson_att[code] = entry
        lms["lesson_attendance"] = lesson_att
        extra["lms"] = lms
        student.extra_data = extra
        flag_modified(student, "extra_data")

        summary["updated"] += 1
        if absent:
            summary["absent"] += 1
        else:
            summary["present"] += 1
        summary["per_student"][str(sid)] = {
            "absence_count": absence_count,
            "status": "absent" if absent else "present",
            "student_absence_count": absence_count,
        }

    return summary
