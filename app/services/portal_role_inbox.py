"""صف نمونه‌های فرایند باز برای نقش ورود (پنل) — بر اساس assigned_role در DB + نگاشت portal."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.meta.operator_state_catalog import normalize_assigned_role, resolve_portal_role_to_assigned_roles
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import Assignment, AssignmentSubmission, ProcessInstance, Student
from app.services.operator_followup_inbox import _resolve_process_item


# مراحل «بررسی/تکمیل مدارک» مخصوص پذیرش/کارمند است و نباید در فید اعلان
# نقش‌های کمیته/درمانگر/سوپروایزر دیده شود.
_DOCUMENT_REVIEW_STATE_CODES = frozenset(
    {
        "documents_review",
        "documents_incomplete",
        "documents_upload",
    }
)

_DOCUMENT_REVIEW_HIDDEN_PORTAL_ROLES = frozenset(
    {
        "therapist",
        "supervisor",
        "committee",
        "progress_committee",
        "education_committee",
        "supervision_committee",
        "specialized_commission",
        "therapy_committee_chair",
        "therapy_committee_executor",
        "monitoring_committee_officer",
    }
)


def _should_hide_document_review(portal_role: str, state_code: str) -> bool:
    pr = (portal_role or "").strip().lower()
    sc = (state_code or "").strip()
    return pr in _DOCUMENT_REVIEW_HIDDEN_PORTAL_ROLES and sc in _DOCUMENT_REVIEW_STATE_CODES


def _portal_role_matches_item(
    portal_role: str,
    assigned_role_raw: Optional[str],
    state_code: str,
    resolved_code: str,
    target_roles: Optional[list[str]],
) -> bool:
    """target_roles از resolve_portal_role_to_assigned_roles؛ None یعنی همه (مثل admin)."""
    if target_roles is None:
        return True
    if not target_roles:
        return False
    ar = normalize_assigned_role((assigned_role_raw or "").strip())
    if ar and ar in target_roles:
        return True
    if resolved_code in target_roles:
        return True
    # تخمین «کارمند» وقتی assigned_role در متادیتا خالی است
    if portal_role == "staff" and resolved_code == "staff":
        return True
    return False


async def build_portal_role_process_inbox(
    db: AsyncSession,
    *,
    portal_role: str,
    process_limit: int = 120,
    scan_cap: int = 600,
    include_assignments_for_staff: bool = True,
) -> dict[str, Any]:
    """
    نمونه‌های فرایند باز که مرحلهٔ فعلی به نقش پنل (طبق portal_role_assigned_role_map) نسبت داده می‌شود.
    برای student خالی؛ برای admin همهٔ موارد غیردانشجو (همان None در نگاشت به‌صورت همهٔ کدهای اپراتوری
    در کاتالوگ — اینجا با target_roles=None همهٔ ردیف‌های غیرحذف‌شده را می‌گیریم).
    """
    if portal_role == "student":
        return {
            "items": [],
            "summary": {"process_count": 0, "assignment_count": 0, "portal_role": portal_role},
        }

    target_roles = resolve_portal_role_to_assigned_roles(portal_role)

    sd = aliased(StateDefinition)
    pd = aliased(ProcessDefinition)

    stmt = (
        select(ProcessInstance, Student, pd, sd)
        .join(Student, ProcessInstance.student_id == Student.id)
        .join(pd, ProcessInstance.process_code == pd.code)
        .outerjoin(
            sd,
            (sd.process_id == pd.id) & (sd.code == ProcessInstance.current_state_code),
        )
        .where(
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
        )
    )
    stmt = stmt.order_by(
        desc(ProcessInstance.last_transition_at),
        desc(ProcessInstance.started_at),
    ).limit(scan_cap)

    r = await db.execute(stmt)
    rows = r.all()

    process_items: list[dict[str, Any]] = []
    for row in rows:
        pi, student, proc_def, state_def = row
        st_code = (pi.current_state_code or "").strip()
        if _should_hide_document_review(portal_role, st_code):
            continue
        ar_raw = state_def.assigned_role if state_def is not None else None
        resolved = _resolve_process_item(ar_raw, st_code, False)
        if resolved is None:
            continue
        resolved_code, role_label, uncertain = resolved

        if not _portal_role_matches_item(portal_role, ar_raw, st_code, resolved_code, target_roles):
            continue

        process_items.append(
            {
                "kind": "process",
                "instance_id": str(pi.id),
                "student_id": str(student.id),
                "student_code": student.student_code,
                "process_code": pi.process_code,
                "process_name_fa": proc_def.name_fa,
                "state_code": st_code,
                "state_name_fa": state_def.name_fa if state_def is not None else st_code,
                "responsible_role_code": resolved_code,
                "responsible_role_label_fa": role_label,
                "assigned_role_raw": ar_raw,
                "inferred": ar_raw is None,
                "uncertain": uncertain,
                "sort_at": pi.started_at.isoformat() if pi.started_at else None,
            }
        )
        if len(process_items) >= process_limit:
            break

    assignment_items: list[dict[str, Any]] = []
    if include_assignments_for_staff and portal_role in ("staff", "admin"):
        sub_stmt = (
            select(AssignmentSubmission, Assignment, Student)
            .join(Assignment, AssignmentSubmission.assignment_id == Assignment.id)
            .join(Student, AssignmentSubmission.student_id == Student.id)
            .where(
                AssignmentSubmission.score.is_(None),
                AssignmentSubmission.body_text.isnot(None),
                AssignmentSubmission.body_text != "",
            )
        )
        sub_stmt = sub_stmt.order_by(AssignmentSubmission.submitted_at.asc()).limit(40)
        r2 = await db.execute(sub_stmt)
        for sub, assign, student in r2.all():
            assignment_items.append(
                {
                    "kind": "assignment_grading",
                    "assignment_id": str(assign.id),
                    "submission_id": str(sub.id),
                    "student_id": str(student.id),
                    "student_code": student.student_code,
                    "title_fa": assign.title_fa,
                    "responsible_role_code": "staff",
                    "sort_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
                }
            )

    merged = process_items + assignment_items
    merged.sort(key=lambda x: (x.get("sort_at") or "", x.get("kind", "")))

    return {
        "items": merged,
        "summary": {
            "process_count": len(process_items),
            "assignment_count": len(assignment_items),
            "portal_role": portal_role,
            "target_roles": target_roles,
        },
    }
