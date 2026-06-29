"""Business logic for process 47 — upgrade_to_ta."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student
from app.services.attendance_service import AttendanceService

TA_THERAPY_HOURS_TARGET = 50.0
GPA_MIN_B = 14.0


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _float_from(extra: dict, lms: dict, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        v = extra.get(k)
        if v is None:
            v = lms.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return default


def _bool_flag(extra: dict, lms: dict, *keys: str) -> bool:
    for k in keys:
        v = extra.get(k)
        if v is None:
            v = lms.get(k)
        if v is True:
            return True
    return False


def _build_conditions_preview(
    term2_met: bool,
    gpa_met: bool,
    therapy_met: bool,
    intern_met: bool,
    *,
    cumulative_gpa: float,
    therapy_hours: float,
) -> list[dict[str, Any]]:
    return [
        {
            "key": "term2_courses",
            "label_fa": "پاس شدن دروس ترم دوم دوره جامع",
            "met": term2_met,
        },
        {
            "key": "gpa_b",
            "label_fa": f"معدل حداقل B (فعلی: {cumulative_gpa:g})",
            "met": gpa_met,
        },
        {
            "key": "therapy_50h",
            "label_fa": f"حداقل ۵۰ ساعت درمان آموزشی (فعلی: {therapy_hours:g})",
            "met": therapy_met,
        },
        {
            "key": "internship_started",
            "label_fa": "شروع دوره انترنی",
            "met": intern_met,
        },
    ]


async def build_ta_upgrade_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Populate instance context fields for rules and UI."""
    stmt = select(Student).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        return {}

    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))

    cumulative_gpa = _float_from(extra, lms, "cumulative_gpa", "cumulativeGPA", "gpa")
    analytic_rank = str(extra.get("analytic_rank") or extra.get("gpa_rank") or "").upper()

    attendance = AttendanceService(db)
    therapy_metrics = await attendance.get_therapy_completion_metrics(student_id)
    therapy_hours = _safe_float(therapy_metrics.get("therapy_hours_2x"))

    term2_met = (
        _bool_flag(
            extra,
            lms,
            "comprehensive_term2_courses_passed",
            "comprehensive_term2_passed",
            "ta_eligibility_term2_ok",
        )
        or extra.get("comprehensive_term2_completed") is True
    )
    gpa_met = (
        cumulative_gpa >= GPA_MIN_B
        or analytic_rank in ("B", "B+", "A", "A+")
        or extra.get("ta_eligibility_gpa_ok") is True
    )
    therapy_met = therapy_hours >= TA_THERAPY_HOURS_TARGET or extra.get("ta_eligibility_therapy_ok") is True
    intern_met = (
        bool(student.is_intern)
        or _bool_flag(extra, lms, "internship_started", "ta_eligibility_intern_ok")
    )

    eligibility_met = term2_met and gpa_met and therapy_met and intern_met
    preview = _build_conditions_preview(
        term2_met,
        gpa_met,
        therapy_met,
        intern_met,
        cumulative_gpa=cumulative_gpa,
        therapy_hours=therapy_hours,
    )
    summary_fa = "؛ ".join(
        f"{row['label_fa'].split('(')[0].strip()}: {'✓' if row['met'] else '✗'}"
        for row in preview
    )

    ctx = {
        "ta_eligibility_met": eligibility_met,
        "ta_eligibility_summary_fa": summary_fa,
        "ta_conditions_preview": preview,
        "ta_cumulative_gpa": cumulative_gpa,
        "ta_therapy_hours_completed": therapy_hours,
        "ta_therapy_hours_target": TA_THERAPY_HOURS_TARGET,
        "ta_term2_courses_met": term2_met,
        "ta_gpa_met": gpa_met,
        "ta_therapy_met": therapy_met,
        "ta_intern_met": intern_met,
    }

    merged = {**_as_mapping(existing), **ctx}
    return merged


def validate_conditions_met_trigger(ctx: dict[str, Any]) -> Optional[str]:
    """Return Persian error if student cannot fire conditions_met."""
    if ctx.get("ta_eligibility_met") is True:
        return None
    return (
        "شرایط ارتقا به کمک‌مدرس احراز نشده است. "
        "چهار شرط (دروس ترم دوم جامع، معدل B، ۵۰ ساعت درمان، شروع انترنی) را در پنل بررسی کنید."
    )
