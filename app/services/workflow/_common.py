"""Shared helpers for workflow action services.

These utilities keep the per-service modules small and consistent: they read
the merged action/instance/transition context, mutate the JSONB stores safely
(with ``flag_modified``), and append a structured audit event so the legacy
``integration_events`` trail is preserved alongside the new real behavior.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import Student, User, ProcessInstance
from app.services.external_integration import append_integration_event


def as_mapping(val: Any) -> dict:
    """Normalize a JSONB column (dict / JSON-string / None) into a plain dict."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return dict(val)
    if isinstance(val, str):
        s = val.strip()
        if not s or s.lower() in ("null", "none"):
            return {}
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_student(db: AsyncSession, student_id) -> Optional[Student]:
    result = await db.execute(select(Student).where(Student.id == student_id))
    return result.scalars().first()


async def get_user(db: AsyncSession, user_id) -> Optional[User]:
    if user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


def merged_context(instance: ProcessInstance, action: dict, context: dict) -> dict:
    """Merge instance context, transition context and action params (action wins)."""
    action_params = {k: v for k, v in (action or {}).items() if k not in ("type", "payload")}
    return {
        **as_mapping(instance.context_data),
        **(context or {}),
        **(action.get("payload") or {}),
        **action_params,
    }


def instance_ctx(instance: ProcessInstance) -> dict:
    return as_mapping(instance.context_data)


def commit_instance_ctx(instance: ProcessInstance, ctx: dict) -> None:
    instance.context_data = ctx
    flag_modified(instance, "context_data")


def student_extra(student: Student) -> dict:
    return as_mapping(student.extra_data)


def commit_student_extra(student: Student, extra: dict) -> None:
    student.extra_data = extra
    flag_modified(student, "extra_data")


def append_to_extra_list(student: Student, key: str, item: dict, *, max_items: int = 200) -> dict:
    """Append ``item`` to ``student.extra_data[key]`` (a list) and persist."""
    extra = student_extra(student)
    items = list(extra.get(key) or [])
    items.append(item)
    if len(items) > max_items:
        items = items[-max_items:]
    extra[key] = items
    commit_student_extra(student, extra)
    return item


def append_to_ctx_list(instance: ProcessInstance, key: str, item: dict, *, max_items: int = 200) -> dict:
    """Append ``item`` to ``instance.context_data[key]`` (a list) and persist."""
    ctx = instance_ctx(instance)
    items = list(ctx.get(key) or [])
    items.append(item)
    if len(items) > max_items:
        items = items[-max_items:]
    ctx[key] = items
    commit_instance_ctx(instance, ctx)
    return item


def record_event(instance: ProcessInstance, action_type: str, detail: dict) -> None:
    """Preserve the structured audit trail in ``context_data.integration_events``."""
    append_integration_event(instance, action_type, {"detail": detail, "at": now_iso()})


def new_id() -> str:
    return str(uuid.uuid4())
