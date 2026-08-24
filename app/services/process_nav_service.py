"""ساخت آیتم‌های منوی سایدبار فرایند + شمارش کار منتظر."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.user_roles import operator_portal_roles, primary_role
from app.meta.operator_state_catalog import normalize_assigned_role
from app.meta.process_nav_catalog import (
    attach_pending_counts,
    get_process_nav_catalog_for_portal_role,
    process_nav_path,
)
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import ProcessInstance, Student, User


async def _pending_by_process_for_operator(
    db: AsyncSession,
    user: User,
) -> dict[str, int]:
    from app.services.portal_role_inbox import build_user_process_inbox

    inbox = await build_user_process_inbox(
        db,
        user,
        process_limit=200,
        scan_cap=2000,
        include_assignments_for_staff=False,
    )
    counts: Counter[str] = Counter()
    for item in inbox.get("items") or []:
        if item.get("kind") != "process":
            continue
        code = (item.get("process_code") or "").strip().lower()
        if code:
            counts[code] += 1
    return dict(counts)


def _merge_process_nav_catalogs(portal_roles: list[str]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for role in portal_roles:
        for row in get_process_nav_catalog_for_portal_role(role):
            code = (row.get("process_code") or "").strip().lower()
            if not code or code in seen:
                continue
            seen.add(code)
            merged.append(dict(row))
    return merged


async def _pending_by_process_for_student(db: AsyncSession, user: User) -> dict[str, int]:
    sr = await db.execute(select(Student.id).where(Student.user_id == user.id))
    row = sr.first()
    if not row:
        return {}

    student_id = row[0]
    sd = aliased(StateDefinition)
    pd = aliased(ProcessDefinition)

    stmt = (
        select(ProcessInstance.process_code, sd.assigned_role)
        .join(pd, ProcessInstance.process_code == pd.code)
        .outerjoin(
            sd,
            (sd.process_id == pd.id) & (sd.code == ProcessInstance.current_state_code),
        )
        .where(
            ProcessInstance.student_id == student_id,
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
        )
    )
    r = await db.execute(stmt)
    counts: Counter[str] = Counter()
    for process_code, assigned_role in r.all():
        ar = normalize_assigned_role(assigned_role)
        if ar not in ("student", "applicant"):
            continue
        code = (process_code or "").strip().lower()
        if code:
            counts[code] += 1
    return dict(counts)


async def build_process_nav_items(db: AsyncSession, user: User) -> dict[str, Any]:
    """فهرست فرایندهای سایدبار برای نقش جاری با شمارش pending."""
    role = primary_role(user)
    if role == "student":
        catalog = get_process_nav_catalog_for_portal_role("student")
        pending = await _pending_by_process_for_student(db, user)
    else:
        op_roles = operator_portal_roles(user) or [role]
        catalog = _merge_process_nav_catalogs(op_roles)
        pending = await _pending_by_process_for_operator(db, user)

    items = attach_pending_counts(catalog, pending)
    return {
        "portal_role": role,
        "items": items,
        "summary": {
            "process_count": len(items),
            "pending_total": sum(int(x.get("pending_count") or 0) for x in items),
        },
    }


async def compute_process_nav_pending_counts(db: AsyncSession, user: User) -> dict[str, int]:
    """مسیر /panel/process-nav/{code} → تعداد کار منتظر."""
    data = await build_process_nav_items(db, user)
    out: dict[str, int] = {}
    for item in data.get("items") or []:
        n = int(item.get("pending_count") or 0)
        if n <= 0:
            continue
        path = item.get("path") or process_nav_path(item.get("process_code") or "")
        out[path] = n
    return out
