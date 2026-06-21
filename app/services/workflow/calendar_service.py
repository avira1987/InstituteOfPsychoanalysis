"""Service F - Calendar / Scheduling-Rules Service.

Replaces the log-only stub for date-rule computation and calendar publishing.

- ``apply_24h_rule_for_start_date`` computes a real start date (>= now + 24h,
  rolled to the next week when the requested date is too soon) and writes it to
  ``ProcessInstance.context_data['calculated_start_date']``.
- ``record_interruption_dates`` / ``register_in_calendar`` /
  ``publish_academic_calendar_to_profiles`` / ``monitor_return_at_end_date``
  persist calendar entries and return-monitoring reminders.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.workflow import _common as C


def _parse_date(val) -> Optional[datetime]:
    if not val:
        return None
    try:
        s = str(val)[:10]
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    ctx = C.merged_context(instance, action, context)

    if action_type == "apply_24h_rule_for_start_date":
        requested = _parse_date(
            ctx.get("requested_start_date") or ctx.get("first_session_date") or ctx.get("start_date")
        )
        earliest = datetime.now(timezone.utc) + timedelta(hours=24)
        if requested is None or requested < earliest:
            # Roll to the next week boundary from the earliest allowed moment.
            start = earliest + timedelta(days=(7 - earliest.weekday()) % 7 or 7) if requested is not None else earliest
        else:
            start = requested
        ic = C.instance_ctx(instance)
        ic["calculated_start_date"] = start.date().isoformat()
        ic["start_date_rule"] = "24h"
        C.commit_instance_ctx(instance, ic)
        C.record_event(instance, action_type, {"calculated_start_date": ic["calculated_start_date"]})
        return f"calculated_start_date={ic['calculated_start_date']}"

    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"
    extra = C.student_extra(student)

    if action_type == "record_interruption_dates":
        rec = {
            "id": C.new_id(),
            "start": ctx.get("interruption_start_date") or ctx.get("start_date"),
            "end": ctx.get("interruption_end_date") or ctx.get("end_date"),
            "process_code": instance.process_code,
            "recorded_at": C.now_iso(),
        }
        items = list(extra.get("interruptions") or [])
        items.append(rec)
        extra["interruptions"] = items
        C.commit_student_extra(student, extra)
        C.record_event(instance, action_type, {"start": rec["start"], "end": rec["end"]})
        return "interruption_dates_recorded"

    if action_type == "register_in_calendar":
        ev = {
            "id": C.new_id(),
            "title_fa": action.get("title_fa") or ctx.get("event_title_fa") or instance.process_code,
            "date": ctx.get("event_date") or ctx.get("date"),
            "process_code": instance.process_code,
            "created_at": C.now_iso(),
        }
        items = list(extra.get("calendar_events") or [])
        items.append(ev)
        extra["calendar_events"] = items
        C.commit_student_extra(student, extra)
        C.record_event(instance, action_type, {"date": ev["date"]})
        return "calendar_event_registered"

    if action_type == "publish_academic_calendar_to_profiles":
        from app.services.institute_calendar_service import publish_calendar_from_instance_context

        ic = C.instance_ctx(instance)
        merged = {**ic, **ctx}
        actor_raw = ctx.get("published_by") or ctx.get("actor_id")
        published_by = None
        if actor_raw:
            try:
                published_by = uuid.UUID(str(actor_raw))
            except (TypeError, ValueError):
                published_by = None
        cal = await publish_calendar_from_instance_context(
            db, instance, merged, published_by=published_by
        )
        extra["academic_calendar_published"] = True
        extra["academic_calendar_published_at"] = C.now_iso()
        if cal.term_start_date:
            extra["term_start_date"] = cal.term_start_date.isoformat()
        if cal.term_end_date:
            extra["term_end_date"] = cal.term_end_date.isoformat()
        C.commit_student_extra(student, extra)
        C.record_event(
            instance,
            action_type,
            {"published": True, "term_code": cal.term_code},
        )
        return f"academic_calendar_published term={cal.term_code}"

    if action_type == "monitor_return_at_end_date":
        end = ctx.get("interruption_end_date") or ctx.get("end_date") or ctx.get("return_date")
        rec = {
            "id": C.new_id(),
            "type": "return_monitor",
            "due_at": str(end) if end else None,
            "process_code": instance.process_code,
            "created_at": C.now_iso(),
            "sent": False,
        }
        items = list(extra.get("scheduled_reminders") or [])
        items.append(rec)
        extra["scheduled_reminders"] = items
        C.commit_student_extra(student, extra)
        C.record_event(instance, action_type, {"due_at": rec["due_at"]})
        return f"return_monitor_scheduled due={rec['due_at']}"

    C.record_event(instance, action_type, {"unhandled_in": "calendar_service"})
    return f"calendar_noop:{action_type}"
