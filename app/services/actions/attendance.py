"""Attendance marking and block-hour accounting.

Part of the ActionHandler split. Every method below runs as a mixin method
on ActionHandler, so `self` exposes the whole handler surface.
"""

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from app.services.attendance_tracking_sync import (
    cancel_attendance_instances_for_therapy_session_ids,
    ensure_attendance_instance_for_session,
)
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.orm.attributes import flag_modified
import uuid

from app.services.actions._shared import (
    _as_mapping,
    logger,
    parse_therapy_session_id_list,
)


class AttendanceActionsMixin:
    """Attendance marking and block-hour accounting."""

    async def _handle_mark_cancelled(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = _as_mapping(instance.context_data)
        if context:
            for k in ("selected_sessions", "cancelled_session_ids", "sessions_cancelled", "session_dates"):
                if k in context:
                    ctx[k] = context[k]
        merged = {**ctx, **(context or {})}
        selected_ids = parse_therapy_session_id_list(merged.get("selected_sessions"))
        cancelled_ids: list[uuid.UUID] = []
        if selected_ids and instance.process_code == "student_session_cancellation":
            tag = f"student_session_cancellation:{instance.id}"
            for sid in selected_ids:
                r = await self.db.execute(
                    select(TherapySession).where(
                        TherapySession.id == sid,
                        TherapySession.student_id == instance.student_id,
                    )
                )
                ts = r.scalars().first()
                if not ts:
                    raise ValueError(f"جلسهٔ درمان یافت نشد: {sid}")
                if ts.status != "scheduled":
                    raise ValueError(f"فقط جلسات برنامه‌ریزی‌شده قابل کنسل هستند ({ts.session_date}).")
                ts.status = "cancelled"
                prev = (ts.notes or "").strip()
                ts.notes = f"{prev} — [{tag}]".strip(" —") if prev else f"[{tag}]"
                cancelled_ids.append(ts.id)
            if cancelled_ids:
                try:
                    await cancel_attendance_instances_for_therapy_session_ids(self.db, cancelled_ids)
                except Exception:
                    logger.exception("cancel_attendance_instances_for student cancellation failed")
            ctx["cancelled_session_ids"] = [str(x) for x in cancelled_ids]
            ctx["cancellation_applied_at"] = datetime.now(timezone.utc).isoformat()
        elif selected_ids and instance.process_code == "student_supervision_cancellation":
            from app.services.supervisor_session_cancellation_service import _parse_date

            tag = f"student_supervision_cancellation:{instance.id}"
            cancelled_inst_ids: list[str] = []
            for sid in selected_ids:
                sup_inst = await self.db.get(ProcessInstance, sid)
                if (
                    not sup_inst
                    or sup_inst.student_id != instance.student_id
                    or sup_inst.process_code != "supervision_50h_completion"
                ):
                    raise ValueError(f"جلسهٔ سوپرویژن یافت نشد: {sid}")
                if sup_inst.current_state_code not in ("session_scheduled", "supervisor_recording"):
                    raise ValueError("فقط جلسات برنامه‌ریزی‌شدهٔ سوپرویژن قابل کنسل هستند.")
                sctx = _as_mapping(sup_inst.context_data)
                sd = _parse_date(sctx.get("session_date") or sctx.get("supervision_session_date"))
                sctx["block_reason"] = "session_cancelled"
                sctx["cancelled_by"] = "student"
                sctx["cancellation_tag"] = tag
                sctx["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                if sd:
                    sctx["cancelled_session_date"] = sd.isoformat()
                sup_inst.context_data = sctx
                sup_inst.current_state_code = "recording_closed"
                sup_inst.is_completed = True
                sup_inst.completed_at = datetime.now(timezone.utc)
                flag_modified(sup_inst, "context_data")
                cancelled_inst_ids.append(str(sup_inst.id))
            if cancelled_inst_ids:
                student = await self._get_student(instance.student_id)
                if student:
                    extra = _as_mapping(student.extra_data)
                    prev = int(extra.get("supervision_cancelled_sessions_count") or 0)
                    extra["supervision_cancelled_sessions_count"] = prev + len(cancelled_inst_ids)
                    student.extra_data = extra
                    flag_modified(student, "extra_data")
            ctx["cancelled_supervision_instance_ids"] = cancelled_inst_ids
            ctx["cancelled_session_ids"] = cancelled_inst_ids
            ctx["cancellation_applied_at"] = datetime.now(timezone.utc).isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "sessions_marked_cancelled_by_student"

    async def _handle_block_attendance(self, action: dict, instance: ProcessInstance, context: dict):
        from app.services.class_attendance_service import (
            CLASS_PRESENT_BLOCK_REASON_FA,
            TUITION_PRESENT_BLOCK_PROCESS_CODES,
        )

        # قسط معوق شهریه → قفل ثبت «حاضر» در کلاس (SOP)
        if instance.process_code in TUITION_PRESENT_BLOCK_PROCESS_CODES:
            student = await self._get_student(instance.student_id)
            if not student:
                return "student_not_found"
            extra = _as_mapping(student.extra_data)
            reason = (
                (action.get("message_fa") or "").strip()
                or CLASS_PRESENT_BLOCK_REASON_FA
            )
            extra["class_present_blocked"] = {
                "active": True,
                "instance_id": str(instance.id),
                "process_code": instance.process_code,
                "locked_at": datetime.now(timezone.utc).isoformat(),
                "reason_fa": reason,
            }
            student.extra_data = extra
            flag_modified(student, "extra_data")
            return "class_present_blocked"

        if instance.process_code == "violation_registration":
            from app.services.hub_student_flags import apply_violation_present_block

            student = await self._get_student(instance.student_id)
            if not student:
                return "student_not_found"
            extra = _as_mapping(student.extra_data)
            apply_violation_present_block(extra, instance)
            student.extra_data = extra
            flag_modified(student, "extra_data")
            return "class_present_blocked"

        if instance.process_code != "student_supervision_cancellation":
            return "attendance_blocked_for_cancelled_sessions"
        from app.services.supervisor_session_cancellation_service import _parse_date

        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        cancelled_ids = merged.get("cancelled_supervision_instance_ids") or merged.get(
            "cancelled_session_ids"
        ) or []
        if isinstance(cancelled_ids, str):
            cancelled_ids = [cancelled_ids]
        student = await self._get_student(instance.student_id)
        if not student:
            return "attendance_blocked_for_cancelled_sessions"
        extra = _as_mapping(student.extra_data)
        lms = _as_mapping(extra.get("lms"))
        att = dict(lms.get("attendance_enabled") or {})
        blocked = list(lms.get("supervision_attendance_blocked_dates") or [])
        for raw_id in cancelled_ids:
            try:
                sup_inst = await self.db.get(ProcessInstance, uuid.UUID(str(raw_id)))
            except (TypeError, ValueError):
                sup_inst = None
            if not sup_inst:
                continue
            sctx = _as_mapping(sup_inst.context_data)
            sd = _parse_date(
                sctx.get("cancelled_session_date")
                or sctx.get("session_date")
                or sctx.get("supervision_session_date")
            )
            sup_key = str(sctx.get("supervisor_id") or student.supervisor_id or "current")
            entry = dict(att.get(sup_key) or {})
            entry["enabled"] = False
            entry["blocked_at"] = datetime.now(timezone.utc).isoformat()
            entry["reason"] = "student_supervision_cancellation"
            if sd:
                entry["blocked_date"] = sd.isoformat()
                if sd.isoformat() not in blocked:
                    blocked.append(sd.isoformat())
            att[sup_key] = entry
        lms["attendance_enabled"] = att
        lms["supervision_attendance_blocked_dates"] = blocked
        extra["lms"] = lms
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "attendance_blocked_for_cancelled_sessions"


# action type -> handler; merged into ActionHandler._registry
REGISTRY = {
    'mark_sessions_cancelled_by_student': AttendanceActionsMixin._handle_mark_cancelled,
    'block_attendance_for_cancelled_sessions': AttendanceActionsMixin._handle_block_attendance,
    'block_attendance_registration': AttendanceActionsMixin._handle_block_attendance,
}
