"""Build term-end transcript rows and GPA snapshot from LMS for processes 32/36."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance, Student, User


def _common():
    """Lazy import to avoid circular load via workflow package __init__."""
    from app.services.workflow import _common as C
    return C

_TERM_END_PROCESS_CODES = frozenset(
    {"introductory_term_end", "comprehensive_term_end"},
)


def _course_name(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return "—"
    return (
        entry.get("course_name")
        or entry.get("name_fa")
        or entry.get("title_fa")
        or entry.get("code")
        or entry.get("course_code")
        or "—"
    )


def _is_failed(entry: dict) -> bool:
    if entry.get("incomplete") or entry.get("status") == "I":
        return True
    pf = (entry.get("pass_fail_status") or entry.get("pass_fail") or "").strip()
    if pf in ("مردود", "Fail", "FAIL", "fail", "F"):
        return True
    letter = (entry.get("letter_grade") or entry.get("grade") or "").strip().upper()
    if letter in ("F", "I", "مردود"):
        return True
    if entry.get("passed") is False or entry.get("pass") is False:
        return True
    return False


def _numeric_grade(entry: dict) -> Optional[float]:
    for key in ("numeric_grade", "grade_numeric", "final_grade", "numeric"):
        val = entry.get(key)
        if val is None or val == "":
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    grade = entry.get("grade") or entry.get("letter_grade")
    if grade is not None and str(grade).replace(".", "", 1).isdigit():
        try:
            return float(grade)
        except (TypeError, ValueError):
            pass
    return None


def _pass_fail_label(entry: dict) -> str:
    if _is_failed(entry):
        return "مردود"
    return "قبول"


def _units_for_row(entry: dict, failed: bool) -> int:
    raw = entry.get("units") or entry.get("credit_hours") or entry.get("credits") or 1
    try:
        units = int(raw)
    except (TypeError, ValueError):
        units = 1
    if failed:
        return 0
    return max(units, 0)


def _normalize_enrolled_courses(extra: dict) -> list[dict]:
    lms = extra.get("lms") or {}
    if not isinstance(lms, dict):
        return []
    rows: list[dict] = []
    enrolled = lms.get("enrolled_courses") or []
    if isinstance(enrolled, list):
        for item in enrolled:
            if isinstance(item, dict):
                rows.append(dict(item))
            elif isinstance(item, str):
                rows.append({"code": item, "course_code": item, "course_name": item})
    links = lms.get("course_links") or []
    if isinstance(links, list):
        for item in links:
            if isinstance(item, dict):
                rows.append(dict(item))
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        key = str(row.get("code") or row.get("course_code") or _course_name(row))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _compute_term_gpa(rows: list[dict]) -> Optional[float]:
    total_points = 0.0
    total_units = 0
    for row in rows:
        units = row.get("units") or 0
        if units <= 0:
            continue
        num = row.get("numeric_grade")
        if num is None:
            continue
        try:
            n = float(num)
        except (TypeError, ValueError):
            continue
        total_points += n * units
        total_units += units
    if total_units <= 0:
        return None
    return round(total_points / total_units, 2)


def _remaining_comprehensive_courses(courses: list[dict]) -> list[str]:
    remaining: list[str] = []
    for entry in courses:
        if _is_failed(entry) or entry.get("completed") is False:
            remaining.append(_course_name(entry))
        elif not entry.get("grades_locked") and entry.get("grade") in (None, ""):
            if entry.get("numeric_grade") is None:
                remaining.append(_course_name(entry))
    return remaining


def _format_transcript_body(
    *,
    doc_type: str,
    student: Student,
    rows: list[dict],
    term_gpa: Optional[float],
    cumulative_gpa: Optional[float],
) -> str:
    code = getattr(student, "student_code", "—")
    term = getattr(student, "current_term", "—")
    lines = [
        f"{'کارنامه ترم' if doc_type == 'term_transcript' else 'کارنامه کل'} — دانشجو {code} — ترم {term}",
        "",
    ]
    for row in rows:
        lines.append(
            f"• {_course_name(row)} | واحد: {row.get('units', 0)} | "
            f"نمره: {row.get('numeric_grade', '—')} ({row.get('letter_grade', '—')}) | "
            f"{row.get('pass_fail_status', '—')}"
        )
    if term_gpa is not None:
        lines.append("")
        lines.append(f"معدل ترم: {term_gpa}")
    if cumulative_gpa is not None and doc_type == "cumulative_transcript":
        lines.append(f"معدل کل: {cumulative_gpa}")
    return "\n".join(lines)


async def build_decline_followup_row(
    db: AsyncSession,
    student: Student,
    failed_courses: list[str],
) -> dict[str, Any]:
    user: Optional[User] = None
    if student.user_id:
        user = await _common().get_user(db, student.user_id)
    name = ""
    if user:
        name = (user.full_name_fa or user.username or "").strip()
    if not name:
        name = str(getattr(student, "student_code", "—"))
    phone = ""
    if user:
        phone = (user.phone or user.mobile or "").strip()
    return {
        "student_name": name,
        "student_phone": phone,
        "failed_courses": ", ".join(failed_courses) if failed_courses else "—",
        "followup_done": False,
    }


async def _enrich_transcript_rows_from_offerings(
    db: AsyncSession,
    rows: list[dict],
    *,
    term_code: Optional[str] = None,
) -> list[dict]:
    from app.services.institute_calendar_service import get_active_calendar
    from app.services.term_course_offering_service import get_offering_by_code

    if not term_code:
        cal = await get_active_calendar(db)
        term_code = cal.term_code if cal else None
    if not term_code:
        return rows
    out: list[dict] = []
    for row in rows:
        enriched = dict(row)
        code = enriched.get("course_code") or enriched.get("code")
        if code:
            off = await get_offering_by_code(db, str(code), term_code=term_code)
            if off:
                enriched["course_name"] = off.course_name_fa
                enriched["units"] = off.units
            elif enriched.get("course_name") in (None, "—", code):
                enriched["course_name"] = f"{code} (نامشخص)"
                enriched.setdefault("course_name_note_fa", "این درس در فهرست منتشرشدهٔ ترم یافت نشد.")
        out.append(enriched)
    return out


def build_term_end_snapshot(
    student: Student,
    instance: ProcessInstance,
    *,
    db: Optional[AsyncSession] = None,
    enriched_rows: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Return snapshot fields to merge into process instance context."""
    extra = _common().student_extra(student)
    courses = _normalize_enrolled_courses(extra)
    rows: list[dict] = []
    failed_names: list[str] = []

    if enriched_rows is not None:
        rows = list(enriched_rows)
        for row in rows:
            if row.get("pass_fail_status") == "مردود" or _is_failed(row):
                failed_names.append(row.get("course_name") or "—")
    else:
        for entry in courses:
            failed = _is_failed(entry)
            num = _numeric_grade(entry)
            letter = entry.get("letter_grade") or entry.get("grade") or ("F" if failed else "—")
            row = {
                "course_name": _course_name(entry),
                "course_code": entry.get("code") or entry.get("course_code"),
                "units": _units_for_row(entry, failed),
                "numeric_grade": num,
                "letter_grade": str(letter) if letter is not None else "—",
                "pass_fail_status": _pass_fail_label(entry),
            }
            rows.append(row)
            if failed:
                failed_names.append(_course_name(entry))

    term_gpa = _compute_term_gpa(rows)
    cumulative_gpa = term_gpa
    prev = _common().as_mapping(instance.context_data).get("cumulative_gpa")
    if prev is not None:
        try:
            cumulative_gpa = round((float(prev) + (term_gpa or 0)) / 2, 2)
        except (TypeError, ValueError):
            cumulative_gpa = term_gpa

    term_code = getattr(student, "current_term", None)
    snapshot: dict[str, Any] = {
        "term_code": term_code,
        "term_label_fa": f"ترم {term_code}" if term_code else None,
        "term_transcript_rows": rows,
        "term_gpa": term_gpa,
        "cumulative_gpa": cumulative_gpa,
        "failed_courses": failed_names,
    }

    if instance.process_code == "comprehensive_term_end":
        remaining = _remaining_comprehensive_courses(courses)
        snapshot["remaining_comprehensive_courses"] = remaining
        snapshot["remaining_courses"] = remaining
        snapshot["all_comprehensive_courses_passed"] = len(remaining) == 0 and len(failed_names) == 0

    return snapshot


async def apply_term_end_snapshot(
    db: AsyncSession,
    instance: ProcessInstance,
    student: Student,
) -> dict[str, Any]:
    """Merge snapshot into instance context; build decline followup row when needed."""
    if instance.process_code not in _TERM_END_PROCESS_CODES:
        return {}

    C = _common()
    ctx = C.instance_ctx(instance)
    if ctx.get("term_transcript_rows"):
        return ctx

    extra = _common().student_extra(student)
    courses = _normalize_enrolled_courses(extra)
    base_rows: list[dict] = []
    for entry in courses:
        failed = _is_failed(entry)
        num = _numeric_grade(entry)
        letter = entry.get("letter_grade") or entry.get("grade") or ("F" if failed else "—")
        base_rows.append(
            {
                "course_name": _course_name(entry),
                "course_code": entry.get("code") or entry.get("course_code"),
                "units": _units_for_row(entry, failed),
                "numeric_grade": num,
                "letter_grade": str(letter) if letter is not None else "—",
                "pass_fail_status": _pass_fail_label(entry),
            }
        )
    enriched = await _enrich_transcript_rows_from_offerings(db, base_rows)
    snapshot = build_term_end_snapshot(
        student, instance, db=db, enriched_rows=enriched
    )
    if instance.process_code == "introductory_term_end":
        failed = snapshot.get("failed_courses") or []
        if failed:
            row = await build_decline_followup_row(db, student, failed)
            snapshot["decline_followup_rows"] = [row]
        else:
            snapshot["decline_followup_rows"] = []

    ctx.update(snapshot)
    C.commit_instance_ctx(instance, ctx)
    return snapshot


def rich_document_body(
    doc_type: str,
    student: Student,
    ctx: dict,
) -> str:
    rows = ctx.get("term_transcript_rows") or []
    if not rows:
        return _format_transcript_body(
            doc_type=doc_type,
            student=student,
            rows=[],
            term_gpa=ctx.get("term_gpa"),
            cumulative_gpa=ctx.get("cumulative_gpa"),
        )
    return _format_transcript_body(
        doc_type=doc_type,
        student=student,
        rows=rows,
        term_gpa=ctx.get("term_gpa"),
        cumulative_gpa=ctx.get("cumulative_gpa"),
    )
