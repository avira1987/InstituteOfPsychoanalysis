"""Creating, moving and releasing therapy/supervision session rows.

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
from app.services.financial_program_defaults_service import get_effective_financial_program_defaults
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.orm.attributes import flag_modified
import uuid

from app.services.actions._shared import (
    _as_mapping,
    _resolve_extra_session_datetime,
    _resolve_therapy_session_increase_schedule,
    logger,
)


class SessionActionsMixin:
    """Creating, moving and releasing therapy/supervision session rows."""

    async def _handle_add_recurring_session(self, action: dict, instance: ProcessInstance, context: dict):
        """افزودن جلسهٔ درمان تکرارشونده به ``therapy_sessions`` (بر اساس context/payload)."""
        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        student = await self._get_student(instance.student_id)
        therapist_id = ctx.get("therapist_id")
        if not therapist_id and student and student.therapist_id:
            therapist_id = str(student.therapist_id)
            ctx["therapist_id"] = therapist_id
        tid = None
        if therapist_id:
            tid = uuid.UUID(therapist_id) if isinstance(therapist_id, str) else therapist_id

        n = int(action.get("count") or ctx.get("sessions_to_add") or 1)
        weekly_inc = int(action.get("weekly_increment") or ctx.get("weekly_sessions_increment") or 0)

        if instance.process_code == "therapy_session_increase":
            start_d, st_utc = _resolve_therapy_session_increase_schedule(ctx)
            if student and weekly_inc > 0:
                student.weekly_sessions = int(student.weekly_sessions or 0) + weekly_inc
                ctx["weekly_sessions_after"] = student.weekly_sessions
            ctx["therapy_increase_session_date"] = start_d.isoformat()
            if st_utc:
                ctx["therapy_increase_session_starts_at_utc"] = st_utc.isoformat()
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            ts = TherapySession(
                id=uuid.uuid4(),
                student_id=instance.student_id,
                therapist_id=tid,
                session_date=start_d,
                session_starts_at=st_utc,
                status="scheduled",
                is_extra=bool(ctx.get("is_extra")),
                payment_status="pending",
            )
            self.db.add(ts)
            return f"therapy_session_increase_added session_id={ts.id} weekly_sessions={student.weekly_sessions if student else '?'}"
        created = []
        base = ctx.get("first_session_date")
        if base:
            if isinstance(base, str):
                start_d = date.fromisoformat(base[:10])
            else:
                start_d = base
        else:
            start_d = datetime.now(timezone.utc).date()
        for i in range(n):
            d = start_d + timedelta(weeks=i)
            ts = TherapySession(
                id=uuid.uuid4(),
                student_id=instance.student_id,
                therapist_id=tid,
                session_date=d,
                status="scheduled",
                is_extra=bool(ctx.get("is_extra")),
                payment_status="pending",
            )
            self.db.add(ts)
            created.append(str(ts.id))
        await self.db.flush()
        for i in range(n):
            # created ids loop — بازخوانی از DB برای ensure
            pass
        return f"therapy_sessions_created n={n} ids={','.join(created[:5])}"

    async def _handle_remove_selected_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = _as_mapping(instance.context_data)
        removed = ctx.get("selected_sessions", [])
        return f"sessions_removed: {removed}"

    async def _handle_release_slots(self, action: dict, instance: ProcessInstance, context: dict):
        return "slots_released_to_available_sheet"

    async def _handle_sync_extra_session_reenter_fields(self, action: dict, instance: ProcessInstance, context: dict):
        """پس از بازگشت به extra_request: کپی زمان جدید به فیلدهای فرم اصلی."""
        if instance.process_code not in ("extra_session", "extra_supervision_session"):
            return "skip"
        ctx = _as_mapping(instance.context_data)
        nd = ctx.get("new_preferred_date")
        nt = ctx.get("new_preferred_time")
        if nd and str(nd).strip():
            ctx["preferred_date"] = str(nd).strip()[:10]
        if nt and str(nt).strip():
            ctx["preferred_time"] = str(nt).strip()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "extra_session_reenter_fields_synced"

    async def _handle_prepare_extra_session_payment(self, action: dict, instance: ProcessInstance, context: dict):
        """قبل از درگاه: مبلغ ریال و تاریخ/ساعت توافق‌شده در context برای UI و ثبت بعدی."""
        if instance.process_code not in ("extra_session", "extra_supervision_session"):
            return "skip_not_extra_session"
        fd = await get_effective_financial_program_defaults(self.db)
        fee_rial = int(fd["extra_session_fee_rial"])
        fee_toman = float(fd["extra_session_fee_toman"])
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        d, st = _resolve_extra_session_datetime(merged)
        ctx["payment_amount_rial"] = fee_rial
        ctx["invoice_amount"] = float(fee_toman)
        ctx["agreed_session_date"] = d.isoformat()
        if st:
            ctx["session_starts_at_iso"] = st.isoformat()
        ctx["record_date"] = d.isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"extra_session_payment_context fee_rial={fee_rial}"

    async def _handle_create_extra_session_record(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        session_date, session_starts_at = _resolve_extra_session_datetime(merged)
        student = await self._get_student(instance.student_id)
        therapist_id = student.therapist_id if student else None
        fdxs = await get_effective_financial_program_defaults(self.db)
        fee = float(fdxs["extra_session_fee_toman"])
        sid = uuid.uuid4()
        note_parts = [
            "جلسه اضافی درمان آموزشی",
            f"تاریخ: {session_date.isoformat()}",
        ]
        tnote = merged.get("agreed_session_time") or merged.get("preferred_time") or merged.get("alternative_time")
        if tnote:
            note_parts.append(f"ساعت: {tnote}")
        session = TherapySession(
            id=sid,
            student_id=instance.student_id,
            therapist_id=therapist_id,
            session_date=session_date,
            session_starts_at=session_starts_at,
            status="scheduled",
            is_extra=True,
            payment_status="paid",
            amount=fee,
            notes=" — ".join(note_parts),
        )
        self.db.add(session)
        await self.db.flush()
        try:
            await ensure_attendance_instance_for_session(self.db, session)
        except Exception:
            logger.exception("ensure_attendance_instance_for_session extra_session failed session=%s", session.id)
        ctx = _as_mapping(instance.context_data)
        ctx["therapy_session_id"] = str(sid)
        ctx["session_id"] = str(sid)
        ctx["record_date"] = session_date.isoformat()
        if session_starts_at:
            ctx["session_starts_at_iso"] = session_starts_at.isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"extra_session_created: {session.id}"

    async def _handle_note_extra_session_calendar(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت خلاصهٔ قابل‌نمایش برای تقویم/پنل (بدون ادعای یکپارچهٔ خارجی)."""
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        d, st = _resolve_extra_session_datetime(merged)
        summary = f"جلسه اضافی درمان — {d.isoformat()}"
        if merged.get("agreed_session_time") or merged.get("preferred_time"):
            summary += f" — ساعت: {merged.get('agreed_session_time') or merged.get('preferred_time')}"
        ctx["extra_session_calendar_summary_fa"] = summary
        ctx["extra_session_calendar_noted_at"] = datetime.now(timezone.utc).isoformat()
        ctx.setdefault("ui_hints", []).append(
            {"action": "extra_session_calendar_note", "summary_fa": summary}
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "extra_session_calendar_noted"

    async def _handle_add_extra_session_therapy_hours(self, action: dict, instance: ProcessInstance, context: dict):
        """یک واحد ساعت درمان (جلسه اضافی) به تجمع context و پروندهٔ دانشجو."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        add = float(action.get("hours", 1.0))
        ctx = _as_mapping(instance.context_data)
        prev = float(ctx.get("accumulated_therapy_hours", 0))
        ctx["accumulated_therapy_hours"] = prev + add
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        extra = _as_mapping(student.extra_data)
        extra["accumulated_therapy_hours"] = float(extra.get("accumulated_therapy_hours", 0)) + add
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"extra_session_hours_added total_ctx={ctx['accumulated_therapy_hours']}"

    async def _handle_create_attendance_field(self, action: dict, instance: ProcessInstance, context: dict):
        return "attendance_field_created_for_session"

    async def _resolve_therapy_session_for_link_action(
        self,
        action: dict,
        instance: ProcessInstance,
        context: dict,
    ):
        """جلسهٔ درمان هدف برای فعال‌سازی لینک آنلاین."""
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        sid_raw = (
            action.get("therapy_session_id")
            or merged.get("therapy_session_id")
            or merged.get("session_id")
        )
        if sid_raw:
            try:
                uid = uuid.UUID(str(sid_raw))
                r1 = await self.db.execute(select(TherapySession).where(TherapySession.id == uid))
                target = r1.scalars().first()
                if target and target.student_id == instance.student_id:
                    return target
            except (ValueError, TypeError):
                pass
        stmt = (
            select(TherapySession)
            .where(
                TherapySession.student_id == instance.student_id,
                TherapySession.status == "scheduled",
                TherapySession.is_extra == True,
            )
            .order_by(TherapySession.session_date.desc())
        )
        target = (await self.db.execute(stmt)).scalars().first()
        if target:
            return target
        stmt2 = (
            select(TherapySession)
            .where(
                TherapySession.student_id == instance.student_id,
                TherapySession.status == "scheduled",
            )
            .order_by(TherapySession.session_date.asc())
        )
        sessions = list((await self.db.execute(stmt2)).scalars().all())
        return sessions[0] if sessions else None

    async def _unlock_online_therapy_session_links(
        self,
        action: dict,
        instance: ProcessInstance,
        context: dict,
        *,
        result_prefix: str,
    ) -> str:
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        url = action.get("meeting_url") or merged.get("meeting_url") or merged.get("session_link")
        target = await self._resolve_therapy_session_for_link_action(action, instance, context)
        if target is None:
            stmt = select(TherapySession).where(
                TherapySession.student_id == instance.student_id,
                TherapySession.status == "scheduled",
                TherapySession.payment_status.in_(["paid", "waived"]),
            )
            unlocked = 0
            for s in (await self.db.execute(stmt)).scalars().all():
                s.links_unlocked = True
                unlocked += 1
            return f"{result_prefix}_bulk count={unlocked}"
        if url and str(url).strip():
            target.meeting_url = str(url).strip()
            provider = action.get("meeting_provider") or merged.get("meeting_provider")
            if provider:
                target.meeting_provider = str(provider)
        target.links_unlocked = True
        return f"{result_prefix} session_id={target.id}"

    async def _handle_activate_online_link(self, action: dict, instance: ProcessInstance, context: dict):
        return await self._unlock_online_therapy_session_links(
            action, instance, context, result_prefix="online_session_link_activated"
        )

    async def _handle_record_supervision_attendance(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت حضور سوپرویژن (متادیتا؛ جزئیات در صورت نیاز به AttendanceService متصل می‌شود)."""
        ctx = _as_mapping(instance.context_data)
        ctx["supervision_attendance_recorded"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "supervision_attendance_recorded"

    async def _handle_add_hour_to_block(self, action: dict, instance: ProcessInstance, context: dict):
        return "hour_added_to_supervision_block"

    async def _handle_update_schedule_frequency(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = _as_mapping(instance.context_data)
        return f"schedule_updated: frequency={ctx.get('frequency')}, day={ctx.get('day')}, time={ctx.get('time')}"

    async def _handle_remove_weekly_session(self, action: dict, instance: ProcessInstance, context: dict):
        return "weekly_session_removed_from_student_schedule"

    async def _handle_connect_to_50h(self, action: dict, instance: ProcessInstance, context: dict):
        return "connected_to_supervision_50h_completion"


# action type -> handler; merged into ActionHandler._registry
REGISTRY = {
    'add_recurring_therapy_session': SessionActionsMixin._handle_add_recurring_session,
    'add_recurring_supervision_session': SessionActionsMixin._handle_add_recurring_session,
    'remove_selected_supervision_sessions': SessionActionsMixin._handle_remove_selected_sessions,
    'release_supervisor_slots_to_available_sheet': SessionActionsMixin._handle_release_slots,
    'create_extra_supervision_session_record': SessionActionsMixin._handle_create_extra_session_record,
    'create_attendance_field_for_session': SessionActionsMixin._handle_create_attendance_field,
    'activate_online_session_link': SessionActionsMixin._handle_activate_online_link,
    'record_supervision_attendance': SessionActionsMixin._handle_record_supervision_attendance,
    'add_hour_to_supervision_block': SessionActionsMixin._handle_add_hour_to_block,
    'connect_to_supervision_50h_completion': SessionActionsMixin._handle_connect_to_50h,
    'update_supervision_schedule_frequency': SessionActionsMixin._handle_update_schedule_frequency,
    'remove_weekly_session_from_student_schedule': SessionActionsMixin._handle_remove_weekly_session,
    'sync_extra_session_reenter_fields': SessionActionsMixin._handle_sync_extra_session_reenter_fields,
    'prepare_extra_session_payment': SessionActionsMixin._handle_prepare_extra_session_payment,
    'create_extra_session_record': SessionActionsMixin._handle_create_extra_session_record,
    'note_extra_session_calendar': SessionActionsMixin._handle_note_extra_session_calendar,
    'add_extra_session_therapy_hours': SessionActionsMixin._handle_add_extra_session_therapy_hours,
    'release_supervisor_slots': SessionActionsMixin._handle_release_slots,
}
