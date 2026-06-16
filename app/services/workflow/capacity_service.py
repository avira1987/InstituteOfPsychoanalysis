"""Service E - Capacity & Retention Service.

Replaces the log-only stub for intern capacity counters and assignment
retention. Persisted under ``Student.extra_data``:

    capacity        -> {"intern_capacity": int, ...}
    retention       -> {"patients": bool, "supervisor": bool, "therapist": bool}
    therapist_assignment / supervisor_assignment -> "past_list" when moved
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.workflow import _common as C


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    ctx = C.merged_context(instance, action, context)
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"

    extra = C.student_extra(student)
    result = action_type

    if action_type == "increase_intern_capacity":
        try:
            delta = int(action.get("amount") or ctx.get("capacity_delta") or ctx.get("additional_capacity") or 1)
        except (TypeError, ValueError):
            delta = 1
        cap = dict(extra.get("capacity") or {})
        cap["intern_capacity"] = int(cap.get("intern_capacity") or 0) + delta
        cap["updated_at"] = C.now_iso()
        extra["capacity"] = cap
        result = f"intern_capacity={cap['intern_capacity']}"

    elif action_type in ("retain_patients", "retain_supervisor", "retain_therapist_and_supervisor"):
        retention = dict(extra.get("retention") or {})
        if action_type == "retain_patients":
            retention["patients"] = True
        elif action_type == "retain_supervisor":
            retention["supervisor"] = True
        else:
            retention["therapist"] = True
            retention["supervisor"] = True
        retention["updated_at"] = C.now_iso()
        extra["retention"] = retention
        result = f"retained:{action_type}"

    elif action_type == "move_to_past_lists":
        extra["therapist_assignment"] = "past_list"
        extra["supervisor_assignment"] = "past_list"
        extra["moved_to_past_at"] = C.now_iso()
        result = "moved_to_past_lists"

    else:
        C.record_event(instance, action_type, {"unhandled_in": "capacity_service"})
        return f"capacity_noop:{action_type}"

    C.commit_student_extra(student, extra)
    C.record_event(instance, action_type, {"result": result})
    return result
