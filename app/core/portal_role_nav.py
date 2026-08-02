"""هم‌تراز با admin-ui/src/utils/portalRoleNav.js — فیلتر منوی کناری."""

from __future__ import annotations

from app.core.portal_role_home import committee_kind_path, staff_lane_path

ADMIN_ONLY_PATHS = frozenset({
    "/panel/processes",
    "/panel/rules",
    "/panel/dynamic-forms",
    "/panel/audit",
    "/panel/system-resources",
})

STAFF_LANE_IDS = ("admissions", "instruction", "content-ops", "therapy-coord", "course-committee")

STAFF_LANE_ROLES: dict[str, frozenset[str]] = {
    "admissions": frozenset({"admin", "staff", "interviewer"}),
    "instruction": frozenset({"admin", "staff"}),
    "content-ops": frozenset({"admin", "staff"}),
    "therapy-coord": frozenset({"admin", "staff"}),
    "course-committee": frozenset({"admin", "staff"}),
}

COMMITTEE_KIND_ROLES: dict[str, frozenset[str]] = {
    "progress": frozenset({"progress_committee", "admin"}),
    "education": frozenset({"education_committee", "deputy_education", "admin"}),
    "supervision": frozenset({
        "supervision_committee",
        "monitoring_committee_officer",
        "specialized_commission",
        "admin",
    }),
    "therapy": frozenset({"therapy_committee_chair", "therapy_committee_executor", "admin"}),
}

_SINGLE_PORTAL_ROLES: dict[str, frozenset[str]] = {
    "/panel/portal/student": frozenset({"student"}),
    "/panel/portal/therapist": frozenset({"therapist", "admin"}),
    "/panel/portal/supervisor": frozenset({"supervisor", "admin"}),
    "/panel/portal/interviewer": frozenset({"interviewer", "admin", "staff"}),
    "/panel/portal/site-manager": frozenset({"site_manager", "admin"}),
}

_SHARED_PATH_ROLES: dict[str, frozenset[str]] = {
    "/panel": frozenset({
        "admin", "staff", "finance", "therapist", "supervisor", "site_manager", "interviewer",
        "progress_committee", "education_committee", "supervision_committee",
        "specialized_commission", "therapy_committee_chair", "therapy_committee_executor",
        "deputy_education", "monitoring_committee_officer",
    }),
    "/panel/tickets": frozenset({
        "student", "admin", "staff", "finance", "therapist", "supervisor", "site_manager",
        "interviewer", "progress_committee", "education_committee", "supervision_committee",
        "specialized_commission", "therapy_committee_chair", "therapy_committee_executor",
        "deputy_education", "monitoring_committee_officer",
    }),
    "/panel/students": frozenset({"admin", "staff", "supervisor", "therapist"}),
    "/panel/reports": frozenset({"admin", "staff", "deputy_education", "monitoring_committee_officer", "finance"}),
    "/panel/users": frozenset({"admin"}),
    "/panel/finance": frozenset({"admin", "finance"}),
    "/panel/profile": frozenset(),  # همه
    "/panel/guide": frozenset(),
}


def user_sees_nav_path(user_role: str, path: str) -> bool:
    if not user_role:
        return False
    if user_role == "admin":
        return True
    if path in ADMIN_ONLY_PATHS:
        return False
    if user_role == "student" and path == "/panel":
        return False
    for lane_id, roles in STAFF_LANE_ROLES.items():
        if path == staff_lane_path(lane_id):
            return user_role in roles
    for kind_id, roles in COMMITTEE_KIND_ROLES.items():
        if path == committee_kind_path(kind_id):
            return user_role in roles
    if path in _SINGLE_PORTAL_ROLES:
        return user_role in _SINGLE_PORTAL_ROLES[path]
    if path in _SHARED_PATH_ROLES:
        allowed = _SHARED_PATH_ROLES[path]
        return not allowed or user_role in allowed
    if not path.startswith("/panel/portal/"):
        return path in ADMIN_ONLY_PATHS and user_role == "admin"
    return False


def staff_lane_paths() -> list[str]:
    return [staff_lane_path(lane) for lane in STAFF_LANE_IDS]


def committee_kind_paths() -> list[str]:
    return [committee_kind_path(k) for k in COMMITTEE_KIND_ROLES]
