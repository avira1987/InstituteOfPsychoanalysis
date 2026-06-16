"""Service G - Registration Gate Service.

Replaces the log-only stub for enrollment gate flags. Persisted under
``Student.extra_data['gates']`` as boolean flags with timestamps:

    future_applications_blocked
    future_enrollment_blocked
    next_term_registration_blocked
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.workflow import _common as C

_SET_FLAG = {
    "block_future_applications": ("future_applications_blocked", True),
    "block_future_enrollment": ("future_enrollment_blocked", True),
    "block_next_term_registration": ("next_term_registration_blocked", True),
    "unblock_next_term_registration": ("next_term_registration_blocked", False),
}


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"

    if action_type not in _SET_FLAG:
        C.record_event(instance, action_type, {"unhandled_in": "registration_gate"})
        return f"gate_noop:{action_type}"

    flag, value = _SET_FLAG[action_type]
    extra = C.student_extra(student)
    gates = dict(extra.get("gates") or {})
    gates[flag] = value
    gates[f"{flag}_at"] = C.now_iso()
    extra["gates"] = gates
    C.commit_student_extra(student, extra)
    C.record_event(instance, action_type, {flag: value})
    return f"gate:{flag}={value}"
