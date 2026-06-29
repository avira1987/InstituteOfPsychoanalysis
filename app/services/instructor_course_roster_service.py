"""تجمیع لیست دانشجویان ثبت‌نام‌شده در یک درس — برای پنل مدرس."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, User


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def assigned_course_codes_for_user(user: User) -> set[str]:
    """کدهای درس انتساب‌یافته به مدرس/کمک‌مدرس از profile_meta."""
    meta = _as_mapping(user.profile_meta)
    items = meta.get("semester_course_assignments") or []
    codes: set[str] = set()
    if not isinstance(items, list):
        return codes
    role = (user.role or "").strip()
    kind = "instructor" if role == "instructor" else "teaching_assistant" if role == "teaching_assistant" else None
    for row in items:
        if not isinstance(row, dict):
            continue
        if kind and row.get("role_kind") not in (None, kind):
            continue
        code = (
            row.get("course_code")
            or row.get("code")
            or row.get("course_name")
            or ""
        )
        code = str(code).strip()
        if code:
            codes.add(code)
    return codes


def user_may_access_course(user: User, course_code: str) -> bool:
    role = (user.role or "").strip()
    if role in ("admin", "staff"):
        return True
    if role not in ("instructor", "teaching_assistant"):
        return False
    return course_code in assigned_course_codes_for_user(user)


def _absence_count_for_student(entry: dict[str, Any], student_id: str) -> int:
    """غیبت per-course از entry یا students nested."""
    if entry.get("absence_count") is not None:
        try:
            return int(entry["absence_count"])
        except (TypeError, ValueError):
            pass
    for row in entry.get("students") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("student_id") or "") == student_id:
            try:
                return int(row.get("absence_count") or 0)
            except (TypeError, ValueError):
                return 0
    return 0


async def get_course_roster(
    db: AsyncSession,
    course_code: str,
) -> list[dict[str, Any]]:
    """لیست یکتأ دانشجویان ثبت‌نام‌شده در درس از lms.lesson_attendance همهٔ پرونده‌ها."""
    code = str(course_code or "").strip()
    if not code:
        return []

    result = await db.execute(select(Student))
    students = result.scalars().all()
    seen: set[str] = set()
    roster: list[dict[str, Any]] = []
    ta_names: set[str] = set()

    for student in students:
        extra = _as_mapping(student.extra_data)
        lms = _as_mapping(extra.get("lms"))
        lesson_att = _as_mapping(lms.get("lesson_attendance"))
        entry = lesson_att.get(code) or lesson_att.get(str(code))
        ta_map = _as_mapping(lms.get("teaching_assistants_by_course"))
        ta_name = ta_map.get(code) or ta_map.get(str(code))
        if ta_name and str(ta_name).strip() not in ("", "—"):
            ta_names.add(str(ta_name).strip())

        if not isinstance(entry, dict):
            enrolled = lms.get("enrolled_courses") or []
            if code not in [str(c) for c in enrolled]:
                continue
            sid = str(student.id)
            if sid in seen:
                continue
            seen.add(sid)
            roster.append({
                "student_id": sid,
                "student_code": student.student_code or sid,
                "name_fa": student.student_code or sid,
                "role": "student",
                "status": "present",
                "absence_count": 0,
            })
            continue

        rows = entry.get("students") or []
        if isinstance(rows, list) and rows:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                sid = str(row.get("student_id") or student.id)
                if sid in seen:
                    continue
                seen.add(sid)
                roster.append({
                    "student_id": sid,
                    "student_code": row.get("student_code") or student.student_code or sid,
                    "name_fa": row.get("name_fa") or row.get("student_name") or student.student_code or sid,
                    "role": row.get("role") or "student",
                    "status": row.get("status") or "present",
                    "absence_count": _absence_count_for_student(entry, sid),
                })
        else:
            sid = str(student.id)
            if sid in seen:
                continue
            seen.add(sid)
            roster.append({
                "student_id": sid,
                "student_code": student.student_code or sid,
                "name_fa": entry.get("name_fa") or student.student_code or sid,
                "role": "student",
                "status": "present",
                "absence_count": _absence_count_for_student(entry, sid),
            })

    for ta_name in sorted(ta_names):
        ta_key = f"ta:{ta_name}"
        if ta_key in seen:
            continue
        seen.add(ta_key)
        roster.append({
            "student_id": ta_key,
            "student_code": ta_name,
            "name_fa": ta_name,
            "role": "teaching_assistant",
            "status": "present",
            "absence_count": 0,
        })

    roster.sort(key=lambda r: (0 if r.get("role") == "student" else 1, r.get("student_code") or ""))
    return roster


def roster_to_grades_rows(roster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """نگاشت roster به ردیف‌های students_grades."""
    rows: list[dict[str, Any]] = []
    for entry in roster:
        rows.append({
            "student_id": entry.get("student_id"),
            "student_name": entry.get("name_fa") or entry.get("student_code"),
            "grade": "",
        })
    return rows


async def get_course_roster_for_user(
    db: AsyncSession,
    user: User,
    course_code: str,
    *,
    include_final_reports: bool = False,
) -> list[dict[str, Any]]:
    if not user_may_access_course(user, course_code):
        return []
    roster = await get_course_roster(db, course_code)
    if include_final_reports and roster:
        from app.services.film_observation_course_service import (
            collect_student_final_reports,
            enrich_roster_with_final_reports,
        )

        reports = await collect_student_final_reports(db, course_code)
        enrich_roster_with_final_reports(roster, reports)
    return roster


def roster_to_completion_tick_rows(roster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """نگاشت roster به ردیف‌های داشبورد تیک تکمیل."""
    rows: list[dict[str, Any]] = []
    for entry in roster:
        rows.append({
            "student_id": entry.get("student_id"),
            "student_name": entry.get("name_fa") or entry.get("student_code"),
            "completed": False,
        })
    return rows


def roster_to_attendance_rows(roster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """نگاشت roster به payload ثبت حضور."""
    rows: list[dict[str, Any]] = []
    for entry in roster:
        rows.append({
            "student_id": entry.get("student_id"),
            "student_name": entry.get("name_fa") or entry.get("student_code"),
            "person_name": entry.get("name_fa") or entry.get("student_code"),
            "role": entry.get("role") or "student",
            "status": entry.get("status") or "present",
        })
    return rows
