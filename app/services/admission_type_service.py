"""نرمال‌سازی و persist نوع پذیرش روی Student.extra_data."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import Student

# canonical values used by intro_second / term_end rules
ADMISSION_CONDITIONAL_THERAPY = "conditional_therapy"
ADMISSION_SINGLE_COURSE = "single_course"
ADMISSION_FULL = "full_admission"

_ALIAS_TO_CANONICAL = {
    "conditional_therapy": ADMISSION_CONDITIONAL_THERAPY,
    "result_conditional_therapy": ADMISSION_CONDITIONAL_THERAPY,
    "single_course": ADMISSION_SINGLE_COURSE,
    "result_single_course": ADMISSION_SINGLE_COURSE,
    "full": ADMISSION_FULL,
    "full_admission": ADMISSION_FULL,
    "result_full_admission": ADMISSION_FULL,
}

_STATE_TO_ADMISSION = {
    "result_conditional_therapy": ADMISSION_CONDITIONAL_THERAPY,
    "result_single_course": ADMISSION_SINGLE_COURSE,
    "result_full_admission": ADMISSION_FULL,
}


def _as_mapping(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def normalize_admission_type(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if not key:
        return None
    return _ALIAS_TO_CANONICAL.get(key) or _ALIAS_TO_CANONICAL.get(str(raw).strip()) or None


def admission_type_from_result_state(state_code: Optional[str]) -> Optional[str]:
    if not state_code:
        return None
    return _STATE_TO_ADMISSION.get(str(state_code).strip())


def resolve_admission_type_from_context(ctx: dict | None) -> Optional[str]:
    ctx = ctx or {}
    for key in ("admission_type", "interview_result", "result"):
        normalized = normalize_admission_type(ctx.get(key))
        if normalized:
            return normalized
    return None


def derive_has_active_therapist(student: Student, extra: dict | None = None) -> bool:
    """هم‌تراز با full_education_leave_service — برای قوانین موتور."""
    ex = extra if extra is not None else _as_mapping(student.extra_data)
    if student.therapist_id is not None:
        return True
    if student.therapy_started:
        return True
    if ex.get("has_active_therapist") is True:
        return True
    rel = ex.get("therapy_relationship")
    if ex.get("therapy_status") == "terminated":
        return False
    if rel in ("released_on_full_leave", "terminated"):
        return False
    return False


def persist_admission_type_on_student(
    student: Student,
    *,
    admission_type: Any = None,
    interview_result: Any = None,
    result_state: Optional[str] = None,
) -> Optional[str]:
    """Write canonical admission_type (+ interview_result) onto student.extra_data."""
    canonical = (
        normalize_admission_type(admission_type)
        or normalize_admission_type(interview_result)
        or admission_type_from_result_state(result_state)
    )
    if not canonical:
        return None

    extra = _as_mapping(student.extra_data)
    extra["admission_type"] = canonical
    ir = normalize_admission_type(interview_result) or canonical
    if ir:
        extra["interview_result"] = ir
    student.extra_data = extra
    flag_modified(student, "extra_data")
    return canonical


def set_has_active_therapist_flag(student: Student, value: bool) -> None:
    extra = _as_mapping(student.extra_data)
    extra["has_active_therapist"] = bool(value)
    student.extra_data = extra
    flag_modified(student, "extra_data")


def conditional_therapy_required(student: Student) -> bool:
    extra = _as_mapping(student.extra_data)
    return normalize_admission_type(extra.get("admission_type")) == ADMISSION_CONDITIONAL_THERAPY


def therapy_deadline_hint_fa(*, deadline: Optional[str] = None) -> str:
    if deadline:
        return (
            "پذیرش شما مشروط به آغاز درمان آموزشی است. "
            f"تا قبل از آغاز ترم دوم (مهلت: {deadline}) باید فرایند «آغاز درمان آموزشی» را تکمیل کنید؛ "
            "در غیر این صورت ثبت‌نام ترم دوم برای شما باز نمی‌شود."
        )
    return (
        "پذیرش شما مشروط به آغاز درمان آموزشی است. "
        "تا قبل از آغاز ترم دوم باید فرایند «آغاز درمان آموزشی» را تکمیل کنید؛ "
        "در غیر این صورت ثبت‌نام ترم دوم برای شما باز نمی‌شود."
    )
