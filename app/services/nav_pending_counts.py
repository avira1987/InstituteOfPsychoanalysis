"""
شمارش کارهای منتظر برای آیتم‌های منوی کناری — هم‌راستا با منطق پنل‌های React
(TherapistPortal، SupervisorPortal، StaffPortal، SiteManagerPortal، CommitteePortal).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance, Student, SupportTicket, User

# ─── همان آرایه‌های کلیدواژهٔ پنل‌های فرانت ───────────────────────────────

_THERAPIST_REVIEW_STATES = (
    "therapist_review",
    "therapist_decision",
    "awaiting_therapist",
    "therapist_confirmation",
    "pending_therapist",
    "waiting_therapist",
)

_SUPERVISOR_REVIEW_STATES = (
    "supervisor_review",
    "supervisor_decision",
    "awaiting_supervisor",
    "pending_supervisor",
    "supervisor_approval",
    "therapist_review",
)

_STAFF_REVIEW_STATES = (
    "staff_review",
    "staff_verification",
    "pending_staff",
    "office_review",
    "payment_verification",
    "payment_required",
    "awaiting_payment",
    "document_check",
)

_SITE_MANAGER_REVIEW_STATES = (
    "site_manager_review",
    "site_manager_followup",
    "pending_site_manager",
    "attendance_check",
    "followup_required",
    "site_review",
)

# CommitteePortal.jsx — roleConfig + defaultConfig
_COMMITTEE_KEYWORDS: dict[str, list[str]] = {
    "progress_committee": [
        "committee_review",
        "progress_committee",
        "leave_review",
        "progress_review",
        "awaiting_committee",
        "restart_review",
        "therapist_change_review",
    ],
    "education_committee": [
        "education_committee",
        "education_review",
        "final_verdict",
        "continuation_review",
    ],
    "supervision_committee": [
        "supervision_committee",
        "supervision_review",
        "disciplinary_review",
    ],
    "specialized_commission": [
        "specialized_commission",
        "commission_review",
        "eligibility_review",
        "early_termination",
    ],
    "therapy_committee_chair": [
        "therapy_committee",
        "chair_review",
        "delegation",
        "no_show",
    ],
    "therapy_committee_executor": [
        "executor_review",
        "followup",
        "executor_report",
        "definitive_stop",
    ],
    "deputy_education": [
        "deputy_review",
        "sla_alert",
        "escalation",
        "deputy_education",
    ],
    "monitoring_committee_officer": [
        "monitoring",
        "violation",
        "referral",
        "monitoring_committee",
    ],
}

_DEFAULT_COMMITTEE_KEYWORDS = ["review", "committee", "pending", "awaiting"]


def _waiting_therapist(state: str) -> bool:
    if not state:
        return False
    if any(rs in state for rs in _THERAPIST_REVIEW_STATES):
        return True
    return "therapist" in state or "review" in state


def _waiting_supervisor(state: str) -> bool:
    if not state:
        return False
    if any(rs in state for rs in _SUPERVISOR_REVIEW_STATES):
        return True
    return "supervisor" in state or "review" in state


def _waiting_staff(state: str) -> bool:
    if not state:
        return False
    if any(rs in state for rs in _STAFF_REVIEW_STATES):
        return True
    return "staff" in state or "payment" in state or "office" in state


def _waiting_site_manager(state: str) -> bool:
    if not state:
        return False
    if any(rs in state for rs in _SITE_MANAGER_REVIEW_STATES):
        return True
    return "site_manager" in state or "followup" in state


def _committee_keywords_for_user(role: str) -> list[str]:
    if role in _COMMITTEE_KEYWORDS:
        return _COMMITTEE_KEYWORDS[role]
    return _DEFAULT_COMMITTEE_KEYWORDS


def _waiting_committee(state: str, role: str) -> bool:
    if not state:
        return False
    kws = _committee_keywords_for_user(role)
    return any(kw in state for kw in kws)


async def _ticket_pending_count(db: AsyncSession, user: User) -> int:
    stmt = select(func.count(SupportTicket.id)).where(
        SupportTicket.status.in_(("open", "in_progress"))
    )
    if user.role != "admin":
        stmt = stmt.where(
            or_(
                SupportTicket.assignee_id == user.id,
                SupportTicket.requester_id == user.id,
            )
        )
    r = await db.execute(stmt)
    return int(r.scalar() or 0)


def _user_sees_nav_path(user_role: str, path: str) -> bool:
    """هم‌راستا با فیلتر navItems در Layout.jsx — فقط همان مسیرهایی که کاربر در منو دارد."""
    meta = [
        ("/panel/portal/student", ["student"], True),
        ("/panel/portal/therapist", ["therapist", "admin"], False),
        ("/panel/portal/supervisor", ["supervisor", "admin"], False),
        ("/panel/portal/staff", ["staff", "admin"], False),
        ("/panel/portal/site-manager", ["site_manager", "admin"], False),
        (
            "/panel/portal/committee",
            [
                "progress_committee",
                "education_committee",
                "supervision_committee",
                "specialized_commission",
                "therapy_committee_chair",
                "therapy_committee_executor",
                "deputy_education",
                "monitoring_committee_officer",
                "admin",
            ],
            False,
        ),
        (
            "/panel/tickets",
            [
                "student",
                "admin",
                "staff",
                "finance",
                "therapist",
                "supervisor",
                "site_manager",
                "progress_committee",
                "education_committee",
                "supervision_committee",
                "specialized_commission",
                "therapy_committee_chair",
                "therapy_committee_executor",
                "deputy_education",
                "monitoring_committee_officer",
            ],
            False,
        ),
    ]
    for p, roles, strict in meta:
        if p != path:
            continue
        in_role = user_role in roles
        if strict:
            return in_role
        if not in_role and user_role != "admin":
            return False
        return True
    return False


async def compute_nav_pending_counts(db: AsyncSession, user: User) -> dict[str, Any]:
    """
    برمی‌گرداند: { "counts": { "/panel/portal/therapist": n, ... } }
    فقط برای مسیرهایی که کاربر در منو می‌بیند (بدون افشای آمار نقش‌های دیگر).
    """
    counts: dict[str, int] = {}
    role = user.role or ""

    stmt = select(ProcessInstance.current_state_code).where(
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
    )
    r = await db.execute(stmt)
    states = [row[0] or "" for row in r.all()]

    n_therapist = sum(1 for s in states if _waiting_therapist(s))
    n_supervisor = sum(1 for s in states if _waiting_supervisor(s))
    n_staff = sum(1 for s in states if _waiting_staff(s))
    n_site = sum(1 for s in states if _waiting_site_manager(s))
    n_committee = sum(1 for s in states if _waiting_committee(s, role))

    counts["/panel/portal/therapist"] = n_therapist
    counts["/panel/portal/supervisor"] = n_supervisor
    counts["/panel/portal/staff"] = n_staff
    counts["/panel/portal/site-manager"] = n_site
    counts["/panel/portal/committee"] = n_committee

    if role == "student":
        sr = await db.execute(select(Student.id).where(Student.user_id == user.id))
        row = sr.first()
        if row:
            sid = row[0]
            cr = await db.execute(
                select(func.count(ProcessInstance.id)).where(
                    ProcessInstance.student_id == sid,
                    ProcessInstance.is_completed.is_(False),
                    ProcessInstance.is_cancelled.is_(False),
                )
            )
            counts["/panel/portal/student"] = int(cr.scalar() or 0)
        else:
            counts["/panel/portal/student"] = 0

    counts["/panel/tickets"] = await _ticket_pending_count(db, user)

    filtered = {k: v for k, v in counts.items() if _user_sees_nav_path(role, k)}
    return {"counts": filtered}
