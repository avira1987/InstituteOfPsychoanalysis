"""Routing and validation helpers for process edit requests."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InterviewSlot, ProcessInstance, User

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RULES_PATH = _REPO_ROOT / "metadata" / "edit_request_rules.json"
_PORTAL_ROLE_MAP_PATH = _REPO_ROOT / "metadata" / "portal_role_assigned_role_map.json"


@lru_cache(maxsize=1)
def _load_rules_raw() -> dict[str, Any]:
    if not _RULES_PATH.is_file():
        return {"version": 0, "rules": []}
    with _RULES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_portal_role_map_raw() -> dict[str, Any]:
    if not _PORTAL_ROLE_MAP_PATH.is_file():
        return {"portal_roles": {}}
    with _PORTAL_ROLE_MAP_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def list_edit_request_rules() -> list[dict[str, Any]]:
    raw = _load_rules_raw()
    rows = raw.get("rules") or []
    return [r for r in rows if isinstance(r, dict)]


def find_edit_request_rule(process_code: str, state_code: str, form_code: Optional[str]) -> Optional[dict[str, Any]]:
    for row in list_edit_request_rules():
        if row.get("process_code") != process_code:
            continue
        if row.get("state_code") != state_code:
            continue
        fc = row.get("form_code")
        if form_code and fc and fc != form_code:
            continue
        return row
    return None


def normalize_requested_fields(requested: list[str], allowed: list[str]) -> list[str]:
    allowed_set = {str(x) for x in (allowed or []) if x}
    out: list[str] = []
    for f in requested or []:
        s = str(f).strip()
        if not s:
            continue
        if s in allowed_set and s not in out:
            out.append(s)
    return out


async def _find_active_user_by_id(db: AsyncSession, user_id: Optional[str]) -> Optional[User]:
    if not user_id:
        return None
    try:
        import uuid

        uid = uuid.UUID(str(user_id))
    except Exception:
        return None
    r = await db.execute(select(User).where(User.id == uid, User.is_active.is_(True)))
    return r.scalars().first()


async def _resolve_creator_assignee(
    db: AsyncSession,
    *,
    instance: ProcessInstance,
    state_code: str,
    target_role: str,
) -> Optional[User]:
    ctx = instance.context_data if isinstance(instance.context_data, dict) else {}
    # درمان: اگر خود دانشجو درمانگر انتخاب کرده، ابتدا همان فرد
    if target_role == "therapist":
        u = await _find_active_user_by_id(db, ctx.get("therapist_id"))
        if u and u.role == "therapist":
            return u

    # مصاحبه: owner از InterviewSlot
    if target_role == "interviewer" or "interview" in state_code:
        q = (
            select(InterviewSlot)
            .where(InterviewSlot.assigned_instance_id == instance.id)
            .order_by(InterviewSlot.created_at.desc())
            .limit(1)
        )
        row = (await db.execute(q)).scalars().first()
        if row:
            for cand in (row.interviewer_user_id, row.created_by):
                if cand is None:
                    continue
                r = await db.execute(select(User).where(User.id == cand, User.is_active.is_(True)))
                u = r.scalars().first()
                if u and u.role != "student":
                    return u
    return None


def _resolve_portal_roles_for_assigned_role(target_role: str) -> list[str]:
    raw = _load_portal_role_map_raw()
    portal_roles = raw.get("portal_roles") or {}
    out: list[str] = []
    for role_name, cfg in portal_roles.items():
        if not isinstance(cfg, dict):
            continue
        arr = cfg.get("assigned_roles")
        if isinstance(arr, list) and target_role in arr:
            out.append(role_name)
    return out


async def _resolve_role_assignee(db: AsyncSession, target_role: str) -> Optional[User]:
    # اول تلاش مستقیم با User.role
    r0 = await db.execute(
        select(User)
        .where(User.role == target_role, User.is_active.is_(True))
        .order_by(User.created_at.asc())
    )
    u = r0.scalars().first()
    if u:
        return u

    # نگاشت assigned_role -> portal role
    portal_roles = _resolve_portal_roles_for_assigned_role(target_role)
    if not portal_roles:
        return None
    r1 = await db.execute(
        select(User)
        .where(User.role.in_(portal_roles), User.is_active.is_(True))
        .order_by(User.created_at.asc())
    )
    return r1.scalars().first()


async def resolve_edit_request_assignee(
    db: AsyncSession,
    *,
    instance: ProcessInstance,
    state_code: str,
    rule: dict[str, Any],
    triage_user: User,
) -> tuple[User, dict[str, Any]]:
    target_role = str(rule.get("default_target_role") or "").strip()
    trace: dict[str, Any] = {
        "strategy": "creator_then_role_then_triage",
        "target_role": target_role,
        "route": "triage",
    }

    if target_role:
        creator_u = await _resolve_creator_assignee(
            db,
            instance=instance,
            state_code=state_code,
            target_role=target_role,
        )
        if creator_u:
            trace["route"] = "creator"
            trace["assignee_role"] = creator_u.role
            return creator_u, trace

        role_u = await _resolve_role_assignee(db, target_role)
        if role_u:
            trace["route"] = "role"
            trace["assignee_role"] = role_u.role
            return role_u, trace

    trace["assignee_role"] = triage_user.role
    return triage_user, trace


def invalidate_edit_request_router_caches() -> None:
    _load_rules_raw.cache_clear()
    _load_portal_role_map_raw.cache_clear()
