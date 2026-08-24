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
    "تک درس": ADMISSION_SINGLE_COURSE,
    "تک‌درس": ADMISSION_SINGLE_COURSE,
    "پذیرش تک درس": ADMISSION_SINGLE_COURSE,
    "پذیرش تک‌درس": ADMISSION_SINGLE_COURSE,
    "مشروط به درمان": ADMISSION_CONDITIONAL_THERAPY,
    "پذیرش مشروط": ADMISSION_CONDITIONAL_THERAPY,
    "پذیرش کامل": ADMISSION_FULL,
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
    nested = ctx.get("student")
    if isinstance(nested, dict):
        return resolve_admission_type_from_context(nested)
    return None


def overlay_admission_on_context(
    ctx: dict | None,
    student: Any = None,
    state_codes: Optional[list] = None,
) -> dict:
    """نوع پذیرش کانونی برای فیلتر درس: اگر هر منبع تک‌درس باشد، تک‌درس می‌ماند."""
    out = _as_mapping(ctx)
    extra = _as_mapping(getattr(student, "extra_data", None) if student is not None else None)
    from_student = resolve_admission_type_from_context(extra)
    from_ctx = resolve_admission_type_from_context(out)
    from_states = None
    for code in state_codes or []:
        found = admission_type_from_result_state(code)
        if found:
            from_states = found
    sources = [from_ctx, from_student, from_states]
    if ADMISSION_SINGLE_COURSE in sources:
        canon = ADMISSION_SINGLE_COURSE
    else:
        canon = from_ctx or from_student or from_states
    if not canon:
        return out
    out["admission_type"] = canon
    if canon == ADMISSION_SINGLE_COURSE:
        out["interview_result"] = ADMISSION_SINGLE_COURSE
        out["result"] = ADMISSION_SINGLE_COURSE
    else:
        out["interview_result"] = (
            normalize_admission_type(out.get("interview_result"))
            or normalize_admission_type(extra.get("interview_result"))
            or canon
        )
        out["result"] = out["interview_result"]
    nested = _as_mapping(out.get("student"))
    nested["admission_type"] = canon
    out["student"] = nested
    return out


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


def therapy_start_applicable(admission: Any = None) -> bool:
    """آیا مسیر «آغاز درمان آموزشی» برای این نوع پذیرش موضوعیت دارد؟

    تک‌درس اصلاً مسیر درمان ندارد. مشروط و پذیرش کامل (و جامع بدون admission) بله.
    """
    canonical = normalize_admission_type(admission)
    if canonical == ADMISSION_SINGLE_COURSE:
        return False
    return True


def should_auto_start_educational_therapy(
    admission: Any = None,
    course_type: Any = None,
) -> bool:
    """آیا پس از ثبت‌نام باید start_therapy به‌اجبار به‌عنوان مسیر اصلی باز شود؟

    دوره جامع: بله (مهلت هفته نهم). آشنایی فقط برای پذیرش کامل. مشروط و تک‌درس خیر.
    """
    ct = str(course_type or "").strip().lower()
    if ct == "comprehensive":
        return True
    return normalize_admission_type(admission) == ADMISSION_FULL


def term2_blocked_without_active_therapist(
    admission: Any = None,
    *,
    has_active_therapist: bool = False,
) -> bool:
    """ثبت‌نام ترم دوم برای پذیرش مشروط بدون درمانگر فعال مجاز نیست."""
    return (
        normalize_admission_type(admission) == ADMISSION_CONDITIONAL_THERAPY
        and not bool(has_active_therapist)
    )


TERM2_THERAPY_REQUIRED_FA = (
    "شما درمانگر فعالی ندارید و امکان ثبت‌نام شما برای ترم دوم ممکن نیست. "
    "پذیرش مشروط به درمان تا قبل از ثبت‌نام ترم دوم باید فرایند «آغاز درمان آموزشی» را تکمیل کند."
)

SINGLE_COURSE_NO_START_THERAPY_FA = (
    "پذیرش تک‌درس شامل مسیر آغاز درمان آموزشی نیست؛ ادامه از پنل دروس و کلاس‌هاست."
)

# متن ثابت پنل دانشجو پس از نتیجهٔ مصاحبه «پذیرش مشروط به شروع درمان شخصی (۱ تا ۵ درس)»
CONDITIONAL_THERAPY_TERM2_NOTICE_FA = (
    "به علت پذیرش مشروط به آغاز درمان آموزشی در دوره آشنایی پس از آغاز درمان آموزشی "
    "امکان ثبت نام در ترم دوم وجود دارد."
)

_INTRO_STATES_AFTER_CONDITIONAL_RESULT = frozenset({
    "result_conditional_therapy",
    "documents_upload",
    "documents_incomplete",
    "documents_review",
    "credentials_created",
    "course_selection",
    "payment",
    "registration_complete",
    "installment_overdue",
})


def therapy_deadline_hint_fa(*, deadline: Optional[str] = None) -> str:
    del deadline
    return CONDITIONAL_THERAPY_TERM2_NOTICE_FA


def should_show_conditional_therapy_term2_notice(
    *,
    process_code: Optional[str] = None,
    state_code: Optional[str] = None,
    context: Optional[dict] = None,
) -> bool:
    """پس از پرداخت مصاحبه و ثبت نتیجهٔ پذیرش مشروط، همین پیام به دانشجو نشان داده شود."""
    if str(state_code or "").strip() == "result_conditional_therapy":
        return True
    admission = resolve_admission_type_from_context(context)
    if admission != ADMISSION_CONDITIONAL_THERAPY:
        return False
    code = str(process_code or "").strip()
    if not code:
        return True
    if code == "start_therapy":
        return True
    if code == "introductory_course_registration":
        if not state_code:
            return True
        return str(state_code).strip() in _INTRO_STATES_AFTER_CONDITIONAL_RESULT
    return False


def resolve_conditional_therapy_student_why_fa(
    *,
    process_code: Optional[str] = None,
    state_code: Optional[str] = None,
    context: Optional[dict] = None,
    existing_why: str = "",
) -> str:
    if should_show_conditional_therapy_term2_notice(
        process_code=process_code,
        state_code=state_code,
        context=context,
    ) and str(state_code or "").strip() in {
        "result_conditional_therapy",
        "registration_complete",
    }:
        return CONDITIONAL_THERAPY_TERM2_NOTICE_FA
    return existing_why
