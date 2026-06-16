"""صندوق پیگیری کارهای اپراتور (فرایند + تکالیف بدون نمره) — فقط برای مدیر اصلی در API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import Assignment, AssignmentSubmission, ProcessInstance, Student, User
from app.services.nav_pending_counts import (
    _waiting_committee,
    _waiting_site_manager,
    _waiting_staff,
    _waiting_supervisor,
    _waiting_therapist,
)

# صف دانشجو — از لیست اپراتور حذف می‌شود
_EXCLUDE_ASSIGNED_ROLES = frozenset(
    {
        "student",
        "applicant",
        "system",
    }
)

# نقش‌های متادیتا → برچسب فارسی (در صورت نبود، خود کد نقش نمایش داده می‌شود)
_ROLE_LABELS_FA: dict[str, str] = {
    "staff": "کارمند دفتر",
    "finance": "اپراتور مالی",
    "therapist": "درمانگر",
    "supervisor": "سوپروایزر",
    "site_manager": "مسئول سایت",
    "instructor": "مدرس / دستیار آموزشی",
    "admissions_officer": "پذیرش / امور ثبت‌نام",
    "deputy_education_director": "معاون آموزش",
    "deputy_education": "معاون آموزش",
    "scientific_officer_course_committee": "مسئول علمی کمیته دروس",
    "progress_committee": "کمیته پیشرفت",
    "education_committee": "کمیته آموزش",
    "supervision_committee": "کمیته نظارت",
    "specialized_commission": "کمیسیون تخصصی",
    "therapy_committee_chair": "مسئول کمیته درمان",
    "therapy_committee_executor": "مجری کمیته درمان",
    "monitoring_committee_officer": "مسئول کمیته نظارت",
    "interviewer": "مصاحبه‌گر",
    "admin": "مدیر سیستم",
}


def _label_for_role(code: str) -> str:
    return _ROLE_LABELS_FA.get(code, code)


def _infer_fallback_role(state: str) -> Optional[tuple[str, str]]:
    """اگر assigned_role در متادیتا نیست، تخمین محدود مثل nav_pending_counts (بدون همپوشانی سخت)."""
    if not state:
        return None
    if _waiting_staff(state):
        return ("staff", _label_for_role("staff"))
    if _waiting_site_manager(state):
        return ("site_manager", _label_for_role("site_manager"))
    if _waiting_therapist(state):
        return ("therapist", _label_for_role("therapist"))
    if _waiting_supervisor(state):
        return ("supervisor", _label_for_role("supervisor"))
    if _waiting_committee(state, "admin"):
        return ("committee", "کمیته / تصمیم چندنفره")
    return None


def _resolve_process_item(
    assigned_role: Optional[str],
    state_code: str,
    ambiguous: bool,
) -> Optional[tuple[str, str, bool]]:
    """
    برمی‌گرداند (role_code, label_fa, uncertain) یا None اگر باید حذف شود.
    """
    ar = (assigned_role or "").strip() or None
    if ar and ar.lower() in _EXCLUDE_ASSIGNED_ROLES:
        return None
    uncertain = ambiguous
    if ar:
        return (ar, _label_for_role(ar), uncertain)

    inf = _infer_fallback_role(state_code)
    if not inf:
        return ("unknown", "نیاز به بررسی دستی / متادیتای ناقص", True)

    code, label = inf
    return (code, label, uncertain)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


async def build_operator_followup_inbox(
    db: AsyncSession,
    *,
    process_limit: int = 150,
    assignment_limit: int = 50,
    scan_cap: int = 800,
    student_id: Optional[uuid.UUID] = None,
    student_code: Optional[str] = None,
) -> dict[str, Any]:
    """
    process_limit / assignment_limit سقف جداگانه؛ scan_cap حداکثر ردیف فرایند برای پردازش در یک درخواست.
    """
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
    if student_id is not None:
        stmt = stmt.where(Student.id == student_id)
    elif student_code and str(student_code).strip():
        stmt = stmt.where(Student.student_code == str(student_code).strip())
    # نزولی بر اساس آخرین ترنزیشن تا پرونده‌های تازه‌فعال در سقف scan_cap دیده شوند
    # (asc روی started_at قدیمی‌ترین‌ها را پر می‌کرد و کار جاری را پنهان می‌کرد)
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
        ar = state_def.assigned_role if state_def is not None else None
        ambiguous = False  # تخمین تک‌مسیره؛ در نسخه بعد می‌توان چندمسیره علامت زد

        resolved = _resolve_process_item(ar, st_code, ambiguous)
        if resolved is None:
            continue
        role_code, role_label, uncertain = resolved

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
                "responsible_role_code": role_code,
                "responsible_role_label_fa": role_label,
                "inferred": ar is None,
                "uncertain": uncertain,
                "sort_at": _iso(pi.started_at),
            }
        )
        if len(process_items) >= process_limit:
            break

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
    if student_id is not None:
        sub_stmt = sub_stmt.where(Student.id == student_id)
    elif student_code and str(student_code).strip():
        sub_stmt = sub_stmt.where(Student.student_code == str(student_code).strip())
    sub_stmt = sub_stmt.order_by(AssignmentSubmission.submitted_at.asc()).limit(assignment_limit)
    r2 = await db.execute(sub_stmt)
    assign_rows = r2.all()

    assignment_items: list[dict[str, Any]] = []
    for sub, assign, student in assign_rows:
        assignment_items.append(
            {
                "kind": "assignment_grading",
                "assignment_id": str(assign.id),
                "submission_id": str(sub.id),
                "student_id": str(student.id),
                "student_code": student.student_code,
                "title_fa": assign.title_fa,
                "responsible_role_code": "staff",
                "responsible_role_label_fa": "کارمند دفتر / مدرس (تصحیح تکلیف)",
                "inferred": False,
                "uncertain": False,
                "sort_at": _iso(sub.submitted_at),
            }
        )

    merged = process_items + assignment_items
    merged.sort(key=lambda x: (x.get("sort_at") or "", x.get("kind", "")))

    return {
        "items": merged,
        "summary": {
            "process_count": len(process_items),
            "assignment_count": len(assignment_items),
            "scan_cap": scan_cap,
        },
    }


async def build_operator_followup_inbox_full(
    db: AsyncSession,
    *,
    process_limit: int = 150,
    assignment_limit: int = 50,
    scan_cap: int = 800,
    student_id: Optional[uuid.UUID] = None,
    student_code: Optional[str] = None,
    include_reference: bool = True,
    include_gaps: bool = False,
    gap_limit: int = 100,
    readiness_user: Optional[User] = None,
) -> dict[str, Any]:
    """
    صندوق کامل: بک‌لاگ + مرجع ثابت + اختیاری gap_items.
    کمبودها on-demand اجرا می‌شوند (بدون cron اجباری).
    اگر readiness_user مدیر (admin) باشد، هشدارهای آمادگی همهٔ اپراتورها هم اضافه می‌شود.
    """
    from app.services.operator_gap_engine import compute_operator_gaps
    from app.services.operator_reference_catalog import build_reference_block
    from app.services.operator_readiness import compute_operator_readiness_alerts

    core = await build_operator_followup_inbox(
        db,
        process_limit=process_limit,
        assignment_limit=assignment_limit,
        scan_cap=scan_cap,
        student_id=student_id,
        student_code=student_code,
    )
    out: dict[str, Any] = dict(core)
    summary: dict[str, Any] = dict(core.get("summary") or {})

    if include_reference:
        out["reference"] = build_reference_block()
    else:
        out["reference"] = None

    if include_gaps:
        gaps = await compute_operator_gaps(db, limit=gap_limit, student_id=student_id)
        out["gap_items"] = gaps
        summary["gap_count"] = len(gaps)
    else:
        out["gap_items"] = []
        summary["gap_count"] = 0

    out["readiness_alerts"] = []
    summary["readiness_count"] = 0
    if readiness_user is not None and (readiness_user.role or "").strip() == "admin":
        ralerts = await compute_operator_readiness_alerts(db, readiness_user)
        out["readiness_alerts"] = ralerts
        summary["readiness_count"] = len(ralerts)

    out["summary"] = summary
    return out
