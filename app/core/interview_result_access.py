"""Who may submit interview-result transitions (assigned interviewer, slot creator, or admin)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_roles import user_has_role
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
    "فقط مصاحبه‌گر همان مصاحبه، ایجادکنندهٔ وقت، یا مدیر اصلی سامانه می‌تواند نتیجهٔ مصاحبه را ثبت کند."
)

_RESULT_SUBMIT_ROLES = frozenset({"interviewer", "staff", "admin"})


def is_interview_result_trigger(trigger_event: str | None) -> bool:
    return (trigger_event or "") in INTERVIEW_RESULT_TRIGGER_EVENTS


def _instance_context_dict(raw: Any) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def user_may_submit_for_slot(user: User, slot: InterviewSlot) -> bool:
    """True when user is assigned interviewer or created the booked slot (staff/admin always; interviewer pool slots)."""
    uid = user.id
    assigned = getattr(slot, "interviewer_user_id", None)
    if assigned is not None and assigned == uid:
        return True
    if slot.created_by == uid:
        staff_like = user_has_role(user, "staff", admin_bypass=False)
        interviewer_like = user_has_role(user, "interviewer", admin_bypass=False)
        if interviewer_like and not staff_like:
            return assigned is None
        return True
    return False


def interviewer_owns_booked_slot(user: User, slot: InterviewSlot) -> bool:
    """Backward-compatible alias — interviewer capability + slot ownership."""
    if not user_has_role(user, "interviewer", admin_bypass=False):
        return False
    return user_may_submit_for_slot(user, slot)


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
    if user_has_role(user, "admin", admin_bypass=False):
        return True
    if not user_has_role(user, *_RESULT_SUBMIT_ROLES, admin_bypass=False):
        return False
    slot = await get_booked_slot_for_instance(db, instance)
    if slot is None:
        return False
    return user_may_submit_for_slot(user, slot)


async def overlay_slot_ownership_on_context(
    db: AsyncSession,
    instance: ProcessInstance,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """شناسهٔ مصاحبه‌گر/ایجادکننده را از اسلات زنده روی context داشبورد می‌گذارد."""
    slot = await get_booked_slot_for_instance(db, instance)
    if slot is None:
        return ctx
    out = dict(ctx)
    assigned = getattr(slot, "interviewer_user_id", None)
    if assigned is not None:
        out["interviewer_user_id"] = str(assigned)
    created = getattr(slot, "created_by", None)
    if created is not None:
        out["slot_created_by"] = str(created)
    return out


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
