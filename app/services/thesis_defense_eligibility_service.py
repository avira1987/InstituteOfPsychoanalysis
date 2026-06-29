"""محاسبه شروط چهارگانه دفاع پایان‌نامه (فرایند ۷۰)."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student
from app.services.attendance_service import AttendanceService

UNITS_REQUIRED = 67.0
GPA_MIN_B = 14.0
THERAPY_THRESHOLD = 250.0
CLINICAL_THRESHOLD = 750.0
SUPERVISION_THRESHOLD = 150.0


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


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


async def build_thesis_defense_eligibility_context(
    db: AsyncSession,
    student_id: uuid.UUID,
) -> dict[str, Any]:
    """مقادیر ساعات/واحد و پرچم‌های احراز برای UI و قوانین."""
    stmt = select(Student).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalars().first()
    extra = _as_mapping(student.extra_data) if student else {}
    lms = _as_mapping(extra.get("lms"))

    total_units = _float_from(extra, lms, "total_units", "completed_units", "units_completed")
    cumulative_gpa = _float_from(extra, lms, "cumulative_gpa", "cumulativeGPA", "gpa")

    attendance = AttendanceService(db)
    m = await attendance.get_therapy_completion_metrics(student_id)
    therapy_hours = float(m["therapy_hours_2x"])
    clinical_hours = float(m["clinical_hours"])
    supervision_hours = float(m["supervision_hours"])

    units_67_b_met = total_units >= UNITS_REQUIRED and cumulative_gpa >= GPA_MIN_B
    clinical_750_met = clinical_hours >= CLINICAL_THRESHOLD
    supervision_150_met = supervision_hours >= SUPERVISION_THRESHOLD
    therapy_250_met = therapy_hours >= THERAPY_THRESHOLD
    all_conditions_met = (
        units_67_b_met and clinical_750_met and supervision_150_met and therapy_250_met
    )

    preview_fa = (
        f"وضعیت شروط دفاع: واحد {total_units:g}/{UNITS_REQUIRED:g} (معدل {cumulative_gpa:g})؛ "
        f"درمان {therapy_hours:g}/{THERAPY_THRESHOLD:g}؛ "
        f"بالینی {clinical_hours:g}/{CLINICAL_THRESHOLD:g}؛ "
        f"سوپرویژن {supervision_hours:g}/{SUPERVISION_THRESHOLD:g}."
    )

    return {
        "total_units": total_units,
        "cumulative_gpa": cumulative_gpa,
        "units_required": UNITS_REQUIRED,
        "gpa_min_b": GPA_MIN_B,
        "therapy_hours": therapy_hours,
        "clinical_hours": clinical_hours,
        "supervision_hours": supervision_hours,
        "therapy_threshold": THERAPY_THRESHOLD,
        "clinical_threshold": CLINICAL_THRESHOLD,
        "supervision_threshold": SUPERVISION_THRESHOLD,
        "units_67_b_met": units_67_b_met,
        "clinical_750_met": clinical_750_met,
        "supervision_150_met": supervision_150_met,
        "therapy_250_met": therapy_250_met,
        "all_conditions_met": all_conditions_met,
        "thesis_defense_eligibility_preview_fa": preview_fa,
    }


def eligibility_readonly_labels(fields: dict[str, Any]) -> dict[str, str]:
    """برچسب فارسی برای فیلدهای readonly فرم غربالگری."""
    tu = fields.get("total_units", 0)
    gpa = fields.get("cumulative_gpa", 0)
    th = fields.get("therapy_hours", 0)
    ch = fields.get("clinical_hours", 0)
    sh = fields.get("supervision_hours", 0)

    def _lbl(met: bool, ok: str, fail: str) -> str:
        return ok if met else fail

    return {
        "check_67_units_b": _lbl(
            fields.get("units_67_b_met"),
            f"✓ {tu:g} واحد — معدل {gpa:g}",
            f"✗ {tu:g} واحد — معدل {gpa:g} (نیاز: ۶۷ واحد و معدل B)",
        ),
        "check_750_clinical": _lbl(
            fields.get("clinical_750_met"),
            f"✓ {ch:g} ساعت",
            f"✗ {ch:g} از ۷۵۰ ساعت",
        ),
        "check_150_supervision": _lbl(
            fields.get("supervision_150_met"),
            f"✓ {sh:g} ساعت",
            f"✗ {sh:g} از ۱۵۰ ساعت",
        ),
        "check_250_therapy": _lbl(
            fields.get("therapy_250_met"),
            f"✓ {th:g} ساعت",
            f"✗ {th:g} از ۲۵۰ ساعت",
        ),
    }
