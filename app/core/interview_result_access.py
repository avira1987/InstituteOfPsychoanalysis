"""Who may submit interview-result transitions (own interviewer or site admin only)."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InterviewSlot, ProcessInstance, User

INTERVIEW_RESULT_TRIGGER_EVENTS = frozenset(
    {
        "interview_result_submitted",
        "interview_result_accepted",
        "interview_result_rejected",
        "interview_result_rejected_with_suggestion",
    }
)

_FORBIDDEN_DETAIL_FA = (
    "فقط مصاحبه‌گر همان مصاحبه یا مدیر اصلی سامانه می‌تواند نتیجهٔ مصاحبه را ثبت کند."
)


def is_interview_result_trigger(trigger_event: str | None) -> bool:
    return (trigger_event or "") in INTERVIEW_RESULT_TRIGGER_EVENTS


def _instance_context_dict(raw: Any) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def interviewer_owns_booked_slot(user: User, slot: InterviewSlot) -> bool:
    """True when this interviewer conducted / owns the booked slot."""
    if user.role != "interviewer":
        return False
    uid = user.id
    assigned = getattr(slot, "interviewer_user_id", None)
    if assigned is not None and assigned == uid:
        return True
    if assigned is None and slot.created_by == uid:
        return True
    return False


async def get_booked_slot_for_instance(
    db: AsyncSession,
    instance: ProcessInstance,
) -> Optional[InterviewSlot]:
    stmt = select(InterviewSlot).where(InterviewSlot.assigned_instance_id == instance.id)
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return None
    ctx = _instance_context_dict(instance.context_data)
    sel = (ctx.get("selected_timeslot") or "").strip()
    if sel:
        for slot in rows:
            if str(slot.id) == sel:
                return slot
    return rows[0]


async def can_submit_interview_result(
    db: AsyncSession,
    *,
    instance: ProcessInstance,
    user: User,
    trigger_event: str,
) -> bool:
    if not is_interview_result_trigger(trigger_event):
        return True
    role = (user.role or "").strip()
    if role == "admin":
        return True
    if role != "interviewer":
        return False
    slot = await get_booked_slot_for_instance(db, instance)
    if slot is None:
        return False
    return interviewer_owns_booked_slot(user, slot)


async def assert_can_submit_interview_result(
    db: AsyncSession,
    *,
    instance: ProcessInstance,
    user: User,
    trigger_event: str,
) -> None:
    from app.core.engine import UnauthorizedError

    if not await can_submit_interview_result(
        db, instance=instance, user=user, trigger_event=trigger_event
    ):
        raise UnauthorizedError(_FORBIDDEN_DETAIL_FA)
