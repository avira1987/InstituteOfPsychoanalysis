"""RBAC اختصاصی فرایندهای آماده‌سازی ترم (۲۹ / ۳۰).

Alias سراسری staff→کمیته دروس و admissions←deputy برای بقیهٔ فرایندها دست نخورده
می‌ماند؛ فقط fall/winter semester preparation از این جدول استفاده می‌کنند.
"""

from __future__ import annotations

from typing import Iterable

from app.core.user_roles import canonical_portal_role
from app.services.semester_prep_service import PREP_PROCESS_CODES

# نقش‌های پورتال مجاز برای هر state_code (علاوه بر admin که همیشه مجاز است)
_COURSE_COMMITTEE_PORTAL = frozenset(
    {
        "course_committee",
        "course_committee_executive",
        "course_committee_scientific",
        "scientific_officer_course_committee",
    }
)
_DEPUTY_PORTAL = frozenset({"deputy_education", "deputy_education_director"})
_STAFF_PORTAL = frozenset({"staff", "internal_manager"})
_ADMISSIONS_PORTAL = frozenset({"staff", "internal_manager", "admissions_officer"})

# state → نقش‌های پورتال مجاز برای اقدام روی فرم / ترنزیشن
FALL_STATE_PORTAL_ROLES: dict[str, frozenset[str]] = {
    "calendar_entry": _COURSE_COMMITTEE_PORTAL,
    "tuition_entry": _DEPUTY_PORTAL,
    "license_check": _DEPUTY_PORTAL,
    "course_list_creation": _COURSE_COMMITTEE_PORTAL,
    "course_finalization": _COURSE_COMMITTEE_PORTAL,
    "marketing_campaign": _ADMISSIONS_PORTAL,
    "interviewer_assignment": _STAFF_PORTAL,
    "interview_scheduling": _STAFF_PORTAL,
    "published": frozenset({"system"}),
}

WINTER_STATE_PORTAL_ROLES: dict[str, frozenset[str]] = {
    "license_check": _DEPUTY_PORTAL,
    "course_list_review": _COURSE_COMMITTEE_PORTAL,
    "course_finalization": _COURSE_COMMITTEE_PORTAL,
    "marketing_campaign": _ADMISSIONS_PORTAL,
    "interviewer_assignment": _STAFF_PORTAL,
    "interview_scheduling": _STAFF_PORTAL,
    "published": frozenset({"system"}),
}

# trigger → state مبدأ (برای validate_role وقتی فقط trigger داریم)
FALL_TRIGGER_FROM_STATE: dict[str, str] = {
    "calendar_submitted": "calendar_entry",
    "tuition_submitted": "tuition_entry",
    "license_reviewed": "license_check",
    "course_list_submitted": "course_list_creation",
    "courses_finalized": "course_finalization",
    "marketing_started": "marketing_campaign",
    "interviewers_assigned": "interviewer_assignment",
    "interview_times_set": "interview_scheduling",
}

WINTER_TRIGGER_FROM_STATE: dict[str, str] = {
    "license_reviewed": "license_check",
    "course_list_reviewed": "course_list_review",
    "courses_finalized": "course_finalization",
    "marketing_started": "marketing_campaign",
    "interviewers_assigned": "interviewer_assignment",
    "interview_times_set": "interview_scheduling",
}

# نقش‌های متادیتای assigned_role / recipients که برای آماده‌سازی به staff نگاشت می‌شوند
PREP_STAFF_ASSIGNED_ROLES = frozenset({"staff", "admissions_officer"})

INTERVIEW_SETUP_PORTAL_ROLES = _STAFF_PORTAL | frozenset({"admin"})

# مرحلهٔ یکپارچهٔ مصاحبه‌ها (گام آخر عملیاتی) — مسئول نمایشی: مدیر داخلی
PREP_INTERNAL_MANAGER_STATES = frozenset({"interviewer_assignment", "interview_scheduling"})


def is_prep_process(process_code: str | None) -> bool:
    return (process_code or "").strip() in PREP_PROCESS_CODES


def is_prep_internal_manager_state(process_code: str | None, state_code: str | None) -> bool:
    return is_prep_process(process_code) and (state_code or "").strip() in PREP_INTERNAL_MANAGER_STATES


def prep_responsible_role_label_fa(
    process_code: str | None,
    state_code: str | None,
    assigned_role: str | None,
    *,
    include_code: bool = True,
) -> str:
    """برچسب فارسی نقش مسئول مرحله — دسترسی را عوض نمی‌کند."""
    from app.meta.role_labels import label_role_fa

    if is_prep_internal_manager_state(process_code, state_code):
        return label_role_fa("internal_manager", include_code=include_code)
    return label_role_fa(assigned_role, include_code=include_code)


def _state_map(process_code: str) -> dict[str, frozenset[str]]:
    if process_code == "winter_semester_preparation":
        return WINTER_STATE_PORTAL_ROLES
    return FALL_STATE_PORTAL_ROLES


def _trigger_map(process_code: str) -> dict[str, str]:
    if process_code == "winter_semester_preparation":
        return WINTER_TRIGGER_FROM_STATE
    return FALL_TRIGGER_FROM_STATE


def normalize_prep_portal_role(role: str | None) -> str:
    raw = (role or "").strip()
    if raw == "internal_manager":
        return "internal_manager"
    return canonical_portal_role(raw) or raw


def portal_roles_for_prep_state(process_code: str, state_code: str) -> frozenset[str] | None:
    """None یعنی state ناشناخته — به لایهٔ عمومی واگذار شود."""
    if not is_prep_process(process_code):
        return None
    return _state_map(process_code).get((state_code or "").strip())


def portal_role_can_act_on_prep_state(
    portal_role: str | None,
    process_code: str | None,
    state_code: str | None,
) -> bool | None:
    """
    True/False اگر این فرایند آماده‌سازی است و state شناخته شده.
    None یعنی این لایه اعمال نشود (فرایند دیگر یا state نامشخص).
    """
    if not is_prep_process(process_code):
        return None
    allowed = portal_roles_for_prep_state(process_code or "", state_code or "")
    if allowed is None:
        return None
    role = normalize_prep_portal_role(portal_role)
    if role == "admin":
        return True
    if role == "system":
        return "system" in allowed
    # internal_manager و staff هر دو در _STAFF_PORTAL هستند
    if role in allowed:
        return True
    if role == "staff" and "internal_manager" in allowed:
        return True
    if role == "internal_manager" and "staff" in allowed:
        return True
    return False


def portal_role_can_fire_prep_trigger(
    portal_role: str | None,
    process_code: str | None,
    trigger_event: str | None,
    *,
    from_state: str | None = None,
) -> bool | None:
    """مجوز ترنزیشن آماده‌سازی بر اساس state مبدأ trigger."""
    if not is_prep_process(process_code):
        return None
    te = (trigger_event or "").strip()
    # SLA خودکار
    if te == "sla_expired":
        role = normalize_prep_portal_role(portal_role)
        return role in ("admin", "system")
    state = (from_state or "").strip() or _trigger_map(process_code or "").get(te, "")
    if not state:
        return None
    return portal_role_can_act_on_prep_state(portal_role, process_code, state)


def can_edit_prep_interview_setup(portal_role: str | None) -> bool:
    role = normalize_prep_portal_role(portal_role)
    if role == "admin":
        return True
    return role in _STAFF_PORTAL or role == "staff"


def prep_notification_portal_roles(assigned_role: str) -> tuple[str, ...]:
    """گیرندگان اعلان دست‌به‌دست آماده‌سازی — بدون fallback معاون برای پذیرش."""
    code = (assigned_role or "").strip().lower()
    if code in ("admissions_officer", "admission_officer"):
        return ("staff", "internal_manager", "admissions_officer")
    if code == "staff":
        return ("staff", "internal_manager")
    if code in ("deputy_education_director", "deputy_education"):
        return ("deputy_education",)
    if code in (
        "scientific_officer_course_committee",
        "course_committee_scientific",
        "course_committee_executive",
        "course_committee",
    ):
        return (
            "course_committee",
            "course_committee_executive",
            "scientific_officer_course_committee",
            "course_committee_scientific",
        )
    if code == "education_director":
        return ("deputy_education", "admin")
    from app.services.process_role_user_resolver import portal_roles_for_assigned_role

    return portal_roles_for_assigned_role(code)


def any_user_role_can_act_on_prep_state(
    roles: Iterable[str],
    process_code: str | None,
    state_code: str | None,
) -> bool | None:
    """اجتماع نقش‌های کاربر؛ None اگر لایهٔ prep اعمال نشود."""
    decided: bool | None = None
    for r in roles:
        hit = portal_role_can_act_on_prep_state(r, process_code, state_code)
        if hit is None:
            continue
        decided = True if hit else (False if decided is None else decided)
        if hit:
            return True
    return decided
