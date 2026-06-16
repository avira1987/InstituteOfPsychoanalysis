"""مسیر ورود پنل به ازای User.role — منبع واحد برای /api/auth/home و redirect فرانت."""

from __future__ import annotations

from urllib.parse import urlencode

# نقش کمیته → kind مسیر
_COMMITTEE_ROLE_TO_KIND: dict[str, str] = {
    "progress_committee": "progress",
    "education_committee": "education",
    "deputy_education": "education",
    "supervision_committee": "supervision",
    "monitoring_committee_officer": "supervision",
    "specialized_commission": "supervision",
    "therapy_committee_chair": "therapy",
    "therapy_committee_executor": "therapy",
}

STAFF_DEFAULT_LANE = "admissions"

_STAFF_LANE_BY_ASSIGNED: dict[str, str] = {}
for _lane, _roles in {
    "admissions": ("admissions_officer", "admission_officer", "interviewer"),
    "instruction": ("instructor", "teaching_assistant", "teaching_assistant_or_instructor"),
    "therapy-coord": ("therapy_education_coordinator",),
    "course-committee": (
        "course_committee",
        "course_committee_scientific",
        "course_committee_executive",
        "scientific_officer_course_committee",
    ),
}.items():
    for _r in _roles:
        _STAFF_LANE_BY_ASSIGNED[_r] = _lane

_ASSIGNED_TO_COMMITTEE_KIND: dict[str, str] = {
    "committee": "progress",
    "progress_committee": "progress",
    "progress_committee_project": "progress",
    "education_committee": "education",
    "deputy_education": "education",
    "deputy_education_director": "education",
    "course_committee_executive": "education",
    "scientific_officer_course_committee": "education",
    "supervision_committee": "supervision",
    "monitoring_committee_officer": "supervision",
    "specialized_commission": "supervision",
    "therapy_committee_chair": "therapy",
    "therapy_committee_executor": "therapy",
}


def staff_lane_for_assigned_role(code: str | None) -> str:
    if not code:
        return STAFF_DEFAULT_LANE
    return _STAFF_LANE_BY_ASSIGNED.get(code.strip(), STAFF_DEFAULT_LANE)


def committee_kind_for_assigned_role(code: str | None) -> str:
    if not code:
        return "progress"
    return _ASSIGNED_TO_COMMITTEE_KIND.get(code.strip(), "progress")


def committee_kind_for_role(role: str | None) -> str:
    if not role:
        return "progress"
    return _COMMITTEE_ROLE_TO_KIND.get(role.strip(), "progress")


def staff_lane_path(lane: str = STAFF_DEFAULT_LANE) -> str:
    return f"/panel/portal/staff/{lane}"


def committee_kind_path(kind: str | None = None, role: str | None = None) -> str:
    k = kind or committee_kind_for_role(role)
    return f"/panel/portal/committee/{k}"


# (path, default_tasks_tab) — tab=None یعنی بدون query
PORTAL_ROLE_HOME: dict[str, tuple[str, str | None]] = {
    "student": ("/panel/portal/student", None),
    "therapist": ("/panel/portal/therapist", "pending"),
    "supervisor": ("/panel/portal/supervisor", "reviews"),
    "staff": (staff_lane_path(STAFF_DEFAULT_LANE), "pending"),
    "site_manager": ("/panel/portal/site-manager", "pending"),
    "interviewer": ("/panel/portal/interviewer", None),
    "finance": ("/panel/finance", None),
    "progress_committee": (committee_kind_path("progress"), "reviews"),
    "education_committee": (committee_kind_path("education"), "reviews"),
    "supervision_committee": (committee_kind_path("supervision"), "reviews"),
    "specialized_commission": (committee_kind_path("supervision"), "reviews"),
    "therapy_committee_chair": (committee_kind_path("therapy"), "reviews"),
    "therapy_committee_executor": (committee_kind_path("therapy"), "reviews"),
    "deputy_education": (committee_kind_path("education"), "reviews"),
    "monitoring_committee_officer": (committee_kind_path("supervision"), "reviews"),
    "admin": ("/panel", None),
}


def portal_home_path(role: str | None) -> str | None:
    """مسیر پایه پنل؛ None اگر نقش در نقشه نیست."""
    if not role:
        return None
    entry = PORTAL_ROLE_HOME.get(role.strip())
    return entry[0] if entry else None


def default_tasks_tab_for_role(role: str | None) -> str | None:
    """تب کارتابل پیش‌فرض: pending | reviews | None."""
    if not role:
        return None
    entry = PORTAL_ROLE_HOME.get(role.strip())
    return entry[1] if entry else None


def redirect_url_for_role(role: str | None) -> str:
    """
    URL کامل برای redirect بعد از login یا /panel.
    نقش ناشناخته → /panel (داشبورد عمومی).
    """
    if not role:
        return "/panel"
    entry = PORTAL_ROLE_HOME.get(role.strip())
    if not entry:
        return "/panel"
    path, tab = entry
    if tab:
        return f"{path}?{urlencode({'tab': tab})}"
    return path
