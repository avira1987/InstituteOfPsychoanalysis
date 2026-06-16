"""Service H - Role Promotion & Account Service.

Replaces the log-only stub for role/rank changes and account provisioning.
Mutates real ``User`` columns plus a rank record in ``Student.extra_data``:

    move_ta_to_instructor          -> User.role = 'instructor', rank = 'instructor'
    upgrade_rank_to_assistant_faculty -> rank = 'assistant_faculty'
    create_user_account            -> ensure portal account active/provisioned
    revoke_student_access          -> User.is_active = False, access_revoked flag
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_password_hash
from app.models.operational_models import ProcessInstance
from app.services.workflow import _common as C


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"
    user = await C.get_user(db, student.user_id)
    extra = C.student_extra(student)
    result = action_type

    if action_type == "move_ta_to_instructor":
        if user:
            user.role = "instructor"
        extra["rank"] = "instructor"
        extra["rank_updated_at"] = C.now_iso()
        result = "promoted_to_instructor"

    elif action_type == "upgrade_rank_to_assistant_faculty":
        if user:
            user.role = "assistant_faculty"
        extra["rank"] = "assistant_faculty"
        extra["rank_updated_at"] = C.now_iso()
        result = "promoted_to_assistant_faculty"

    elif action_type == "create_user_account":
        plain: str | None = None
        if user:
            user.is_active = True
            if (user.role or "").strip() not in ("student", "applicant"):
                user.role = "student"
            plain = secrets.token_urlsafe(8)[:12]
            user.hashed_password = get_password_hash(plain)
            if not (user.username or "").strip() and (user.phone or "").strip():
                user.username = (user.phone or "").strip()
        extra["account_provisioned"] = True
        extra["account_provisioned_at"] = C.now_iso()
        if user and plain:
            ctx = dict(C.as_mapping(instance.context_data))
            login_deadline = (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat()
            ctx["portal_username"] = (user.username or "").strip()
            ctx["portal_password_display"] = plain
            ctx["lms_login_deadline"] = login_deadline
            ctx["portal_credentials_issued_at"] = C.now_iso()
            instance.context_data = ctx
            flag_modified(instance, "context_data")
        result = "account_provisioned"

    elif action_type == "revoke_student_access":
        if user:
            user.is_active = False
        extra["access_revoked"] = True
        extra["access_revoked_at"] = C.now_iso()
        result = "access_revoked"

    else:
        C.record_event(instance, action_type, {"unhandled_in": "role_promotion"})
        return f"role_noop:{action_type}"

    C.commit_student_extra(student, extra)
    C.record_event(instance, action_type, {"result": result})
    return result
