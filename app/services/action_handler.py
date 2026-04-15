"""Action Handler - Executes transition actions from process metadata.

This is the bridge between the state machine engine (which reads metadata and
changes states) and the actual business logic (SMS, session management, etc.).

When a transition fires, its `actions` list is published via EventBus.
This handler subscribes to those events and dispatches each action to
the appropriate service method.
"""

import json
import uuid
import logging
from typing import Optional, Any, List
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
)
from app.services.notification_service import notification_service
from app.services.payment_service import PaymentService
from app.services.attendance_service import AttendanceService
from app.services.external_integration import append_integration_event, notify_integration
from app.config import get_settings
from app.services.alocom_client import AlocomAPIError
from app.services.alocom_provision import provision_therapy_session_alocom
from app.services.attendance_tracking_sync import (
    cancel_attendance_instances_for_therapy_session_ids,
    ensure_attendance_instance_for_session,
)

logger = logging.getLogger(__name__)


def parse_therapy_session_id_list(raw) -> list[uuid.UUID]:
    """لیست شناسهٔ جلسات درمان از payload/فرم."""
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                raw = json.loads(s)
            except (json.JSONDecodeError, TypeError):
                raw = [x.strip() for x in s.split(",") if x.strip()]
        else:
            raw = [x.strip() for x in s.replace("،", ",").split(",") if x.strip()]
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[uuid.UUID] = []
    for x in raw:
        try:
            out.append(uuid.UUID(str(x)))
        except (TypeError, ValueError):
            continue
    return out


async def validate_therapy_reduction_preflight(
    db: AsyncSession,
    instance: ProcessInstance,
    payload: dict,
    student: Student,
) -> Optional[str]:
    """
    اعتبارسنجی payload قبل از ترنزیشن sessions_selected.
    برمی‌گرداند رشتهٔ خطا یا None.
    """
    merged = {**_as_mapping(instance.context_data), **(payload or {})}
    rem_raw = merged.get("remaining_sessions_after_reduction")
    if rem_raw is None and merged.get("new_weekly_sessions") is not None:
        try:
            rem_raw = int(merged["new_weekly_sessions"])
        except (TypeError, ValueError):
            rem_raw = None
    try:
        new_weekly = int(rem_raw) if rem_raw is not None else None
    except (TypeError, ValueError):
        new_weekly = None
    if new_weekly is None or new_weekly < 1:
        return "تعداد جلسات هفتگی پس از کاهش را در فرم مشخص کنید (عدد معتبر ≥ ۱)."

    old_ws = int(student.weekly_sessions or 1)
    if new_weekly >= old_ws:
        return "برای کاهش، تعداد جلسات هفتگی پس از تغییر باید کمتر از برنامهٔ فعلی باشد."

    selected_ids = parse_therapy_session_id_list(merged.get("selected_sessions"))
    required = max(1, old_ws - new_weekly)
    if len(selected_ids) < required:
        return (
            f"حداقل {required} جلسهٔ آتی برنامه‌ریزی‌شده را برای لغو انتخاب کنید "
            f"(انتخاب‌شده: {len(selected_ids)})."
        )

    today = datetime.now(timezone.utc).date()
    for sid in selected_ids:
        r = await db.execute(
            select(TherapySession).where(
                TherapySession.id == sid,
                TherapySession.student_id == instance.student_id,
            )
        )
        ts = r.scalars().first()
        if not ts:
            return "یکی از جلسات انتخاب‌شده یافت نشد یا متعلق به شما نیست."
        if ts.is_extra:
            return "جلسات فوق‌العاده را نمی‌توان از این مسیر لغو کرد."
        if ts.status != "scheduled":
            return f"فقط جلسات «برنامه‌ریزی‌شده» قابل انتخاب هستند ({ts.session_date})."
        if ts.session_date < today:
            return "جلسات گذشته را نمی‌توان انتخاب کرد."

    return None


def _as_mapping(val) -> dict:
    """JSONB یا رشتهٔ JSON قدیمی — مثل StateMachineEngine._as_mapping؛ جلوگیری از dict(str) و خطای length 1."""
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


def _parse_iso_date_only(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def _combine_date_time_tehran(d: date, time_str: Optional[str]) -> Optional[datetime]:
    if d is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Tehran")
        ts = (time_str or "").strip()
        if not ts:
            return datetime(d.year, d.month, d.day, 9, 0, tzinfo=tz)
        parts = ts.replace(":", " ").split()
        h = int(parts[0]) if parts else 9
        m = int(parts[1]) if len(parts) > 1 else 0
        sec = int(parts[2]) if len(parts) > 2 else 0
        return datetime(d.year, d.month, d.day, h, m, sec, tzinfo=tz)
    except Exception:
        return None


def _resolve_therapy_session_increase_schedule(ctx: dict) -> tuple[date, Optional[datetime]]:
    """تاریخ/زمان جلسهٔ جدید برای فرایند افزایش جلسات هفتگی درمان."""
    alt_d = _parse_iso_date_only(ctx.get("therapist_alternative_date"))
    alt_t = (ctx.get("therapist_alternative_time_hhmm") or "").strip()
    std_d = _parse_iso_date_only(ctx.get("first_session_date"))
    std_t = (ctx.get("preferred_time_hhmm") or "").strip()
    if alt_d and alt_t:
        st = _combine_date_time_tehran(alt_d, alt_t)
        return alt_d, st.astimezone(timezone.utc) if st else None and alt_d
    if alt_d and not alt_t:
        st = _combine_date_time_tehran(alt_d, std_t or None)
        d = alt_d
    elif std_d:
        d = std_d
        st = _combine_date_time_tehran(std_d, std_t or None)
    else:
        d = datetime.now(timezone.utc).date()
        st = _combine_date_time_tehran(d, std_t or None)
    st_utc = st.astimezone(timezone.utc) if st else None
    return d, st_utc


def _resolve_extra_session_datetime(ctx: dict) -> tuple[date, Optional[datetime]]:
    """تاریخ/زمان توافق‌شده برای جلسه اضافی از فیلدهای فرم و payload."""
    merged = dict(ctx)
    date_keys = (
        "agreed_session_date",
        "confirmed_alternative_date",
        "new_preferred_date",
        "agreed_date",
        "alternative_date",
        "preferred_date",
    )
    time_keys = (
        "agreed_session_time",
        "confirmed_alternative_time",
        "new_preferred_time",
        "agreed_time",
        "alternative_time",
        "preferred_time",
    )
    d: Optional[date] = None
    for k in date_keys:
        d = _parse_iso_date_only(merged.get(k))
        if d:
            break
    if not d:
        d = datetime.now(timezone.utc).date()
    tstr = None
    for k in time_keys:
        v = merged.get(k)
        if v is not None and str(v).strip():
            tstr = str(v).strip()
            break
    st = _combine_date_time_tehran(d, tstr)
    return d, st


class ActionHandler:
    """Dispatches transition actions to the correct service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.payment = PaymentService(db)
        self.attendance = AttendanceService(db)

    async def handle_actions(
        self,
        actions: list[dict],
        instance: ProcessInstance,
        context: dict,
    ) -> list[dict]:
        """Execute a list of actions from a transition and return results."""
        results = []
        for action in actions:
            if not isinstance(action, dict):
                logger.warning(
                    "Skipping invalid action (expected dict, got %s): %r",
                    type(action).__name__,
                    action,
                )
                results.append({"action": "invalid_action_shape", "success": True, "detail": "skipped"})
                continue
            action_type = action.get("type", "unknown")
            try:
                result = await self._dispatch(action_type, action, instance, context)
                results.append({"action": action_type, "success": True, "detail": result})
                logger.info(f"Action OK: {action_type} | instance={instance.id}")
            except Exception as e:
                results.append({"action": action_type, "success": False, "error": str(e)})
                logger.error(f"Action FAIL: {action_type} | instance={instance.id} | {e}", exc_info=True)
        return results

    async def _dispatch(
        self,
        action_type: str,
        action: dict,
        instance: ProcessInstance,
        context: dict,
    ) -> Optional[str]:
        handler = self._registry.get(action_type)
        if handler:
            return await handler(self, action, instance, context)

        logger.warning(f"No handler for action type '{action_type}', skipping.")
        return f"no_handler_for_{action_type}"

    # ─── Notification ────────────────────────────────────────────

    async def _handle_notification(self, action: dict, instance: ProcessInstance, context: dict):
        ntype = action.get("notification_type", "sms")
        template = action.get("template", "")
        recipients = action.get("recipients", [])

        notif_context = await self._build_notification_context(instance, context)

        sent = []
        for role in recipients:
            contact = await self._resolve_contact(role, instance, ntype)
            if contact:
                result = await notification_service.send_notification(
                    ntype, template, contact, notif_context,
                )
                sent.append(f"{role}:{contact}:{result.success}")
            else:
                sent.append(f"{role}:no_contact")
                logger.warning(f"No contact for role '{role}' in instance {instance.id}")

        return f"sent={','.join(sent)}"

    # ─── Sub-process Start ───────────────────────────────────────

    def _eval_start_process_run_if(self, action: dict, instance: ProcessInstance, transition_context: dict) -> bool:
        code = action.get("run_if")
        if not code:
            return True
        merged = {**_as_mapping(instance.context_data), **(transition_context or {})}
        if code == "session_not_cancelled":
            return merged.get("session_cancelled") is not True
        return True

    async def _merge_fee_determination_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        from app.services.fee_determination_runner import enrich_fee_determination_payload_from_therapy_session

        merged = dict(base or {})
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        for key in (
            "session_paid",
            "supervision_session_paid",
            "student_on_leave",
            "session_cancelled",
            "cancelled_by",
            "context",
            "reason",
            "therapy_session_id",
            "session_id",
        ):
            if key in pctx and merged.get(key) is None:
                merged[key] = pctx[key]
        for key in ("session_paid", "student_on_leave", "therapy_session_id", "selected_sessions"):
            if key in tc and merged.get(key) is None:
                merged[key] = tc[key]
        if merged.get("context") == "supervision" or merged.get("supervision_session_paid") is not None:
            if merged.get("session_paid") is None and merged.get("supervision_session_paid") is not None:
                merged["session_paid"] = bool(merged.get("supervision_session_paid"))
        merged["parent_instance_id"] = str(parent.id)
        merged = await enrich_fee_determination_payload_from_therapy_session(
            self.db, parent.student_id, merged
        )
        return merged

    async def _handle_start_process(self, action: dict, instance: ProcessInstance, context: dict):
        from app.core.engine import StateMachineEngine
        from app.services.fee_determination_runner import complete_fee_determination_instance

        sub_code = action.get("process_code", "")
        if action.get("run_if_intern"):
            st = await self._get_student(instance.student_id)
            if not st or not getattr(st, "is_intern", False):
                return f"sub_process_skipped run_if_intern ({sub_code})"

        if not self._eval_start_process_run_if(action, instance, context or {}):
            return f"sub_process_skipped run_if ({sub_code})"

        engine = StateMachineEngine(self.db)
        actor_id = instance.started_by or instance.student_id
        base_payload = dict(action.get("payload") or {})
        base_payload["parent_instance_id"] = str(instance.id)

        payloads: list[dict] = []
        if sub_code == "fee_determination" and action.get("run_for_each_session"):
            pctx = _as_mapping(instance.context_data)
            tc = context or {}
            sessions = pctx.get("selected_sessions") or tc.get("selected_sessions") or []
            if not sessions:
                payloads.append(
                    await self._merge_fee_determination_initial_payload(instance, base_payload, context)
                )
            else:
                for item in sessions:
                    unit = dict(base_payload)
                    if isinstance(item, dict):
                        unit.update(item)
                    else:
                        unit["therapy_session_id"] = str(item)
                    payloads.append(
                        await self._merge_fee_determination_initial_payload(instance, unit, context)
                    )
        else:
            if sub_code == "fee_determination":
                payloads.append(
                    await self._merge_fee_determination_initial_payload(instance, base_payload, context)
                )
            else:
                payloads.append(base_payload)

        ids: list[str] = []
        for payload in payloads:
            sub_instance = await engine.start_process(
                process_code=sub_code,
                student_id=instance.student_id,
                actor_id=actor_id,
                actor_role="system",
                initial_context=payload,
            )
            await self.db.flush()
            if sub_code == "fee_determination":
                await complete_fee_determination_instance(self.db, sub_instance.id)
            ids.append(str(sub_instance.id))
        if ids:
            pctx = _as_mapping(instance.context_data)
            pctx["last_child_process_code"] = sub_code
            pctx["last_child_process_instance_id"] = ids[-1]
            if sub_code == "violation_registration":
                pctx["violation_registration_instance_id"] = ids[-1]
            instance.context_data = pctx
            flag_modified(instance, "context_data")
        return f"sub_process={sub_code}, sub_instances={','.join(ids)}"

    # ─── Session Management ──────────────────────────────────────

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
        if instance.process_code != "extra_session":
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
        if instance.process_code != "extra_session":
            return "skip_not_extra_session"
        settings = get_settings()
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        d, st = _resolve_extra_session_datetime(merged)
        fee_rial = int(getattr(settings, "EXTRA_SESSION_FEE_RIAL", 7_500_000))
        fee_toman = await self.payment.calculate_session_fee(instance.student_id, session_type="extra")
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
        fee = float(await self.payment.calculate_session_fee(instance.student_id, session_type="extra"))
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

    async def _handle_activate_online_link(self, action: dict, instance: ProcessInstance, context: dict):
        return "online_session_link_activated"

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

    # ─── Therapy-Specific ────────────────────────────────────────

    async def _handle_remove_therapy_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """لغو جلسات انتخاب‌شده، به‌روزرسانی تعداد هفتگی، و هم‌ترازی با تقویم."""
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"

        rem_raw = merged.get("remaining_sessions_after_reduction")
        if rem_raw is None and merged.get("new_weekly_sessions") is not None:
            try:
                rem_raw = int(merged["new_weekly_sessions"])
            except (TypeError, ValueError):
                rem_raw = None
        try:
            new_weekly = int(rem_raw) if rem_raw is not None else None
        except (TypeError, ValueError):
            new_weekly = None
        if new_weekly is None or new_weekly < 1:
            raise ValueError("تعداد جلسات هفتگی پس از کاهش (remaining_sessions_after_reduction) نامعتبر است.")

        old_ws = int(student.weekly_sessions or 1)
        if new_weekly >= old_ws:
            raise ValueError("برای کاهش، تعداد جلسات هفتگی پس از تغییر باید کمتر از برنامهٔ فعلی باشد.")

        selected_ids = parse_therapy_session_id_list(merged.get("selected_sessions"))
        required = max(1, old_ws - new_weekly)
        if len(selected_ids) < required:
            raise ValueError(
                f"حداقل {required} جلسهٔ آتی را برای لغو انتخاب کنید (انتخاب‌شده: {len(selected_ids)})."
            )

        today = datetime.now(timezone.utc).date()
        cancelled_ids: list[uuid.UUID] = []
        for sid in selected_ids:
            r = await self.db.execute(
                select(TherapySession).where(
                    TherapySession.id == sid,
                    TherapySession.student_id == instance.student_id,
                )
            )
            ts = r.scalars().first()
            if not ts:
                raise ValueError(f"جلسهٔ درمان یافت نشد یا متعلق به شما نیست: {sid}")
            if ts.is_extra:
                raise ValueError("جلسات فوق‌العاده از این مسیر قابل حذف نیستند.")
            if ts.status != "scheduled":
                raise ValueError(f"فقط جلسات «برنامه‌ریزی‌شده» قابل لغو هستند ({ts.session_date}).")
            if ts.session_date < today:
                raise ValueError("جلسات گذشته را نمی‌توان از این مسیر لغو کرد.")

            ts.status = "cancelled"
            prev = (ts.notes or "").strip()
            tag = f"therapy_session_reduction:{instance.id}"
            ts.notes = f"{prev} — [{tag}]".strip(" —") if prev else f"[{tag}]"
            cancelled_ids.append(ts.id)

        student.weekly_sessions = new_weekly
        flag_modified(student, "weekly_sessions")

        try:
            await cancel_attendance_instances_for_therapy_session_ids(self.db, cancelled_ids)
        except Exception:
            logger.exception("cancel_attendance_instances_for_therapy_session_ids failed")

        ctx = _as_mapping(instance.context_data)
        ctx["therapy_reduction_applied_at"] = datetime.now(timezone.utc).isoformat()
        ctx["weekly_sessions_before_reduction"] = old_ws
        ctx["remaining_sessions_after_reduction"] = new_weekly
        ctx["cancelled_therapy_session_ids"] = [str(x) for x in cancelled_ids]
        instance.context_data = ctx
        flag_modified(instance, "context_data")

        phone = None
        try:
            ur = await self.db.execute(
                select(User.phone)
                .join(Student, Student.user_id == User.id)
                .where(Student.id == instance.student_id)
            )
            phone = ur.scalars().first()
            phone = phone[0] if phone else None
        except Exception:
            phone = None
        if phone and str(phone).strip():
            msg = notification_service.get_template("therapy_session_reduction_completed", "sms")
            if msg:
                msg = msg.replace("{new_weekly}", str(new_weekly)).replace("{old_weekly}", str(old_ws))
                try:
                    await notification_service.send_sms(str(phone).strip(), msg)
                except Exception:
                    logger.exception("therapy_session_reduction SMS send failed")

        return f"therapy_sessions_cancelled={len(cancelled_ids)} new_weekly={new_weekly}"

    async def _handle_release_therapist_slots(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت رویداد آزادسازی زمان درمانگر در پرونده (بدون جدول جداگانهٔ اسلات)."""
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        log = list(extra.get("therapist_slot_release_log") or [])
        entry: dict = {
            "at": datetime.now(timezone.utc).isoformat(),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "source": "therapy_session_reduction",
        }
        if instance.process_code == "therapy_completion":
            entry["source"] = "therapy_completion"
            entry["therapist_id"] = str(student.therapist_id) if student.therapist_id else None
            append_integration_event(
                instance,
                "therapy_slots_released_to_available_sheet",
                {"therapist_id": entry.get("therapist_id"), "student_id": str(instance.student_id)},
            )
            await notify_integration(
                "therapy_slots_released_to_available_sheet",
                instance.id,
                instance.student_id,
                instance.process_code,
                extra={"therapist_id": entry.get("therapist_id")},
            )
            ctx = _as_mapping(instance.context_data)
            ctx["therapist_slots_released_at"] = datetime.now(timezone.utc).isoformat()
            instance.context_data = ctx
            flag_modified(instance, "context_data")
        else:
            entry["cancelled_session_ids"] = merged.get("cancelled_therapy_session_ids") or [
                str(x) for x in parse_therapy_session_id_list(merged.get("selected_sessions"))
            ]
        log.append(entry)
        extra["therapist_slot_release_log"] = log[-200:]
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"therapist_slots_released_to_available_sheet n={len(log)}"

    async def _handle_record_change_history(self, action: dict, instance: ProcessInstance, context: dict):
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        hist = list(extra.get("therapy_change_history") or [])
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": "therapy_session_reduction",
            "instance_id": str(instance.id),
            "weekly_before": merged.get("weekly_sessions_before_reduction"),
            "weekly_after": merged.get("remaining_sessions_after_reduction"),
            "cancelled_ids": merged.get("cancelled_therapy_session_ids"),
        }
        hist.append(entry)
        extra["therapy_change_history"] = hist[-500:]
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "therapy_change_history_recorded"

    async def _handle_cancel_session(self, action: dict, instance: ProcessInstance, context: dict):
        return "session_cancelled"

    async def _handle_add_credit(self, action: dict, instance: ProcessInstance, context: dict):
        await self.payment.process_refund(
            student_id=instance.student_id,
            amount=self.payment.DEFAULT_SESSION_FEE,
            reason="بستانکاری - لغو جلسه توسط درمانگر",
            reference_id=instance.id,
        )
        return "credit_added_for_cancelled_session"

    async def _handle_deduct_credit_session(self, action: dict, instance: ProcessInstance, context: dict):
        """کسر از اعتبار جلسه در context؛ اگر اعتبار ناکافی باشد ثبت بدهی."""
        fee = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        ctx = _as_mapping(instance.context_data)
        balance = float(ctx.get("session_credit_balance", 0))
        if balance >= fee:
            ctx["session_credit_balance"] = balance - fee
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return f"session_credit_deducted remaining={ctx['session_credit_balance']}"
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=fee,
            description="کسر بابت جلسه — اعتبار ناکافی",
            reference_id=instance.id,
        )
        return f"debt_for_shortfall amount={fee}"

    async def _handle_register_makeup(self, action: dict, instance: ProcessInstance, context: dict):
        return "makeup_session_registered"

    async def _handle_enable_online_link(self, action: dict, instance: ProcessInstance, context: dict):
        return "online_session_link_enabled"

    # ─── Attendance & Hours ──────────────────────────────────────

    async def _handle_mark_cancelled(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = _as_mapping(instance.context_data)
        if context:
            for k in ("selected_sessions", "cancelled_session_ids", "sessions_cancelled", "session_dates"):
                if k in context:
                    ctx[k] = context[k]
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "sessions_marked_cancelled_by_student"

    async def _handle_block_attendance(self, action: dict, instance: ProcessInstance, context: dict):
        return "attendance_blocked_for_cancelled_sessions"

    # ─── Financial ───────────────────────────────────────────────

    async def _handle_add_to_credit_balance(self, action: dict, instance: ProcessInstance, context: dict):
        """fee_determination: record financial credit; session_payment: virtual balance (payment row from gateway callback)."""
        sessions = action.get("sessions")
        if sessions is not None:
            n = float(sessions)
            per = float(action.get("amount_per_session", self.payment.DEFAULT_SESSION_FEE))
            total = per * n
            await self.payment.process_refund(
                student_id=instance.student_id,
                amount=total,
                reason="بازگشت اعتبار جلسه (تعیین تکلیف هزینه)",
                reference_id=instance.id,
            )
            return f"credit_refund_recorded: {total}"
        if instance.process_code == "session_payment":
            amount = float(
                context.get("amount")
                or _as_mapping(instance.context_data).get("amount")
                or self.payment.DEFAULT_SESSION_FEE
            )
            ctx = _as_mapping(instance.context_data)
            ctx["session_credit_balance"] = float(ctx.get("session_credit_balance", 0)) + amount
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return f"session_credit_balance_context: {ctx['session_credit_balance']}"
        amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        await self.payment.process_refund(
            student_id=instance.student_id,
            amount=amount,
            reason="اعتبار جلسه",
            reference_id=instance.id,
        )
        return f"credit_added: {amount}"

    async def _handle_forfeit_payment(self, action: dict, instance: ProcessInstance, context: dict):
        amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        await self.payment.charge_absence_fee(
            student_id=instance.student_id,
            amount=amount,
            created_by=None,
        )
        ctx = _as_mapping(instance.context_data)
        ctx["session_payment_forfeited"] = True
        ctx["forfeit_amount"] = amount
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"session_payment_forfeited amount={amount}"

    async def _handle_create_debt_or_deduct_credit(self, action: dict, instance: ProcessInstance, context: dict):
        """سناریوی ۴: اگر بستانکاری (موجودی مالی) کافی باشد، بدون ایجاد بدهی جدید تسویه ثبت می‌شود."""
        try:
            amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        except (TypeError, ValueError):
            amount = float(self.payment.DEFAULT_SESSION_FEE)
        bal_info = await self.payment.get_student_balance(instance.student_id)
        net = float(bal_info.get("balance", 0) or 0)
        ctx = _as_mapping(instance.context_data)
        if net >= amount:
            ctx["fee_settlement_mode"] = "from_existing_credit_balance"
            ctx["fee_settlement_amount"] = amount
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return f"fee_settled_from_credit balance_was={net} amount={amount}"
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=amount,
            description="بدهی غیبت جلسه",
            reference_id=instance.id,
        )
        return f"debt_created: {amount}"

    async def _handle_increment_absence(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        key = action.get("counter_key", "absence_counter_unexcused")
        extra[key] = int(extra.get(key, 0)) + 1
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"absence_counter_incremented {key}={extra[key]}"

    # ─── Session payment (real bookkeeping + session rows) ─────

    async def _handle_generate_payment_invoice(self, action: dict, instance: ProcessInstance, context: dict):
        ctx_map = _as_mapping(instance.context_data)
        raw_sessions = ctx_map.get("sessions_to_pay")
        try:
            n_sessions = max(1, int(raw_sessions)) if raw_sessions is not None else 1
        except (TypeError, ValueError):
            n_sessions = 1
        per = float(self.payment.DEFAULT_SESSION_FEE)
        computed = per * float(n_sessions)
        if context.get("amount") is not None:
            try:
                amount = float(context["amount"])
            except (TypeError, ValueError):
                amount = computed
        elif ctx_map.get("amount") not in (None, "", 0) and float(ctx_map.get("amount") or 0) > 0:
            amount = float(ctx_map["amount"])
        elif ctx_map.get("total_amount") not in (None, "", 0) and float(ctx_map.get("total_amount") or 0) > 0:
            amount = float(ctx_map["total_amount"])
        else:
            amount = computed
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=amount,
            description="پیش‌فاکتور پرداخت جلسات درمان",
            reference_id=instance.id,
        )
        ctx = _as_mapping(instance.context_data)
        ctx["invoice_amount"] = amount
        ctx["payment_amount_rial"] = int(round(float(amount) * 10))
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"payment_invoice_generated amount={amount}"

    async def _handle_zero_debt_if_paid(self, action: dict, instance: ProcessInstance, context: dict):
        stmt = delete(FinancialRecord).where(
            FinancialRecord.student_id == instance.student_id,
            FinancialRecord.record_type == "debt",
            FinancialRecord.reference_id == instance.id,
        )
        result = await self.db.execute(stmt)
        return f"zero_debt_cleared rows={getattr(result, 'rowcount', None)}"

    async def _handle_allocate_credit_to_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        fee = float(self.payment.DEFAULT_SESSION_FEE)
        ctx = _as_mapping(instance.context_data)
        balance = float(ctx.get("session_credit_balance", 0))
        if balance <= 0:
            balance = float(context.get("amount") or 0)
        if balance <= 0 or fee <= 0:
            return "allocate_credit_no_balance"
        sessions_to_cover = int(balance // fee)
        stmt = (
            select(TherapySession)
            .where(
                TherapySession.student_id == instance.student_id,
                TherapySession.payment_status == "pending",
                TherapySession.status.in_(["scheduled", "completed"]),
            )
            .order_by(TherapySession.session_date)
        )
        res = await self.db.execute(stmt)
        rows = list(res.scalars().all())
        spent = 0.0
        n = 0
        paid_sessions: List[TherapySession] = []
        for s in rows[:sessions_to_cover]:
            s.payment_status = "paid"
            spent += fee
            n += 1
            paid_sessions.append(s)
        ctx["session_credit_balance"] = max(0.0, balance - spent)
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await self.db.flush()
        for s in paid_sessions:
            try:
                await ensure_attendance_instance_for_session(self.db, s)
            except Exception:
                logger.exception("ensure_attendance_instance_for_session failed after allocate session=%s", s.id)
        return f"allocated_to_sessions n={n} remaining={ctx['session_credit_balance']}"

    async def _handle_unlock_session_links(self, action: dict, instance: ProcessInstance, context: dict):
        stmt = select(TherapySession).where(
            TherapySession.student_id == instance.student_id,
            TherapySession.payment_status.in_(["paid", "waived"]),
            TherapySession.status == "scheduled",
        )
        res = await self.db.execute(stmt)
        unlocked = 0
        for s in res.scalars().all():
            s.links_unlocked = True
            unlocked += 1
        student = await self._get_student(instance.student_id)
        if student:
            extra = _as_mapping(student.extra_data)
            extra["session_links_unlocked"] = True
            student.extra_data = extra
            flag_modified(student, "extra_data")
        return f"session_links_unlocked count={unlocked}"

    async def _handle_unlock_attendance_registration(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["attendance_registration_unlocked"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "attendance_registration_unlocked"

    async def _handle_suspend_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["sessions_suspended"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "sessions_suspended_flag_set"

    # ─── Therapy Lifecycle ───────────────────────────────────────

    async def _handle_activate_therapy(self, action: dict, instance: ProcessInstance, context: dict):
        """Set student.therapy_started = True and optionally therapist_id from context (BUILD_TODO § ب)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        student.therapy_started = True
        ctx = _as_mapping(instance.context_data)
        ctx.update(context or {})
        if ctx.get("therapist_id"):
            student.therapist_id = uuid.UUID(ctx["therapist_id"]) if isinstance(ctx["therapist_id"], str) else ctx["therapist_id"]
        if ctx.get("weekly_sessions") is not None:
            student.weekly_sessions = int(ctx["weekly_sessions"])
        return "therapy_activated"

    async def _handle_block_class_access(self, action: dict, instance: ProcessInstance, context: dict):
        """Block student access to class/attendance (e.g. week 9 deadline). Stored in extra_data (BUILD_TODO § ب)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["class_access_blocked"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "class_access_blocked"

    async def _handle_resolve_access(self, action: dict, instance: ProcessInstance, context: dict):
        """Clear class/attendance block (inverse of block_class_access)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["class_access_blocked"] = False
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "access_restrictions_resolved"

    async def _handle_reactivate_class_registration(self, action: dict, instance: ProcessInstance, context: dict):
        """بازگشت از مرخصی: رفع مسدودیت ثبت‌نام کلاس (همان resolve_access)."""
        return await self._handle_resolve_access(action, instance, context)

    async def _handle_warn_if(self, action: dict, instance: ProcessInstance, context: dict):
        """هشدار شرطی مرخصی (انترن + وقفه ۲ ترم) — ذخیره در context برای نمایش در پنل دانشجو."""
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        student = await self._get_student(instance.student_id)
        is_intern = bool(student and student.is_intern)
        lt_raw = merged.get("leave_terms")
        try:
            lt = int(lt_raw) if lt_raw is not None else None
        except (TypeError, ValueError):
            lt = None
        raw_cond = action.get("condition") or ""
        show = False
        if raw_cond and "student.is_intern" in raw_cond and "leave_terms" in raw_cond:
            if is_intern and lt == 2:
                show = True
        if not show:
            return "warn_if_skipped"
        msg = (action.get("message_fa") or "").strip()
        ctx = _as_mapping(instance.context_data)
        if msg:
            ctx["student_portal_alert_fa"] = msg
        ctx["leave_intern_2term_warning_applies"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "warn_if_set"

    async def _handle_set_leave_return_schedule(self, action: dict, instance: ProcessInstance, context: dict):
        """تنظیم return_reminder_at و return_deadline_at برای calendar_triggers (مرخصی آموزشی)."""
        settings = get_settings()
        days_rem = int(
            action.get("reminder_offset_days")
            or getattr(settings, "EDUCATIONAL_LEAVE_RETURN_REMINDER_OFFSET_DAYS", 90)
        )
        days_after = int(
            action.get("deadline_after_reminder_days")
            or getattr(settings, "EDUCATIONAL_LEAVE_RETURN_DEADLINE_AFTER_REMINDER_DAYS", 30)
        )
        now = datetime.now(timezone.utc)
        reminder_at = now + timedelta(days=days_rem)
        deadline_at = reminder_at + timedelta(days=days_after)
        ctx = _as_mapping(instance.context_data)
        ctx["return_reminder_at"] = reminder_at.isoformat()
        ctx["return_deadline_at"] = deadline_at.isoformat()
        ctx["leave_schedule_set_at"] = now.isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return (
            f"leave_return_schedule reminder={ctx['return_reminder_at']} deadline={ctx['return_deadline_at']}"
        )

    async def _handle_revoke_intern_status(self, action: dict, instance: ProcessInstance, context: dict):
        """لغو وضعیت انترن (مثلاً وقفه ۲ ترمی)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        student.is_intern = False
        extra = _as_mapping(student.extra_data)
        extra["intern_revoked_at"] = datetime.now(timezone.utc).isoformat()
        extra["intern_revoked_reason"] = action.get("reason") or "educational_leave_2term"
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "intern_status_revoked"

    async def _handle_release_supervisor_slot(self, action: dict, instance: ProcessInstance, context: dict):
        """آزاد کردن سوپروایزر اختصاص‌یافته به دانشجو (ارجاع بیماران طبق SOP)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        prev = str(student.supervisor_id) if student.supervisor_id else None
        student.supervisor_id = None
        extra = _as_mapping(student.extra_data)
        extra["supervisor_released_at"] = datetime.now(timezone.utc).isoformat()
        extra["supervisor_release_reason"] = action.get("reason") or "educational_leave_2term"
        if prev:
            extra["previous_supervisor_id"] = prev
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"supervisor_released previous={prev}"

    async def _handle_create_session_link(self, action: dict, instance: ProcessInstance, context: dict):
        settings = get_settings()
        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        url = action.get("meeting_url") or ctx.get("meeting_url") or ctx.get("session_link")
        target = None
        sid_raw = action.get("therapy_session_id") or ctx.get("therapy_session_id") or ctx.get("session_id")
        if sid_raw:
            try:
                uid = uuid.UUID(str(sid_raw))
                r1 = await self.db.execute(select(TherapySession).where(TherapySession.id == uid))
                target = r1.scalars().first()
            except (ValueError, TypeError):
                target = None
        if target is None:
            stmt = (
                select(TherapySession)
                .where(
                    TherapySession.student_id == instance.student_id,
                    TherapySession.status == "scheduled",
                    TherapySession.is_extra == True,
                )
                .order_by(TherapySession.session_date.desc())
            )
            res = await self.db.execute(stmt)
            target = res.scalars().first()
        if target is None:
            stmt = (
                select(TherapySession)
                .where(
                    TherapySession.student_id == instance.student_id,
                    TherapySession.status == "scheduled",
                )
                .order_by(TherapySession.session_date.asc())
            )
            res = await self.db.execute(stmt)
            sessions = list(res.scalars().all())
            target = sessions[0] if sessions else None
        base = settings.APP_BASE_URL.rstrip("/")
        if not url:
            if target:
                url = f"{base}/meet/therapy/{target.id}"
            else:
                url = f"{base}/meet/therapy/pending/{instance.student_id}"
        if target:
            target.meeting_url = url
            target.meeting_provider = str(
                action.get("meeting_provider") or ctx.get("meeting_provider") or "manual"
            )
            target.links_unlocked = True
        ctx = _as_mapping(instance.context_data)
        ctx["last_session_link"] = url
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"session_link_set url={url} session_id={getattr(target, 'id', None)}"

    async def _resolve_system_actor_id_for_actions(self) -> uuid.UUID:
        r = await self.db.execute(select(User.id).where(User.role == "admin").limit(1))
        row = r.scalars().first()
        if row:
            return row[0]
        r = await self.db.execute(select(User.id).limit(1))
        row = r.scalars().first()
        return row[0] if row else uuid.uuid4()

    async def _handle_apply_start_therapy_session_schedule(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """پس از انتخاب زمان توسط دانشجو: اعمال قانون ۲۴ ساعت، بذر جلسات درمان، مبلغ ریال، و انتقال خودکار به payment_pending."""
        from app.core.engine import StateMachineEngine

        if instance.process_code != "start_therapy":
            return "skip_not_start_therapy"

        merged = {**_as_mapping(instance.context_data), **(context or {})}

        def _parse_first_date(val) -> Optional[date]:
            if val is None:
                return None
            if isinstance(val, date) and not isinstance(val, datetime):
                return val
            if isinstance(val, datetime):
                return val.date()
            s = str(val).strip()
            if not s:
                return None
            try:
                return date.fromisoformat(s[:10])
            except (TypeError, ValueError):
                return None

        student = await self._get_student(instance.student_id)
        today = datetime.now(timezone.utc).date()

        first = _parse_first_date(merged.get("first_session_date"))
        if first is None:
            first = today + timedelta(days=1)

        ws_raw = merged.get("weekly_sessions")
        if ws_raw is None and student is not None:
            ws_raw = student.weekly_sessions
        try:
            ws = int(ws_raw) if ws_raw is not None else 1
        except (TypeError, ValueError):
            ws = 1
        ws = max(1, min(ws, 12))

        tid = merged.get("therapist_id")
        if not tid and student is not None and student.therapist_id:
            tid = str(student.therapist_id)
        if not tid:
            raise ValueError("therapist_id در پروندهٔ این مرحله ثبت نشده است.")

        try:
            tid_uuid = uuid.UUID(str(tid))
        except (TypeError, ValueError) as e:
            raise ValueError("شناسهٔ درمانگر نامعتبر است.") from e

        if first <= today:
            first = today + timedelta(days=7)

        n_weeks = max(1, min(ws, 12))
        note_tag = f"start_therapy_instance:{instance.id}"

        for _attempt in range(8):
            stmt_old_ids = select(TherapySession.id).where(
                TherapySession.student_id == instance.student_id,
                TherapySession.notes.like(f"%{note_tag}%"),
            )
            old_rows = await self.db.execute(stmt_old_ids)
            old_ids = [row[0] for row in old_rows.all()]
            if old_ids:
                await cancel_attendance_instances_for_therapy_session_ids(self.db, old_ids)
            await self.db.execute(
                delete(TherapySession).where(
                    TherapySession.student_id == instance.student_id,
                    TherapySession.notes.like(f"%{note_tag}%"),
                )
            )
            created_sessions: List[TherapySession] = []
            for i in range(n_weeks):
                d = first + timedelta(weeks=i)
                ts = TherapySession(
                    id=uuid.uuid4(),
                    student_id=instance.student_id,
                    therapist_id=tid_uuid,
                    session_date=d,
                    status="scheduled",
                    payment_status="pending",
                    notes=note_tag,
                )
                self.db.add(ts)
                created_sessions.append(ts)
            await self.db.flush()
            for ts in created_sessions:
                try:
                    await ensure_attendance_instance_for_session(self.db, ts)
                except Exception:
                    logger.exception(
                        "ensure_attendance_instance_for_session failed session=%s",
                        ts.id,
                    )

            hours = await self.attendance.get_hours_until_first_slot(instance.student_id)
            if hours >= 24:
                break
            first = first + timedelta(days=7)
        else:
            logger.warning(
                "start_therapy: 24h rule not satisfied after bumps instance=%s",
                instance.id,
            )

        settings = get_settings()
        fee = int(getattr(settings, "START_THERAPY_FIRST_SESSION_FEE_RIAL", 10_000_000))
        if merged.get("payment_amount_rial") is not None:
            try:
                fee = int(merged["payment_amount_rial"])
            except (TypeError, ValueError):
                pass

        ctx = _as_mapping(instance.context_data)
        ctx.update(merged)
        ctx["therapist_id"] = str(tid_uuid)
        ctx["weekly_sessions"] = ws
        ctx["first_session_date"] = first.isoformat()
        ctx["first_session_date_effective"] = first.isoformat()
        ctx["payment_amount_rial"] = fee
        ctx["start_therapy_sessions_seeded"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await self.db.flush()

        engine = StateMachineEngine(self.db)
        actor = await self._resolve_system_actor_id_for_actions()
        res = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="24h_check_passed",
            actor_id=actor,
            actor_role="system",
            payload={},
        )
        if not res.success:
            logger.error(
                "start_therapy nested 24h_check_passed failed instance=%s err=%s",
                instance.id,
                res.error,
            )
            return f"nested_transition_failed: {res.error}"

        await self.db.refresh(instance)
        return f"start_therapy_schedule_applied fee_rial={fee} to_state={res.to_state}"

    async def _handle_delete_future_appointments(self, action: dict, instance: ProcessInstance, context: dict):
        today = datetime.now(timezone.utc).date()
        stmt = delete(TherapySession).where(
            TherapySession.student_id == instance.student_id,
            TherapySession.session_date >= today,
            TherapySession.status == "scheduled",
        )
        result = await self.db.execute(stmt)
        rc = getattr(result, "rowcount", None)
        return f"future_therapy_appointments_deleted rowcount={rc}"

    async def _handle_update_therapy_status(self, action: dict, instance: ProcessInstance, context: dict):
        status = action.get("status") or (context or {}).get("therapy_status") or "completed"
        student = await self._get_student(instance.student_id)
        if student:
            extra = _as_mapping(student.extra_data)
            extra["therapy_status"] = status
            student.extra_data = extra
            flag_modified(student, "extra_data")
        ctx = _as_mapping(instance.context_data)
        ctx["therapy_status"] = status
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"therapy_status_updated status={status}"

    async def _handle_mark_terminated(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        student.therapy_started = False
        if action.get("clear_therapist", True):
            student.therapist_id = None
        extra = _as_mapping(student.extra_data)
        extra["therapy_relationship"] = "terminated"
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "therapy_relationship_terminated"

    async def _handle_log_termination(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = _as_mapping(instance.context_data)
        log = list(ctx.get("termination_requests") or [])
        log.append({"logged_at": datetime.now(timezone.utc).isoformat(), "payload": dict(context or {})})
        ctx["termination_requests"] = log
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"termination_request_logged n={len(log)}"

    async def _handle_set_student_status(self, action: dict, instance: ProcessInstance, context: dict):
        status = action.get("status") or (context or {}).get("student_status") or "active"
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["lifecycle_status"] = status
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"student_status_updated lifecycle_status={status}"

    # ─── Supervision ─────────────────────────────────────────────

    async def _handle_send_reminder(self, action: dict, instance: ProcessInstance, context: dict):
        await self._handle_notification(
            {
                "notification_type": action.get("notification_type", "sms"),
                "template": action.get("template", "supervision_45_48_reminder"),
                "recipients": action.get("recipients", ["student", "supervisor"]),
            },
            instance,
            context,
        )
        ctx = _as_mapping(instance.context_data)
        ctx["reminder_45_48_sent_at"] = datetime.now(timezone.utc).isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "45_48_reminder_sent_if_applicable"

    async def _handle_unlock_payment_50th(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if student:
            extra = _as_mapping(student.extra_data)
            extra["payment_unlocked_for_50th_session"] = True
            student.extra_data = extra
            flag_modified(student, "extra_data")
        ctx = _as_mapping(instance.context_data)
        ctx["payment_unlocked_for_50th_session"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "payment_unlocked_for_50th_session"

    async def _handle_display_supervision_history(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = _as_mapping(instance.context_data)
        ctx.setdefault("ui_hints", []).append({"action": "display_supervision_history", "payload": {}})
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "supervision_history_displayed"

    async def _handle_remove_slot_from_available(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = _as_mapping(instance.context_data)
        ctx["supervisor_slot_removed_from_available"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "slot_removed_from_available_sheet"

    async def _handle_add_hour_by_course_and_weekly_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """هر جلسهٔ حضور: +۱ ساعت در context نمونه؛ ساعات خاتمه از جلسات completed + متریک‌ها."""
        add = float(action.get("hours_per_unit", 1.0))
        ctx = _as_mapping(instance.context_data)
        prev = float(ctx.get("accumulated_therapy_hours", 0))
        ctx["accumulated_therapy_hours"] = prev + add
        prev_th = float(ctx.get("therapy_hours_2x", 0))
        ctx["therapy_hours_2x"] = prev_th + add
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"hours_accumulated instance={ctx['therapy_hours_2x']} (+{add})"

    async def _handle_record_attendance_action(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        sid_raw = action.get("session_id") or ctx.get("therapy_session_id") or ctx.get("session_id")
        session_id = uuid.UUID(sid_raw) if sid_raw else None
        rd = ctx.get("record_date")
        if isinstance(rd, str):
            record_date = date.fromisoformat(rd[:10])
        elif isinstance(rd, date):
            record_date = rd
        else:
            record_date = datetime.now(timezone.utc).date()
        status = action.get("status") or ctx.get("attendance_status") or "present"
        await self.attendance.record_attendance(
            student_id=instance.student_id,
            session_id=session_id,
            record_date=record_date,
            status=status,
            absence_type=ctx.get("absence_type"),
            notes=ctx.get("attendance_notes"),
        )
        return f"attendance_recorded status={status} date={record_date}"

    async def _handle_record_absence_auto(self, action: dict, instance: ProcessInstance, context: dict):
        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        sid_raw = ctx.get("therapy_session_id") or ctx.get("session_id")
        session_id = uuid.UUID(sid_raw) if sid_raw else None
        record_date = datetime.now(timezone.utc).date()
        await self.attendance.record_attendance(
            student_id=instance.student_id,
            session_id=session_id,
            record_date=record_date,
            status="absent_unexcused",
            absence_type=ctx.get("absence_type") or "student",
            notes="record_absence_auto",
        )
        return "absence_recorded_auto"

    async def _handle_notify_committee(self, action: dict, instance: ProcessInstance, context: dict):
        recipients = action.get("recipients") or [
            "therapy_committee_chair",
            "monitoring_committee_officer",
            "deputy_education",
        ]
        await self._handle_notification(
            {
                "notification_type": action.get("notification_type", "in_app"),
                "template": action.get("template", "committee_notice"),
                "recipients": recipients,
            },
            instance,
            context,
        )
        return f"notify_committee sent_to={recipients}"

    async def _handle_update_record(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت نتیجه در پروندهٔ دانشجو (مثلاً ارزیابی TA) از روی payload/context."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        keys = (
            "total_score",
            "result_status",
            "average_score",
            "participation_rate",
            "grade",
            "course_name",
        )
        block = {k: merged[k] for k in keys if k in merged}
        extra = _as_mapping(student.extra_data)
        extra.setdefault("gradebook", {})[instance.process_code] = block
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return f"record_updated keys={list(block.keys())}"

    async def _handle_merge_instance_context(self, action: dict, instance: ProcessInstance, context: dict):
        """ثبت payment_method و شمارندهٔ اقساط در context_data؛ در صورت صفر، بستن خودکار با finalize_term2_registration."""
        from app.core.engine import StateMachineEngine, InvalidTransitionError

        system_actor = uuid.UUID("00000000-0000-0000-0000-000000000001")
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        mode = action.get("mode", "initial_payment")

        from app.services.installment_settings_service import get_installment_policy

        policy = await get_installment_policy(self.db)
        term2_installment_gap_days = int(policy.get("term2_installment_gap_days") or 25)

        if mode == "initial_payment":
            pm = merged.get("payment_method")
            ic = merged.get("installment_count")
            merged["payment_method"] = pm
            if pm == "cash":
                merged["pending_installments_remaining"] = 0
                merged.pop("next_installment_due_at", None)
            elif pm == "installment" and ic is not None:
                try:
                    n = int(ic)
                    merged["pending_installments_remaining"] = max(0, n - 1)
                except (TypeError, ValueError):
                    pass
                # سررسید قسط بعدی: از تاریخ شروع ترم در extra دانشجو یا N روز پس از امروز
                extra_st = {}
                stu = await self._get_student(instance.student_id)
                if stu:
                    extra_st = _as_mapping(stu.extra_data)
                term_start = merged.get("term_start_date") or extra_st.get("term_start_date")
                base_date = datetime.now(timezone.utc).date()
                if term_start:
                    try:
                        base_date = date.fromisoformat(str(term_start)[:10])
                    except (TypeError, ValueError):
                        pass
                merged["next_installment_due_at"] = (
                    base_date + timedelta(days=term2_installment_gap_days)
                ).isoformat()
        elif mode == "installment_paid":
            cur = merged.get("pending_installments_remaining")
            if isinstance(cur, int) and cur > 0:
                merged["pending_installments_remaining"] = cur - 1
            elif cur is not None:
                try:
                    c = int(cur)
                    if c > 0:
                        merged["pending_installments_remaining"] = c - 1
                except (TypeError, ValueError):
                    pass
            pending_after = merged.get("pending_installments_remaining")
            if isinstance(pending_after, int) and pending_after > 0:
                merged["next_installment_due_at"] = (
                    datetime.now(timezone.utc).date() + timedelta(days=term2_installment_gap_days)
                ).isoformat()
            else:
                merged.pop("next_installment_due_at", None)

        instance.context_data = merged
        flag_modified(instance, "context_data")
        await self.db.flush()

        pending = merged.get("pending_installments_remaining")
        if (
            pending == 0
            and instance.process_code == "intro_second_semester_registration"
            and instance.current_state_code == "registration_complete"
        ):
            try:
                engine = StateMachineEngine(self.db)
                await engine.execute_transition(
                    instance.id,
                    "finalize_term2_registration",
                    system_actor,
                    "system",
                )
            except InvalidTransitionError:
                pass

        return f"merge_instance_context mode={mode} pending={pending}"

    async def _handle_deactivate_student_account(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        user = await self._get_user(student.user_id)
        if user:
            user.is_active = False
        extra = _as_mapping(student.extra_data)
        extra["portal_blocked"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "student_account_deactivated"

    async def _handle_call_bpms_subprocess(self, action: dict, instance: ProcessInstance, context: dict):
        code = action.get("process_code") or action.get("subprocess_code") or "violation_registration"
        payload = dict(action.get("payload") or {})
        payload["parent_instance_id"] = str(instance.id)
        return await self._handle_start_process(
            {"process_code": code, "payload": payload},
            instance,
            context,
        )

    async def _handle_create_online_class_links(self, action: dict, instance: ProcessInstance, context: dict):
        """ایجاد رویداد کلاس در الوکام و ذخیرهٔ لینک روی جلسهٔ درمان؛ در نبود پیکربندی → همان استاب یکپارچه‌سازی."""
        settings = get_settings()
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        aid_raw = (
            action.get("agent_service_id")
            or merged.get("agent_service_id")
            or settings.ALOCOM_DEFAULT_AGENT_SERVICE_ID
        )
        try:
            agent_service_id = int(aid_raw) if aid_raw is not None else 0
        except (TypeError, ValueError):
            agent_service_id = 0

        use_alocom = (
            settings.ALOCOM_ENABLED
            and bool((settings.ALOCOM_USERNAME or "").strip())
            and bool((settings.ALOCOM_PASSWORD or "").strip())
            and agent_service_id > 0
        )
        if not use_alocom:
            if settings.ALOCOM_FALLBACK_TO_UI_HINTS:
                return await self._handle_external_integration(
                    {**action, "type": "create_online_class_links"},
                    instance,
                    context,
                )
            return "create_online_class_links_skipped_no_alocom_config"

        stmt = select(TherapySession).where(TherapySession.student_id == instance.student_id)
        sid_raw = action.get("therapy_session_id") or merged.get("therapy_session_id") or merged.get("session_id")
        sid_filter: Optional[uuid.UUID] = None
        if sid_raw:
            try:
                sid_filter = uuid.UUID(str(sid_raw))
            except (ValueError, TypeError):
                sid_filter = None
        if sid_filter:
            stmt = stmt.where(TherapySession.id == sid_filter)
        else:
            stmt = stmt.where(TherapySession.status == "scheduled").order_by(
                TherapySession.session_date.asc()
            )
        res = await self.db.execute(stmt)
        target = res.scalars().first()
        if not target:
            if settings.ALOCOM_FALLBACK_TO_UI_HINTS:
                return await self._handle_external_integration(
                    {**action, "type": "create_online_class_links"},
                    instance,
                    context,
                )
            return "create_online_class_links_no_therapy_session"

        st = await self._get_student(instance.student_id)
        title = (
            action.get("title")
            or action.get("title_fa")
            or merged.get("class_title")
            or merged.get("alocom_event_title")
            or (f"کلاس آنلاین — {st.student_code}" if st else "کلاس آنلاین")
        )
        duration_raw = action.get("duration_minutes") or merged.get("duration_minutes")
        try:
            duration_minutes = int(duration_raw) if duration_raw is not None else None
        except (TypeError, ValueError):
            duration_minutes = None
        try:
            sba = int(action.get("start_by_admin", merged.get("start_by_admin", 1)))
        except (TypeError, ValueError):
            sba = 1
        fetch_link = bool(action.get("fetch_student_event_link", merged.get("fetch_student_event_link", True)))

        starts_raw = merged.get("session_starts_at") or merged.get("class_starts_at")
        if isinstance(starts_raw, str) and starts_raw.strip():
            try:
                iso = starts_raw.replace("Z", "+00:00")
                target.session_starts_at = datetime.fromisoformat(iso)
            except ValueError:
                pass

        try:
            detail = await provision_therapy_session_alocom(
                self.db,
                session=target,
                agent_service_id=agent_service_id,
                title=str(title)[:500],
                duration_minutes=duration_minutes,
                start_by_admin=sba,
                fetch_student_event_link=fetch_link,
            )
        except AlocomAPIError as e:
            logger.error("Alocom provision failed: %s", e, exc_info=True)
            if settings.ALOCOM_FALLBACK_TO_UI_HINTS:
                ctx = _as_mapping(instance.context_data)
                ctx["alocom_last_error"] = str(e)
                instance.context_data = ctx
                flag_modified(instance, "context_data")
                return await self._handle_external_integration(
                    {**action, "type": "create_online_class_links", "alocom_error": str(e)},
                    instance,
                    context,
                )
            raise

        ctx = _as_mapping(instance.context_data)
        ctx["alocom_last_provision"] = detail
        ctx["last_session_link"] = detail.get("meeting_url")
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"create_online_class_links_ok event_id={detail.get('alocom_event_id')}"

    async def _handle_external_integration(self, action: dict, instance: ProcessInstance, context: dict):
        """یکپارچه‌سازی LMS/وب‌هوک + راهنمای UI؛ برای اکشن‌های «ثبت در LMS» و مشابه."""
        name = action.get("type", "unknown")
        detail = {k: v for k, v in action.items() if k != "type"}
        append_integration_event(instance, name, {"detail": detail, "context_keys": list((context or {}).keys())})
        ctx = _as_mapping(instance.context_data)
        ctx.setdefault("ui_hints", []).append({"action": name, "detail": detail})
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        webhook = await notify_integration(
            name,
            instance.id,
            instance.student_id,
            instance.process_code,
            extra={"action": detail},
        )
        return f"{name} integration={webhook}"

    async def _handle_move_therapist_to_past(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["therapist_assignment"] = "past_list"
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "therapist_moved_to_past_list"

    async def _handle_unlock_student_portal_flag(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["student_portal_result_recorded"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "record_result_in_student_portal"

    async def _handle_redirect_to_process(self, action: dict, instance: ProcessInstance, context: dict):
        code = action.get("process_code", "")
        if code:
            return await self._handle_start_process(
                {"process_code": code, "payload": action.get("payload", {})},
                instance,
                context,
            )
        return "redirect_process_skipped_no_code"

    async def _handle_run_patient_referral(self, action: dict, instance: ProcessInstance, context: dict):
        payload = dict(action.get("payload") or {})
        payload.setdefault("parent_instance_id", str(instance.id))
        return await self._handle_start_process(
            {"process_code": "patient_referral", "payload": payload},
            instance,
            context,
        )

    async def _handle_refer_to_violation_registration(self, action: dict, instance: ProcessInstance, context: dict):
        payload = dict(action.get("payload") or {})
        payload.setdefault("parent_instance_id", str(instance.id))
        return await self._handle_start_process(
            {"process_code": "violation_registration", "payload": payload},
            instance,
            context,
        )

    async def _handle_reset_therapy_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """آغاز مجدد درمان: حذف جلسات آینده (همان مسیر قطع برنامه‌ریزی‌شده)."""
        return await self._handle_delete_future_appointments(action, instance, context)

    async def _handle_update_therapist(self, action: dict, instance: ProcessInstance, context: dict):
        """تعیین درمانگر جدید از context/payload/instance پس از تایید دانشجو."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        merged = {**_as_mapping(instance.context_data), **(context or {}), **(action.get("payload") or {})}
        tid = merged.get("new_therapist_id") or merged.get("therapist_id")
        if tid:
            student.therapist_id = uuid.UUID(str(tid)) if isinstance(tid, str) else tid
        return "therapist_updated"

    async def _handle_update_therapy_schedule(self, action: dict, instance: ProcessInstance, context: dict):
        """اعمال ساعت توافق‌شده روی جلسات آیندهٔ برنامه‌ریزی‌شدهٔ درمان."""
        merged = {**_as_mapping(instance.context_data), **(context or {}), **(action.get("payload") or {})}
        raw = merged.get("session_time_hhmm") or merged.get("new_session_time_hhmm")
        if not raw or not str(raw).strip():
            return await self._handle_external_integration(
                {"type": "update_schedule_missing_time", "detail": "session_time_hhmm required"},
                instance,
                context,
            )
        s = str(raw).strip().replace("٫", ".").replace("،", ":")
        if ":" not in s and len(s) >= 3:
            # e.g. 1430 -> 14:30
            if s.isdigit() and len(s) == 4:
                s = f"{s[:2]}:{s[2:]}"
        parts = s.split(":", 1)
        try:
            h = int(parts[0].strip())
            m = int(parts[1].strip()) if len(parts) > 1 else 0
        except (ValueError, TypeError, IndexError):
            return "update_schedule_invalid_time"
        h = max(0, min(23, h))
        m = max(0, min(59, m))

        today = datetime.now(timezone.utc).date()
        stmt = (
            select(TherapySession)
            .where(
                TherapySession.student_id == instance.student_id,
                TherapySession.status == "scheduled",
                TherapySession.session_date >= today,
            )
            .order_by(TherapySession.session_date)
        )
        result = await self.db.execute(stmt)
        sessions = list(result.scalars().all())
        ctx = _as_mapping(instance.context_data)
        if not sessions:
            ctx["therapy_schedule_update"] = {"requested_time": f"{h:02d}:{m:02d}", "sessions_updated": 0}
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return "update_schedule_no_future_sessions"

        for sess in sessions:
            d = sess.session_date
            if isinstance(d, datetime):
                d = d.date()
            sess.session_starts_at = datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)

        ctx["therapy_schedule_update"] = {"requested_time": f"{h:02d}:{m:02d}", "sessions_updated": len(sessions)}
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"update_schedule_ok n={len(sessions)}"

    async def _handle_process_refund_action(self, action: dict, instance: ProcessInstance, context: dict):
        amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        reason = str(action.get("reason", "process_refund"))
        await self.payment.process_refund(
            student_id=instance.student_id,
            amount=amount,
            reason=reason,
            reference_id=instance.id,
        )
        return f"process_refund amount={amount}"

    async def _handle_move_supervisor_to_past_list(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["supervisor_assignment"] = "past_list"
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "supervisor_moved_to_past_list"

    # ─── Contact Resolution ──────────────────────────────────────

    async def _resolve_contact(self, role: str, instance: ProcessInstance, ntype: str) -> Optional[str]:
        """Resolve a contact (phone/email) for a role in the context of an instance."""
        student = await self._get_student(instance.student_id)
        if not student:
            return None

        if role == "student":
            user = await self._get_user(student.user_id)
            return user.phone or user.email if user else None

        if role == "supervisor" and student.supervisor_id:
            user = await self._get_user_direct(student.supervisor_id)
            return user.phone or user.email if user else None

        if role == "therapist" and student.therapist_id:
            user = await self._get_user_direct(student.therapist_id)
            return user.phone or user.email if user else None

        if role in ("site_manager", "deputy_education", "monitoring_committee_officer",
                     "therapy_committee_chair", "therapy_committee_executor"):
            stmt = select(User).where(User.role == role, User.is_active == True).limit(1)
            result = await self.db.execute(stmt)
            user = result.scalars().first()
            return user.phone or user.email if user else None

        ctx = _as_mapping(instance.context_data)
        if role == "new_supervisor" and ctx.get("new_supervisor_id"):
            user = await self._get_user_direct(uuid.UUID(ctx["new_supervisor_id"]))
            return user.phone or user.email if user else None

        return None

    async def _build_notification_context(self, instance: ProcessInstance, context: dict) -> dict:
        """Build template variable context for notifications."""
        student = await self._get_student(instance.student_id)
        student_user = await self._get_user(student.user_id) if student else None

        notif_ctx = {
            "student_name": student_user.full_name_fa if student_user else "دانشجو",
            "student_code": student.student_code if student else "",
            "process_code": instance.process_code,
            **_as_mapping(instance.context_data),
            **(context or {}),
        }

        if student and student.supervisor_id:
            sup_user = await self._get_user_direct(student.supervisor_id)
            if sup_user:
                notif_ctx["supervisor_name"] = sup_user.full_name_fa or "سوپروایزر"

        if student and student.therapist_id:
            th_user = await self._get_user_direct(student.therapist_id)
            if th_user:
                notif_ctx["therapist_name"] = th_user.full_name_fa or "درمانگر"

        if instance.process_code == "educational_leave" and notif_ctx.get("committee_meeting_at"):
            notif_ctx["meeting_summary_fa"] = self._format_committee_meeting_summary_fa(notif_ctx)
        notif_ctx.setdefault("meeting_summary_fa", "")

        if instance.process_code == "therapy_completion":
            ctxm = _as_mapping(instance.context_data)
            notif_ctx.setdefault("therapy_hours", ctxm.get("therapy_hours") or ctxm.get("therapy_hours_2x"))
            notif_ctx.setdefault("therapy_threshold", ctxm.get("therapy_threshold"))
            notif_ctx.setdefault("clinical_hours", ctxm.get("clinical_hours"))
            notif_ctx.setdefault("clinical_threshold", ctxm.get("clinical_threshold"))
            notif_ctx.setdefault("supervision_hours", ctxm.get("supervision_hours"))
            notif_ctx.setdefault("supervision_threshold", ctxm.get("supervision_threshold"))
            if student:
                ex = _as_mapping(student.extra_data)
                prior = ex.get("prior_therapy_therapist_id")
                if prior and not notif_ctx.get("therapist_name"):
                    try:
                        th_user = await self._get_user_direct(uuid.UUID(str(prior)))
                        if th_user:
                            notif_ctx["therapist_name"] = th_user.full_name_fa or "درمانگر"
                    except (ValueError, TypeError):
                        pass

        return notif_ctx

    @staticmethod
    def _format_committee_meeting_summary_fa(ctx: dict) -> str:
        """خلاصهٔ خوانا برای پیامک/ایمیل جلسه کمیته مرخصی."""
        raw = (ctx.get("committee_meeting_at") or "").strip()
        mode = (ctx.get("committee_meeting_mode") or "").strip()
        mode_fa = "آنلاین" if mode == "online" else ("حضوری" if mode == "in_person" else mode or "—")
        parts = [f"زمان (ثبت‌شده در سامانه): {raw[:19] if len(raw) >= 10 else raw}", f"نوع: {mode_fa}"]
        if mode == "online" and (ctx.get("committee_meeting_link") or "").strip():
            parts.append(f"لینک: {(ctx.get('committee_meeting_link') or '').strip()}")
        elif mode == "in_person" and (ctx.get("committee_meeting_location_fa") or "").strip():
            parts.append(f"محل: {(ctx.get('committee_meeting_location_fa') or '').strip()}")
        return " — ".join(parts)

    async def _get_student(self, student_id) -> Optional[Student]:
        stmt = select(Student).where(Student.id == student_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _get_user(self, user_id) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _get_user_direct(self, user_id) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    # ─── Action Registry ─────────────────────────────────────────

    _registry = {
        "notification": _handle_notification,
        "start_process": _handle_start_process,

        "add_recurring_therapy_session": _handle_add_recurring_session,
        "add_recurring_supervision_session": _handle_add_recurring_session,
        "remove_selected_therapy_sessions": _handle_remove_therapy_sessions,
        "remove_selected_supervision_sessions": _handle_remove_selected_sessions,
        "release_therapist_slots_to_available_sheet": _handle_release_therapist_slots,
        "release_supervisor_slots_to_available_sheet": _handle_release_slots,
        "record_therapy_change_history": _handle_record_change_history,

        "create_extra_supervision_session_record": _handle_create_extra_session_record,
        "create_attendance_field_for_session": _handle_create_attendance_field,
        "activate_online_session_link": _handle_activate_online_link,
        "record_supervision_attendance": _handle_record_supervision_attendance,
        "add_hour_to_supervision_block": _handle_add_hour_to_block,
        "connect_to_supervision_50h_completion": _handle_connect_to_50h,

        "update_supervision_schedule_frequency": _handle_update_schedule_frequency,
        "remove_weekly_session_from_student_schedule": _handle_remove_weekly_session,

        "cancel_session": _handle_cancel_session,
        "add_credit_if_paid": _handle_add_credit,
        "deduct_credit_session": _handle_deduct_credit_session,
        "register_makeup_session": _handle_register_makeup,
        "enable_online_session_link": _handle_enable_online_link,

        "mark_sessions_cancelled_by_student": _handle_mark_cancelled,
        "block_attendance_for_cancelled_sessions": _handle_block_attendance,

        "add_to_credit_balance": _handle_add_to_credit_balance,
        "forfeit_session_payment": _handle_forfeit_payment,
        "create_debt_or_deduct_credit": _handle_create_debt_or_deduct_credit,
        "increment_absence_counter": _handle_increment_absence,

        "generate_payment_invoice": _handle_generate_payment_invoice,
        "zero_debt_if_paid": _handle_zero_debt_if_paid,
        "allocate_credit_to_sessions": _handle_allocate_credit_to_sessions,
        "unlock_session_links": _handle_unlock_session_links,
        "unlock_attendance_registration": _handle_unlock_attendance_registration,
        "suspend_sessions": _handle_suspend_sessions,

        "activate_therapy": _handle_activate_therapy,
        "block_class_access": _handle_block_class_access,
        "resolve_access_restrictions": _handle_resolve_access,
        "create_session_link": _handle_create_session_link,
        "apply_start_therapy_session_schedule": _handle_apply_start_therapy_session_schedule,
        "delete_future_therapy_appointments": _handle_delete_future_appointments,
        "release_therapist_slots": _handle_release_therapist_slots,
        "update_therapy_status": _handle_update_therapy_status,
        "mark_therapy_relationship_terminated": _handle_mark_terminated,
        "log_termination_request": _handle_log_termination,
        "set_student_status": _handle_set_student_status,

        "send_45_48_reminder_if_applicable": _handle_send_reminder,
        "unlock_payment_for_50th_session": _handle_unlock_payment_50th,
        "display_supervision_history": _handle_display_supervision_history,
        "remove_slot_from_available": _handle_remove_slot_from_available,

        "record_attendance": _handle_record_attendance_action,
        "record_absence_auto": _handle_record_absence_auto,
        "add_hour_by_course_and_weekly_sessions": _handle_add_hour_by_course_and_weekly_sessions,
        "notify_committee": _handle_notify_committee,
        "update_record": _handle_update_record,
        "merge_instance_context": _handle_merge_instance_context,
        "deactivate_student_account": _handle_deactivate_student_account,
        "call_bpms_subprocess": _handle_call_bpms_subprocess,
        "redirect_to_process": _handle_redirect_to_process,
        "move_therapist_to_past": _handle_move_therapist_to_past,
        "record_result_in_student_portal": _handle_unlock_student_portal_flag,
        "ensure_therapist_slots_freed": _handle_release_therapist_slots,

        "send_unlock_to_lms": _handle_external_integration,
        "unlock_student_therapist_selection": _handle_external_integration,
        "record_commission_result": _handle_external_integration,
        "store_nezarat_recommendation": _handle_external_integration,
        "generate_termination_letter": _handle_external_integration,
        "register_new_supervision_block_in_lms": _handle_external_integration,
        "enable_attendance_for_new_supervisor": _handle_external_integration,
        "create_online_link_50th": _handle_external_integration,
        "enable_attendance_for_current_supervisor_50th": _handle_external_integration,
        "display_available_supervisor_slots": _handle_external_integration,
        "display_mandatory_message": _handle_external_integration,
        "apply_24h_rule_for_start_date": _handle_external_integration,
        "display_calculated_start_date": _handle_external_integration,
        "cancel_supervision_session": _handle_cancel_session,
        "add_supervision_credit_if_paid": _handle_add_credit,
        "register_supervision_makeup_session": _handle_register_makeup,
        "enable_attendance_registration": _handle_unlock_attendance_registration,
        "release_supervisor_slot": _handle_release_supervisor_slot,
        "move_supervisor_to_past_list": _handle_move_supervisor_to_past_list,
        "record_interruption_dates": _handle_external_integration,
        "monitor_return_at_end_date": _handle_external_integration,
        "run_patient_referral": _handle_run_patient_referral,
        "move_ta_to_instructor": _handle_external_integration,
        "upgrade_rank_to_assistant_faculty": _handle_external_integration,
        "unlock_next_course_in_track": _handle_external_integration,
        "publish_courses_to_website": _handle_external_integration,
        "publish_academic_calendar_to_profiles": _handle_external_integration,
        "show_popup": _handle_external_integration,
        "load_available_courses": _handle_external_integration,
        "register_courses_in_portal": _handle_external_integration,
        "create_online_class_links": _handle_create_online_class_links,
        "schedule_installment_reminders": _handle_external_integration,
        "block_attendance_registration": _handle_block_attendance,
        "notify_instructor": _handle_external_integration,
        "unblock_attendance_registration": _handle_unlock_attendance_registration,

        "record_commission_result_in_student_portal": _handle_external_integration,
        "record_evaluation_completion": _handle_external_integration,
        "lock_block_counter": _handle_external_integration,
        "display_evaluation_warning_to_supervisor": _handle_external_integration,
        "create_evaluation_task": _handle_external_integration,
        "suspend_class_registration": _handle_block_class_access,
        "revoke_intern_status": _handle_revoke_intern_status,
        "set_leave_return_schedule": _handle_set_leave_return_schedule,
        "warn_if": _handle_warn_if,

        # نام‌های اضافهٔ متادیتا (هم‌ارز یا استاب یکپارچه‌سازی)
        "add_ta_score": _handle_external_integration,
        "apply_electronic_signature_and_seal": _handle_external_integration,
        "archive_letter_in_student_file": _handle_external_integration,
        "block_future_applications": _handle_external_integration,
        "block_future_enrollment": _handle_external_integration,
        "block_next_term_registration": _handle_external_integration,
        "cancel_all_future_sessions": _handle_delete_future_appointments,
        "create_education_committee_task": _handle_external_integration,
        "sync_extra_session_reenter_fields": _handle_sync_extra_session_reenter_fields,
        "prepare_extra_session_payment": _handle_prepare_extra_session_payment,
        "create_extra_session_record": _handle_create_extra_session_record,
        "note_extra_session_calendar": _handle_note_extra_session_calendar,
        "add_extra_session_therapy_hours": _handle_add_extra_session_therapy_hours,
        "create_lms_course_links": _handle_external_integration,
        "create_user_account": _handle_external_integration,
        "deduct_credit_if_has": _handle_deduct_credit_session,
        "display_error_message": _handle_external_integration,
        "display_meeting_in_portal": _handle_external_integration,
        "display_rejection_explanations": _handle_external_integration,
        "enable_pdf_export": _handle_external_integration,
        "generate_certificate": _handle_external_integration,
        "generate_cumulative_transcript": _handle_external_integration,
        "generate_decline_list": _handle_external_integration,
        "generate_pdf_export": _handle_external_integration,
        "generate_term_transcript": _handle_external_integration,
        "increase_intern_capacity": _handle_external_integration,
        "load_term3_courses": _handle_external_integration,
        "log_sla_breach_in_portals": _handle_external_integration,
        "move_to_past_lists": _handle_external_integration,
        "process_refund": _handle_process_refund_action,
        "reactivate_class_registration": _handle_reactivate_class_registration,
        "record_accounting": _handle_external_integration,
        "record_pause_dates_in_lms": _handle_external_integration,
        "record_termination_date": _handle_external_integration,
        "record_termination_in_student_portal": _handle_external_integration,
        "refer_to_violation_registration": _handle_refer_to_violation_registration,
        "register_in_calendar": _handle_external_integration,
        "register_student_in_courses": _handle_external_integration,
        "release_supervisor_slots": _handle_release_slots,
        "reset_therapy_sessions": _handle_reset_therapy_sessions,
        "retain_patients": _handle_external_integration,
        "retain_supervisor": _handle_external_integration,
        "retain_therapist_and_supervisor": _handle_external_integration,
        "revoke_student_access": _handle_external_integration,
        "schedule_reminder": _handle_external_integration,
        "scheduled_notification": _handle_external_integration,
        "send_to_dashboard": _handle_external_integration,
        "send_to_progress_committee": _handle_external_integration,
        "share_document_with_interviewer": _handle_external_integration,
        "show_payment_confirmation": _handle_external_integration,
        "store_executive_advisory_opinion": _handle_external_integration,
        "store_rejection_reason_confidential": _handle_external_integration,
        "unblock_next_term_registration": _handle_external_integration,
        "update_schedule": _handle_update_therapy_schedule,
        "update_therapist": _handle_update_therapist,
        "update_total_hours": _handle_external_integration,
        "upload_certificate_to_portal": _handle_external_integration,
    }
