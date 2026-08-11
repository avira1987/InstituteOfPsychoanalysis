"""Service A - Notification & Portal-Display Service.

Replaces the log-only stub for portal display messages, reminders, dashboard
feeds and instructor notifications. All output is persisted as real, queryable
state that the student/staff portals render:

- ``Student.extra_data['portal_messages']``      -> UI banners/popups/errors
- ``Student.extra_data['scheduled_reminders']``  -> due-dated reminders (job-pickable)
- ``Student.extra_data['notification_outbox']``  -> instructor/role notifications
- ``ProcessInstance.context_data['dashboard_feed']`` / ``['committee_queue']``
- ``Student.extra_data['sla_breaches']``          -> SLA breach log
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.notification_service import notification_service
from app.services.workflow import _common as C

_DISPLAY_KINDS = {
    "show_popup": ("popup", "info"),
    "show_payment_confirmation": ("payment_confirmation", "success"),
    "display_error_message": ("error", "error"),
    "display_meeting_in_portal": ("meeting", "info"),
    "display_rejection_explanations": ("rejection", "warning"),
    "display_mandatory_message": ("mandatory", "warning"),
    "display_available_supervisor_slots": ("supervisor_slots", "info"),
    "display_calculated_start_date": ("start_date", "info"),
    "display_evaluation_warning_to_supervisor": ("evaluation_warning", "warning"),
}


def _text_for(action_type: str, ctx: dict, action: dict) -> str:
    explicit = (action.get("message_fa") or action.get("message") or action.get("text") or "").strip()
    if explicit:
        return explicit
    mapping = {
        "show_popup": ctx.get("popup_message_fa") or "پیام سامانه",
        "show_payment_confirmation": "پرداخت شما با موفقیت ثبت شد.",
        "display_error_message": ctx.get("error_message_fa") or "خطا در انجام عملیات.",
        "display_meeting_in_portal": ctx.get("meeting_summary_fa") or "جلسه در پورتال نمایش داده شد.",
        "display_rejection_explanations": ctx.get("rejection_reason_fa") or "درخواست شما رد شد.",
        "display_mandatory_message": ctx.get("mandatory_message_fa") or "این مرحله الزامی است.",
        "display_available_supervisor_slots": "وقت‌های آزاد ناظران در دسترس است.",
        "display_calculated_start_date": (
            f"تاریخ شروع محاسبه‌شده: {ctx.get('calculated_start_date') or ctx.get('start_date') or '—'}"
        ),
        "display_evaluation_warning_to_supervisor": "ارزیابی شما هنوز تکمیل نشده است.",
    }
    return str(mapping.get(action_type, action_type))


def _parse_due(ctx: dict, action: dict) -> str:
    days = action.get("in_days") or ctx.get("reminder_in_days")
    due_raw = action.get("due_at") or ctx.get("reminder_due_at")
    if due_raw:
        return str(due_raw)
    try:
        d = int(days) if days is not None else 1
    except (TypeError, ValueError):
        d = 1
    return (datetime.now(timezone.utc) + timedelta(days=d)).isoformat()


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    ctx = C.merged_context(instance, action, context)
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"

    if action_type in _DISPLAY_KINDS:
        kind, severity = _DISPLAY_KINDS[action_type]
        item = {
            "id": C.new_id(),
            "kind": kind,
            "severity": severity,
            "text_fa": _text_for(action_type, ctx, action),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "created_at": C.now_iso(),
            "read": False,
        }
        C.append_to_extra_list(student, "portal_messages", item)
        C.record_event(instance, action_type, {"kind": kind})
        return f"portal_message:{kind}"

    if action_type in ("schedule_reminder", "scheduled_notification", "schedule_installment_reminders"):
        if action_type == "schedule_installment_reminders":
            ic = C.instance_ctx(instance)
            merged_ic = {**ic, **ctx}
            plan = merged_ic.get("installment_plan") or []
            reminder_days = 1
            try:
                reminder_days = max(1, int(action.get("reminder_days_before") or 1))
            except (TypeError, ValueError):
                pass
            gap_days = 30
            try:
                gap_days = max(1, int(action.get("installment_gap_days") or ctx.get("installment_gap_days") or 30))
            except (TypeError, ValueError):
                pass
            template = action.get("template") or "installment_reminder"
            created = []
            pending_items = [
                p for p in plan
                if isinstance(p, dict) and p.get("status") in ("pending", "overdue")
            ]
            if not pending_items:
                count = action.get("installments") or merged_ic.get("installment_count") or merged_ic.get(
                    "pending_installments_remaining"
                )
                try:
                    count = max(1, int(count)) if count is not None else 3
                except (TypeError, ValueError):
                    count = 3
                next_due_raw = merged_ic.get("next_installment_due_at")
                base_due = _parse_due(merged_ic, {"due_at": next_due_raw}) if next_due_raw else None
                if base_due is None:
                    base_due = datetime.now(timezone.utc) + timedelta(days=gap_days)
                for i in range(count):
                    due_at = base_due + timedelta(days=gap_days * i)
                    remind_at = due_at - timedelta(days=reminder_days)
                    from app.utils.shamsi_calendar_utils import tehran_calendar_date

                    due_day = tehran_calendar_date(due_at) or due_at.date()
                    rec = {
                        "id": C.new_id(),
                        "type": "installment",
                        "sequence": i + 1,
                        "due_at": remind_at.isoformat(),
                        "installment_due_at": due_day.isoformat(),
                        "template": template,
                        "process_code": instance.process_code,
                        "instance_id": str(instance.id),
                        "created_at": C.now_iso(),
                        "sent": False,
                    }
                    C.append_to_extra_list(student, "scheduled_reminders", rec)
                    created.append(rec["id"])
            else:
                for item in pending_items:
                    due_raw = item.get("due_at")
                    due_at = _parse_due(merged_ic, {"due_at": due_raw})
                    if due_at is None:
                        continue
                    remind_at = due_at - timedelta(days=reminder_days)
                    from app.utils.shamsi_calendar_utils import tehran_calendar_date

                    due_day = tehran_calendar_date(due_at) or due_at.date()
                    rec = {
                        "id": C.new_id(),
                        "type": "installment",
                        "sequence": item.get("index"),
                        "due_at": remind_at.isoformat(),
                        "installment_due_at": due_day.isoformat(),
                        "amount_rial": item.get("amount_rial"),
                        "template": template,
                        "process_code": instance.process_code,
                        "instance_id": str(instance.id),
                        "created_at": C.now_iso(),
                        "sent": False,
                    }
                    C.append_to_extra_list(student, "scheduled_reminders", rec)
                    created.append(rec["id"])
            C.record_event(instance, action_type, {"installments": len(created), "created_ids": created})
            return f"scheduled_installment_reminders n={len(created)}"
        rec = {
            "id": C.new_id(),
            "type": action_type,
            "due_at": _parse_due(ctx, action),
            "template": action.get("template") or ctx.get("reminder_template") or "process_reminder",
            "recipients": action.get("recipients") or ["student"],
            "process_code": instance.process_code,
            "created_at": C.now_iso(),
            "sent": False,
        }
        C.append_to_extra_list(student, "scheduled_reminders", rec)
        C.record_event(instance, action_type, {"due_at": rec["due_at"]})
        return f"reminder_scheduled due={rec['due_at']}"

    if action_type == "notify_instructor":
        rec = {
            "id": C.new_id(),
            "role": "instructor",
            "template": action.get("template") or "instructor_notification",
            "text_fa": _text_for(action_type, ctx, action) if action.get("message_fa") else (
                ctx.get("instructor_message_fa") or "اعلان جدید درباره دانشجو"
            ),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "created_at": C.now_iso(),
            "delivered": False,
        }
        # Best-effort real delivery if an instructor phone is resolvable.
        instructor_id = ctx.get("instructor_id") or ctx.get("instructor_user_id")
        instructor = await C.get_user(db, instructor_id) if instructor_id else None
        if instructor and instructor.phone:
            try:
                result = await notification_service.send_notification(
                    "sms", rec["template"], instructor.phone,
                    {"student_name": getattr(student, "student_code", "")},
                    message_override=rec["text_fa"],
                )
                rec["delivered"] = bool(getattr(result, "success", False))
            except Exception:
                rec["delivered"] = False
        C.append_to_extra_list(student, "notification_outbox", rec)
        C.record_event(instance, action_type, {"delivered": rec["delivered"]})
        return f"notify_instructor delivered={rec['delivered']}"

    if action_type in ("send_to_dashboard", "send_to_progress_committee"):
        key = "dashboard_feed" if action_type == "send_to_dashboard" else "committee_queue"
        item = {
            "id": C.new_id(),
            "student_id": str(instance.student_id),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "title_fa": action.get("title_fa") or ctx.get("dashboard_title_fa") or instance.process_code,
            "created_at": C.now_iso(),
            "status": "open",
        }
        C.append_to_ctx_list(instance, key, item)
        C.record_event(instance, action_type, {"queue": key})
        return f"{action_type}:{key}"

    if action_type == "log_sla_breach_in_portals":
        item = {
            "id": C.new_id(),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "state": instance.current_state_code,
            "logged_at": C.now_iso(),
        }
        C.append_to_extra_list(student, "sla_breaches", item)
        C.record_event(instance, action_type, {"state": instance.current_state_code})
        return "sla_breach_logged"

    if action_type == "share_document_with_interviewer":
        item = {
            "id": C.new_id(),
            "document_ref": ctx.get("document_id") or ctx.get("document_ref"),
            "interviewer_id": ctx.get("interviewer_id"),
            "process_code": instance.process_code,
            "shared_at": C.now_iso(),
        }
        C.append_to_extra_list(student, "shared_documents", item)
        C.record_event(instance, action_type, {"interviewer_id": item["interviewer_id"]})
        return "document_shared_with_interviewer"

    # Unknown type routed here - keep audit trail, never break the transition.
    C.record_event(instance, action_type, {"unhandled_in": "portal_notifications"})
    return f"portal_noop:{action_type}"
