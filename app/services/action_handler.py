"""Action Handler - Executes transition actions from process metadata.

This is the bridge between the state machine engine (which reads metadata and
changes states) and the actual business logic (SMS, session management, etc.).

When a transition fires, its `actions` list is published via EventBus.
This handler subscribes to those events and dispatches each action to
the appropriate service method.
"""

import json
import re
import uuid
import logging
from typing import Optional, Any, List
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from app.services.notification_service import TEMPLATES, notification_service
from app.services.payment_service import PaymentService
from app.services.attendance_service import AttendanceService
from app.services.external_integration import append_integration_event, notify_integration
from app.services.workflow import (
    portal_notifications as _svc_portal,
    lms_service as _svc_lms,
    document_service as _svc_document,
    evaluation_records as _svc_evaluation,
    capacity_service as _svc_capacity,
    termination_records as _svc_termination,
    calendar_service as _svc_calendar,
    registration_gate as _svc_gate,
    role_promotion as _svc_role,
)
from app.config import get_settings
from app.services.alocom_client import AlocomAPIError
from app.services.alocom_provision import provision_therapy_session_alocom
from app.services.attendance_tracking_sync import (
    cancel_attendance_instances_for_therapy_session_ids,
    ensure_attendance_instance_for_session,
)
from app.services.financial_program_defaults_service import get_effective_financial_program_defaults
from app.services.interview_slot_service import enrich_interview_notification_context

logger = logging.getLogger(__name__)

_LIVE_SESSION_PREP_CODES = frozenset({
    "live_supervision_session_prep",
    "live_therapy_observation_session_prep",
})

_LIVE_SESSION_COURSE_KEYWORDS = {
    "live_supervision_session_prep": ("supervision", "سوپرویژن"),
    "live_therapy_observation_session_prep": ("observation", "مشاهده", "therapy_observation"),
}


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


async def validate_supervision_reduction_preflight(
    db: AsyncSession,
    instance: ProcessInstance,
    payload: dict,
    student: Student,
) -> Optional[str]:
    """
    اعتبارسنجی payload قبل از ترنزیشن sessions_selected (فرایند ۲۴).
    برمی‌گرداند رشتهٔ خطا یا None.
    """
    merged = {**_as_mapping(instance.context_data), **(payload or {})}
    try:
        weekly = int(merged.get("supervision_weekly_sessions") or 1)
    except (TypeError, ValueError):
        weekly = 1
    if weekly < 2:
        return "این مسیر فقط برای دانشجویان با ۲ جلسه یا بیشتر سوپرویژن در هفته است."

    selected = _parse_supervision_reduction_selected_list(merged.get("selected_sessions"))
    if not selected:
        return "حداقل یک جلسهٔ سوپرویژن برای حذف انتخاب کنید."

    remaining = weekly - len(selected)
    if remaining < 1:
        return "حداقل یک جلسهٔ سوپرویژن در هفته باید باقی بماند."

    max_remove = weekly - 1
    if len(selected) > max_remove:
        return f"حداکثر {max_remove} جلسه را می‌توانید حذف کنید (انتخاب‌شده: {len(selected)})."

    return None


def _parse_supervision_reduction_selected_list(raw) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x is not None and str(x).strip()]
            except (json.JSONDecodeError, TypeError):
                return []
        return [p for p in re.split(r"[,،\s]+", s) if p]
    return [str(raw).strip()]


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
                try:
                    from app.services.failed_action_service import record_failed_action

                    await record_failed_action(
                        self.db,
                        instance,
                        action_type,
                        action if isinstance(action, dict) else None,
                        str(e),
                    )
                except Exception:
                    logger.exception("Failed to persist failed_action for %s", action_type)
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

        if action_type.startswith("record_"):
            return await self._handle_record_process_artifact(action, instance, context)

        logger.warning(f"No handler for action type '{action_type}', skipping.")
        return f"no_handler_for_{action_type}"

    # ─── Notification ────────────────────────────────────────────

    async def _handle_notification(self, action: dict, instance: ProcessInstance, context: dict):
        ntype = action.get("notification_type", "sms")
        template = action.get("template", "")
        recipients = action.get("recipients", [])

        notif_context = await self._build_notification_context(instance, context)
        if not self._notification_action_condition_matches(action, notif_context):
            return "skipped_condition"

        msg_override = (action.get("template_text_fa") or action.get("template_text") or "").strip() or None
        sent = []
        effective_template = template
        if ntype == "in_app" and template.startswith("sla_warning_") and template not in TEMPLATES:
            effective_template = "sla_warning_non_blocking"
            if not notif_context.get("warning_message"):
                notif_context = {
                    **notif_context,
                    "warning_message": msg_override
                    or action.get("warning_message_fa")
                    or f"هشدار مهلت: {template}",
                }

        # آماده‌سازی ترم: اعلان in_app پایدار برای همهٔ کاربران نقش بعدی
        from app.services.semester_prep_rbac import is_prep_process

        if ntype == "in_app" and is_prep_process(instance.process_code):
            prep_sent = await self._persist_prep_in_app_notifications(
                instance,
                recipients=recipients,
                template=effective_template,
                notif_context=notif_context,
                message_override=msg_override,
                warning_message=action.get("warning_message"),
            )
            if prep_sent is not None:
                if template.startswith("sla_warning_"):
                    self._record_sla_warning_dispatch(
                        instance,
                        notification_type=ntype,
                        template=template,
                        message=msg_override
                        or notif_context.get("warning_message")
                        or f"هشدار مهلت: {template}",
                        recipients=[
                            {"recipient_role": r, "contact": None, "delivered": True}
                            for r in recipients
                        ],
                    )
                return prep_sent

        warning_records: list[dict] = []
        last_message: str = ""
        for role in recipients:
            if role == "class_students" and instance.process_code in _LIVE_SESSION_PREP_CODES:
                course_code = await self._live_session_course_code(instance)
                contacts = (
                    await self._resolve_class_student_contacts(instance, course_code)
                    if course_code
                    else []
                )
                if not contacts:
                    sent.append(f"{role}:no_contact")
                    logger.warning(f"No class_students contacts for instance {instance.id}")
                    warning_records.append(
                        {"recipient_role": role, "contact": None, "delivered": False}
                    )
                    continue
                for contact in contacts:
                    result = await notification_service.send_notification(
                        ntype,
                        effective_template,
                        contact,
                        notif_context,
                        message_override=msg_override,
                    )
                    last_message = result.message or last_message
                    sent.append(f"{role}:{contact}:{result.success}")
                    warning_records.append(
                        {
                            "recipient_role": role,
                            "contact": contact,
                            "delivered": bool(result.success),
                        }
                    )
                continue

            if role in ("accounting", "finance"):
                contacts = await self._resolve_finance_contacts(ntype)
                if not contacts:
                    sent.append(f"{role}:no_contact")
                    logger.warning(f"No contact for role '{role}' in instance {instance.id}")
                    warning_records.append(
                        {"recipient_role": role, "contact": None, "delivered": False}
                    )
                    continue
                for contact in contacts:
                    result = await notification_service.send_notification(
                        ntype,
                        effective_template,
                        contact,
                        notif_context,
                        message_override=msg_override,
                    )
                    last_message = result.message or last_message
                    sent.append(f"{role}:{contact}:{result.success}")
                    warning_records.append(
                        {
                            "recipient_role": role,
                            "contact": contact,
                            "delivered": bool(result.success),
                        }
                    )
                continue

            contact = await self._resolve_contact(role, instance, ntype)
            if contact:
                result = await notification_service.send_notification(
                    ntype,
                    effective_template,
                    contact,
                    notif_context,
                    message_override=msg_override,
                )
                last_message = result.message or last_message
                sent.append(f"{role}:{contact}:{result.success}")
                warning_records.append(
                    {
                        "recipient_role": role,
                        "contact": contact,
                        "delivered": bool(result.success),
                    }
                )
            else:
                sent.append(f"{role}:no_contact")
                logger.warning(f"No contact for role '{role}' in instance {instance.id}")
                warning_records.append(
                    {
                        "recipient_role": role,
                        "contact": None,
                        "delivered": False,
                    }
                )

        if template.startswith("sla_warning_"):
            self._record_sla_warning_dispatch(
                instance,
                notification_type=ntype,
                template=template,
                message=(
                    last_message
                    or msg_override
                    or notif_context.get("warning_message")
                    or f"هشدار مهلت: {template}"
                ),
                recipients=warning_records,
            )

        return f"sent={','.join(sent)}"

    async def _persist_prep_in_app_notifications(
        self,
        instance: ProcessInstance,
        *,
        recipients: list,
        template: str,
        notif_context: dict,
        message_override: str | None,
        warning_message: str | None = None,
    ) -> str:
        """ذخیرهٔ اعلان in_app آماده‌سازی ترم برای همهٔ کاربران فعال نقش گیرنده."""
        from app.core.user_roles import user_matches_role_sql
        from app.services.notification_service import notification_service
        from app.services.panel_flash_messages import create_panel_flash_message
        from app.services.semester_prep_rbac import prep_notification_portal_roles

        body = (message_override or "").strip()
        if not body:
            rendered = notification_service.get_template(template, "in_app") or ""
            try:
                body = rendered.format(**(notif_context or {})) if rendered else ""
            except (KeyError, ValueError):
                body = rendered
        if not body and warning_message:
            body = str(warning_message).strip()
        if not body:
            body = f"اقدام جدید در آماده‌سازی ترم ({template})"

        workbench = (
            f"/panel/semester-prep/workbench?process_code="
            f"{instance.process_code}"
        )
        sent: list[str] = []
        seen_ids: set = set()
        for role in recipients:
            role_s = str(role or "").strip()
            if not role_s:
                continue
            # گیرندگان گروهی بدون کاربر مشخص — فقط لاگ
            if role_s in (
                "all_active_students",
                "all_active_fall_students",
                "all_instructors",
                "course_committee_members",
            ):
                result = await notification_service.send_notification(
                    "in_app",
                    template,
                    f"role:{role_s}",
                    notif_context,
                    message_override=body,
                )
                sent.append(f"{role_s}:broadcast_log:{result.success}")
                continue

            portal_roles = prep_notification_portal_roles(role_s)
            for pr in portal_roles:
                stmt = (
                    select(User)
                    .where(user_matches_role_sql(pr), User.is_active.is_(True))
                    .order_by(User.full_name_fa.asc())
                )
                users = list((await self.db.execute(stmt)).scalars().all())
                for user in users:
                    if user.id in seen_ids:
                        continue
                    seen_ids.add(user.id)
                    await create_panel_flash_message(
                        self.db,
                        user_id=user.id,
                        message=body,
                        level="success",
                        source_path=workbench,
                        category="system",
                    )
                    contact = user.phone or user.email or str(user.id)
                    result = await notification_service.send_notification(
                        "in_app",
                        template,
                        contact,
                        notif_context,
                        message_override=body,
                    )
                    sent.append(f"{role_s}:{contact}:{result.success}")

            if not any(s.startswith(f"{role_s}:") for s in sent):
                sent.append(f"{role_s}:no_users")
                logger.warning(
                    "No prep notification users for role %s on instance %s",
                    role_s,
                    instance.id,
                )

        return f"prep_flash_sent={','.join(sent) if sent else 'none'}"

    @staticmethod
    def _record_sla_warning_dispatch(
        instance: ProcessInstance,
        *,
        notification_type: str,
        template: str,
        message: str,
        recipients: list[dict],
    ) -> None:
        """ثبت رخداد ارسال هشدار مهلت در context نمونه تا در UI قابل بررسی باشد."""
        ctx = _as_mapping(instance.context_data)
        log = ctx.get("__sla_warning_log")
        if not isinstance(log, list):
            log = []
        log.append(
            {
                "fired_at": datetime.now(timezone.utc).isoformat(),
                "state_code": instance.current_state_code,
                "notification_type": notification_type,
                "template": template,
                "message": message,
                "recipients": recipients,
            }
        )
        ctx["__sla_warning_log"] = log[-100:]
        instance.context_data = ctx
        flag_modified(instance, "context_data")

    # ─── Sub-process Start ───────────────────────────────────────

    def _eval_start_process_run_if(self, action: dict, instance: ProcessInstance, transition_context: dict) -> bool:
        code = action.get("run_if")
        if not code:
            return True
        merged = {**_as_mapping(instance.context_data), **(transition_context or {})}
        if code == "session_not_cancelled":
            return merged.get("session_cancelled") is not True
        return True

    @staticmethod
    def _notification_action_condition_matches(action: dict, notif_context: dict) -> bool:
        raw = (action.get("condition") or "").strip()
        if not raw:
            return True
        if "==" not in raw:
            return True
        left, right = raw.split("==", 1)
        key = left.strip()
        expect = right.strip().strip("'").strip('"')
        return str(notif_context.get(key)) == str(expect)

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

    async def _merge_committees_review_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        """زمینهٔ اولیهٔ زیرفرایند ب — علت درمانگر و مسیر ورود از والد."""
        merged = dict(base or {})
        merged["parent_instance_id"] = str(parent.id)
        merged["parent_process_code"] = parent.process_code
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        for key in (
            "reason",
            "label",
            "reason_code",
            "termination_reason_code",
            "termination_note",
            "commission_opinion_fa",
            "commission_meeting_notes_fa",
            "therapist_id",
        ):
            if pctx.get(key) is not None and merged.get(key) is None:
                merged[key] = pctx[key]
        if parent.process_code == "specialized_commission_review":
            merged.setdefault("entry_reason", "ineligibility_specialized_commission")
            gp_raw = pctx.get("parent_instance_id")
            if gp_raw:
                try:
                    gp = await self.db.get(ProcessInstance, uuid.UUID(str(gp_raw)))
                except (ValueError, TypeError):
                    gp = None
                if gp:
                    gctx = _as_mapping(gp.context_data)
                    for key in ("termination_reason_code", "termination_note", "reason_code"):
                        if gctx.get(key) is not None and merged.get(key) is None:
                            merged[key] = gctx[key]
                    merged["grandparent_process_code"] = gp.process_code
        elif parent.process_code == "therapy_early_termination":
            merged.setdefault("entry_reason", "termination_reason_4")
            if merged.get("termination_reason_code") is None:
                merged["termination_reason_code"] = (
                    pctx.get("termination_reason_code") or pctx.get("reason_code") or 4
                )
        for key, val in tc.items():
            if merged.get(key) is None and val is not None:
                merged[key] = val
        return merged

    async def _merge_commission_review_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        """زمینهٔ اولیهٔ زیرفرایند الف از فرایند قطع زودرس."""
        merged = dict(base or {})
        merged["parent_instance_id"] = str(parent.id)
        merged["parent_process_code"] = parent.process_code
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        for key in ("termination_reason_code", "termination_note", "reason_code", "therapist_id"):
            if pctx.get(key) is not None and merged.get(key) is None:
                merged[key] = pctx[key]
        for key, val in tc.items():
            if merged.get(key) is None and val is not None:
                merged[key] = val
        return merged

    async def _merge_violation_registration_initial_payload(
        self,
        parent: ProcessInstance,
        base: dict,
        transition_context: Optional[dict],
    ) -> dict:
        """زمینهٔ اولیهٔ فرایند ثبت تخلف از فرایند مبدأ."""
        merged = dict(base or {})
        merged["parent_instance_id"] = str(parent.id)
        merged["source_process_code"] = parent.process_code
        pctx = _as_mapping(parent.context_data)
        tc = transition_context or {}
        reason = merged.get("reason") or pctx.get("reason") or pctx.get("reason_code")
        if reason is not None:
            merged.setdefault("source_reason", str(reason))
        for key in (
            "description",
            "violation_description",
            "termination_note",
            "occurrence_date",
            "reporter_name",
        ):
            if pctx.get(key) is not None and merged.get(key) is None:
                merged[key] = pctx[key]
        if merged.get("description") is None and merged.get("violation_description"):
            merged["description"] = merged["violation_description"]
        for key, val in tc.items():
            if merged.get(key) is None and val is not None:
                merged[key] = val
        merged["violation_reported_at"] = datetime.now(timezone.utc).isoformat()
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
            elif sub_code == "committees_review":
                payloads.append(
                    await self._merge_committees_review_initial_payload(instance, base_payload, context)
                )
            elif sub_code == "specialized_commission_review":
                payloads.append(
                    await self._merge_commission_review_initial_payload(instance, base_payload, context)
                )
            elif sub_code == "violation_registration":
                payloads.append(
                    await self._merge_violation_registration_initial_payload(
                        instance, base_payload, context
                    )
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
                    await notification_service.send_sms(
                        str(phone).strip(),
                        msg,
                        template_key="therapy_session_reduction_completed",
                        context={},
                    )
                except Exception:
                    pass

        return f"therapy_sessions_cancelled={len(cancelled_ids)} new_weekly={new_weekly}"

    async def _handle_reopen_student_step_forms(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """باز کردن مجدد فرم مرحلهٔ دانشجو پس از رد/بازگشت (مثلاً therapist_declined)."""
        from app.meta.student_step_forms import apply_reopen_student_step_forms_to_context

        state_code = (
            str(action.get("state") or action.get("state_code") or instance.current_state_code or "").strip()
        )
        if not state_code:
            return "reopen_student_step_forms skipped (no state)"

        clear_keys = action.get("clear_keys") or action.get("clear_context_keys") or []
        if isinstance(clear_keys, str):
            clear_keys = [p.strip() for p in clear_keys.split(",") if p.strip()]
        elif not isinstance(clear_keys, list):
            clear_keys = []

        clear_submitted = action.get("clear_submitted", True)
        ctx = apply_reopen_student_step_forms_to_context(
            instance.context_data,
            state_code,
            clear_keys=[str(k) for k in clear_keys if k is not None],
            clear_submitted=bool(clear_submitted),
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"reopen_student_step_forms state={state_code} cleared={len(clear_keys)}"

    async def _handle_release_therapist_slots(self, action: dict, instance: ProcessInstance, context: dict):
        """آزادسازی اسلات‌های درمانگر آموزشی در شیت وقت‌های آزاد."""
        from app.services.educational_therapist_slot_service import release_slots

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"

        slot_ids_raw = merged.get("slot_ids") or merged.get("booked_slot_ids")
        slot_ids = None
        if slot_ids_raw:
            import uuid as _uuid

            slot_ids = []
            raw_list = slot_ids_raw if isinstance(slot_ids_raw, list) else str(slot_ids_raw).split(",")
            for item in raw_list:
                try:
                    slot_ids.append(_uuid.UUID(str(item).strip()))
                except (TypeError, ValueError):
                    pass

        therapist_id = merged.get("therapist_id") or merged.get("new_therapist_id")
        therapist_uuid = None
        if therapist_id:
            try:
                therapist_uuid = uuid.UUID(str(therapist_id))
            except (TypeError, ValueError):
                therapist_uuid = student.therapist_id
        elif student.therapist_id:
            therapist_uuid = student.therapist_id

        released = await release_slots(
            self.db,
            student_id=instance.student_id,
            instance_id=instance.id,
            slot_ids=slot_ids or None,
            therapist_user_id=therapist_uuid,
        )

        extra = _as_mapping(student.extra_data)
        log = list(extra.get("therapist_slot_release_log") or [])
        entry: dict = {
            "at": datetime.now(timezone.utc).isoformat(),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "released_count": released,
            "source": action.get("source") or instance.process_code,
        }
        if instance.process_code == "therapy_completion":
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
        return f"therapist_slots_released n={released}"

    async def _handle_book_educational_therapist_slots(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        from app.services.educational_therapist_slot_service import (
            book_slots_from_context,
            build_slot_summary_for_context,
        )

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        therapist_key = (action.get("therapist_id_key") or "therapist_id").strip()
        slot_key = (action.get("slot_ids_key") or "slot_ids").strip()
        weekly_key = (action.get("weekly_sessions_key") or "weekly_sessions").strip()

        result = await book_slots_from_context(
            self.db,
            instance_id=instance.id,
            student_id=instance.student_id,
            context=merged,
            therapist_id_key=therapist_key,
            slot_ids_key=slot_key,
            weekly_sessions_key=weekly_key,
        )
        if result == "skip_no_slot_ids":
            return result

        slot_ids = merged.get(slot_key) or merged.get("slot_ids")
        if slot_ids:
            from app.services.educational_therapist_slot_service import _parse_slot_ids
            from app.models.operational_models import EducationalTherapistSlot
            from sqlalchemy import select

            ids = _parse_slot_ids(slot_ids)
            if ids:
                rows = (await self.db.execute(
                    select(EducationalTherapistSlot).where(EducationalTherapistSlot.id.in_(ids))
                )).scalars().all()
                summary = build_slot_summary_for_context(rows)
                ctx = _as_mapping(instance.context_data)
                ctx.update(summary)
                ctx["booked_slot_ids"] = summary.get("slot_ids")
                instance.context_data = ctx
                flag_modified(instance, "context_data")

        return result

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
        from app.services.payment_service import LEDGER_SUPERVISION, LEDGER_THERAPY

        # add_supervision_credit_if_paid → supervision wallet; کنسلی درمانگر → therapy
        if action.get("type") == "add_supervision_credit_if_paid":
            category = LEDGER_SUPERVISION
            reason = "بستانکاری - لغو جلسه توسط سوپروایزر"
        else:
            category = action.get("ledger_category") or self._fee_ledger_category(instance, context)
            reason = "بستانکاری - لغو جلسه توسط درمانگر"
            if category == LEDGER_SUPERVISION:
                reason = "بستانکاری - لغو جلسه سوپرویژن"
        await self.payment.process_refund(
            student_id=instance.student_id,
            amount=self.payment.DEFAULT_SESSION_FEE,
            reason=reason,
            reference_id=instance.id,
            category=category or LEDGER_THERAPY,
        )
        return f"credit_added_for_cancelled_session category={category}"

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
            category="therapy",
        )
        return f"debt_for_shortfall amount={fee}"

    async def _handle_register_makeup(self, action: dict, instance: ProcessInstance, context: dict):
        return "makeup_session_registered"

    async def _handle_enable_online_link(self, action: dict, instance: ProcessInstance, context: dict):
        return await self._unlock_online_therapy_session_links(
            action, instance, context, result_prefix="online_session_link_enabled"
        )

    # ─── Attendance & Hours ──────────────────────────────────────

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

    # ─── Financial ───────────────────────────────────────────────

    @staticmethod
    def _fee_ledger_category(instance: ProcessInstance, context: Optional[dict] = None) -> str:
        """therapy vs supervision wallet for fee_determination / session credits."""
        from app.services.payment_service import LEDGER_SUPERVISION, LEDGER_THERAPY

        ctx = {**_as_mapping(instance.context_data), **(context or {})}
        if (
            ctx.get("context") == "supervision"
            or ctx.get("supervision_session_paid") is not None
            or str(ctx.get("session_kind") or "").lower().startswith("supervision")
            or "supervision" in str(instance.process_code or "")
        ):
            return LEDGER_SUPERVISION
        return LEDGER_THERAPY

    async def _handle_add_to_credit_balance(self, action: dict, instance: ProcessInstance, context: dict):
        """fee_determination: record financial credit; session_payment: virtual balance (payment row from gateway callback)."""
        from app.services.payment_service import LEDGER_THERAPY

        category = action.get("ledger_category") or self._fee_ledger_category(instance, context)
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
                category=category,
            )
            return f"credit_refund_recorded: {total} category={category}"
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
            category=category or LEDGER_THERAPY,
        )
        return f"credit_added: {amount} category={category}"

    async def _handle_forfeit_payment(self, action: dict, instance: ProcessInstance, context: dict):
        category = action.get("ledger_category") or self._fee_ledger_category(instance, context)
        amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        await self.payment.charge_absence_fee(
            student_id=instance.student_id,
            amount=amount,
            created_by=None,
            category=category,
        )
        ctx = _as_mapping(instance.context_data)
        ctx["session_payment_forfeited"] = True
        ctx["forfeit_amount"] = amount
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"session_payment_forfeited amount={amount} category={category}"

    async def _handle_create_debt_or_deduct_credit(self, action: dict, instance: ProcessInstance, context: dict):
        """سناریوی ۴: اگر بستانکاری همان کیف‌پول کافی باشد، بدون ایجاد بدهی جدید تسویه ثبت می‌شود."""
        category = action.get("ledger_category") or self._fee_ledger_category(instance, context)
        try:
            amount = float(action.get("amount", self.payment.DEFAULT_SESSION_FEE))
        except (TypeError, ValueError):
            amount = float(self.payment.DEFAULT_SESSION_FEE)
        bal_info = await self.payment.get_student_balance(instance.student_id, category=category)
        net = float(bal_info.get("balance", 0) or 0)
        ctx = _as_mapping(instance.context_data)
        if net >= amount:
            ctx["fee_settlement_mode"] = "from_existing_credit_balance"
            ctx["fee_settlement_amount"] = amount
            ctx["fee_settlement_ledger_category"] = category
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return f"fee_settled_from_credit balance_was={net} amount={amount} category={category}"
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=amount,
            description="بدهی غیبت جلسه",
            reference_id=instance.id,
            category=category,
        )
        return f"debt_created: {amount} category={category}"

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
        fd_inv = await get_effective_financial_program_defaults(self.db)
        per = float(fd_inv.get("default_therapy_session_fee_toman") or self.payment.DEFAULT_SESSION_FEE)
        # بدهی واقعی (گذشته/برگزارشده) — نه جلسات آیندهٔ تقویم؛ با تسویه اجباری به فاکتور
        from app.services.therapy_session_schedule import count_therapy_debt_sessions

        debt_n = await count_therapy_debt_sessions(self.db, instance.student_id)
        dsi = ctx_map.get("debt_settlement_included")
        if isinstance(dsi, str):
            include_debt = dsi.strip().lower() in ("1", "true", "yes", "on")
        else:
            include_debt = bool(dsi)
        if debt_n > 0:
            include_debt = True
        billable = n_sessions + (debt_n if include_debt else 0)
        computed = per * float(billable)
        if context.get("amount") is not None:
            try:
                amount = float(context["amount"])
            except (TypeError, ValueError):
                amount = computed
        elif include_debt and debt_n > 0:
            # مبلغ پرونده ممکن است بدون بدهی قدیمی باشد — با بدهی از محاسبهٔ تازه استفاده کن
            amount = computed
        elif ctx_map.get("amount") not in (None, "", 0) and float(ctx_map.get("amount") or 0) > 0:
            amount = float(ctx_map["amount"])
        elif ctx_map.get("total_amount") not in (None, "", 0) and float(ctx_map.get("total_amount") or 0) > 0:
            amount = float(ctx_map["total_amount"])
        else:
            amount = computed
        desc = "پیش‌فاکتور پرداخت جلسات درمان"
        if include_debt and debt_n > 0:
            desc = f"پیش‌فاکتور {n_sessions} جلسه آتی + تسویه {debt_n} جلسه بدهکار"
        await self.payment.generate_invoice(
            student_id=instance.student_id,
            amount=amount,
            description=desc,
            reference_id=instance.id,
            category="therapy",
        )
        ctx = _as_mapping(instance.context_data)
        ctx["invoice_amount"] = amount
        ctx["payment_amount_rial"] = int(round(float(amount) * 10))
        ctx["sessions_to_pay"] = n_sessions
        ctx["debt_sessions_count"] = debt_n
        ctx["debt_settlement_included"] = include_debt
        if include_debt and debt_n > 0:
            ctx["debt_amount_toman"] = per * float(debt_n)
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"payment_invoice_generated amount={amount} sessions={n_sessions} debt={debt_n if include_debt else 0}"

    async def _handle_zero_debt_if_paid(self, action: dict, instance: ProcessInstance, context: dict):
        stmt = delete(FinancialRecord).where(
            FinancialRecord.student_id == instance.student_id,
            FinancialRecord.record_type == "debt",
            FinancialRecord.reference_id == instance.id,
        )
        result = await self.db.execute(stmt)
        return f"zero_debt_cleared rows={getattr(result, 'rowcount', None)}"

    async def _handle_allocate_credit_to_sessions(self, action: dict, instance: ProcessInstance, context: dict):
        """تخصیص فقط از کیف‌پول درمان (نه سوپرویژن) به جلسات درمان."""
        from app.services.payment_service import LEDGER_THERAPY

        fd_c = await get_effective_financial_program_defaults(self.db)
        fee = float(fd_c.get("default_therapy_session_fee_toman") or self.payment.DEFAULT_SESSION_FEE)
        ctx = _as_mapping(instance.context_data)
        balance = float(ctx.get("session_credit_balance", 0))
        if balance <= 0:
            balance = float(context.get("amount") or 0)
        if balance <= 0:
            # مانده واقعی کیف درمان (بستانکاری fee_determination)
            therapy_bal = await self.payment.get_student_balance(
                instance.student_id, category=LEDGER_THERAPY
            )
            balance = max(0.0, float(therapy_bal.get("balance") or 0))
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
        return f"allocated_to_sessions n={n} remaining={ctx['session_credit_balance']} wallet={LEDGER_THERAPY}"

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
        from app.services.class_attendance_service import TUITION_PRESENT_BLOCK_PROCESS_CODES

        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["attendance_registration_unlocked"] = True
        # رفع قفل «حاضر» کلاس پس از تسویه قسط معوق
        if instance.process_code in TUITION_PRESENT_BLOCK_PROCESS_CODES or extra.get("class_present_blocked"):
            extra.pop("class_present_blocked", None)
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "attendance_registration_unlocked"

    async def _handle_set_installment_portal_lock(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["installment_portal_lock"] = {
            "active": True,
            "instance_id": str(instance.id),
            "process_code": instance.process_code,
            "locked_at": datetime.now(timezone.utc).isoformat(),
        }
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "installment_portal_lock_set"

    async def _handle_clear_installment_portal_lock(self, action: dict, instance: ProcessInstance, context: dict):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra.pop("installment_portal_lock", None)
        student.extra_data = extra
        flag_modified(student, "extra_data")
        return "installment_portal_lock_cleared"

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
        from app.services.admission_type_service import set_has_active_therapist_flag

        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        student.therapy_started = True
        set_has_active_therapist_flag(student, True)
        ctx = _as_mapping(instance.context_data)
        ctx.update(context or {})
        if ctx.get("therapist_id"):
            student.therapist_id = uuid.UUID(ctx["therapist_id"]) if isinstance(ctx["therapist_id"], str) else ctx["therapist_id"]
        if ctx.get("weekly_sessions") is not None:
            student.weekly_sessions = int(ctx["weekly_sessions"])
        # هم‌ترازی جلسات زمان‌بندی‌شده بدون therapist_id تا در پنل درمانگر لیست شوند
        if student.therapist_id:
            orphan_q = await self.db.execute(
                select(TherapySession).where(
                    TherapySession.student_id == student.id,
                    TherapySession.status == "scheduled",
                    TherapySession.therapist_id.is_(None),
                )
            )
            for ts in orphan_q.scalars().all():
                ts.therapist_id = student.therapist_id
            await self.db.flush()
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

        if target is not None and instance.process_code == "start_therapy":
            if (target.payment_status or "").strip() in ("", "pending"):
                target.payment_status = "paid"

        # ترجیح: لینک واقعی الوکام (در غیر این صورت فقط اگر الوکام خاموش است استاب محلی)
        from app.services.alocom_provision import (
            is_alocom_configured,
            is_stub_therapy_meeting_url,
            provision_therapy_session_alocom,
        )

        alocom_ready, agent_service_id = is_alocom_configured(settings)
        if url and is_stub_therapy_meeting_url(str(url)):
            url = None
        if alocom_ready and target is not None and not url:
            title = (
                action.get("title")
                or action.get("title_fa")
                or ctx.get("class_title")
                or ctx.get("alocom_event_title")
                or f"درمان آموزشی — جلسه اول"
            )
            duration_raw = action.get("duration_minutes") or ctx.get("duration_minutes")
            try:
                duration_minutes = int(duration_raw) if duration_raw is not None else 50
            except (TypeError, ValueError):
                duration_minutes = 50
            try:
                detail = await provision_therapy_session_alocom(
                    self.db,
                    session=target,
                    agent_service_id=agent_service_id,
                    title=str(title)[:500],
                    duration_minutes=duration_minutes,
                    fetch_student_event_link=bool(
                        action.get("fetch_student_event_link", ctx.get("fetch_student_event_link", True))
                    ),
                )
                url = (detail.get("meeting_url") or "").strip() or None
                ctx_store = _as_mapping(instance.context_data)
                ctx_store["alocom_last_provision"] = detail
                ctx_store["last_session_link"] = url
                ctx_store["meeting_url"] = url
                ctx_store["host_meeting_url"] = detail.get("host_meeting_url")
                instance.context_data = ctx_store
                flag_modified(instance, "context_data")
                await self.db.flush()
                return (
                    f"session_link_alocom url={url} session_id={target.id} "
                    f"event_id={detail.get('alocom_event_id')}"
                )
            except Exception as e:
                logger.exception(
                    "create_session_link Alocom provision failed instance=%s session=%s: %s",
                    instance.id,
                    getattr(target, "id", None),
                    e,
                )
                ctx_err = _as_mapping(instance.context_data)
                ctx_err["alocom_last_error"] = str(e)
                instance.context_data = ctx_err
                flag_modified(instance, "context_data")
                # وقتی الوکام فعال است لینک ساختگی ذخیره نکن — تا ensure بعدی بتواند بسازد
                if target and is_stub_therapy_meeting_url(target.meeting_url):
                    target.meeting_url = None
                    target.host_meeting_url = None
                    target.meeting_provider = None
                    target.links_unlocked = False
                await self.db.flush()
                return f"session_link_alocom_failed: {e}"

        if alocom_ready and not url:
            return "session_link_pending_alocom"

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
        ctx_store = _as_mapping(instance.context_data)
        ctx_store["last_session_link"] = url
        ctx_store["meeting_url"] = url
        instance.context_data = ctx_store
        flag_modified(instance, "context_data")
        await self.db.flush()
        return f"session_link_set url={url} session_id={getattr(target, 'id', None)}"

    async def _resolve_system_actor_id_for_actions(self) -> uuid.UUID:
        r = await self.db.execute(select(User.id).where(User.role == "admin").limit(1))
        row = r.scalars().first()
        if row:
            return row
        r = await self.db.execute(select(User.id).limit(1))
        row = r.scalars().first()
        return row if row else uuid.uuid4()

    async def _handle_apply_start_therapy_session_schedule(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """پس از انتخاب دانشجو از شیت: تاریخ شروع، قانون ۲۴ ساعت، بذر جلسات، انتقال به payment_pending."""
        from app.core.engine import StateMachineEngine
        from app.services.educational_therapist_slot_service import _parse_slot_ids
        from app.models.operational_models import EducationalTherapistSlot

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

        def _next_on_or_after(d: date, weekday: int) -> date:
            delta = (int(weekday) - d.weekday()) % 7
            return d + timedelta(days=delta)

        student = await self._get_student(instance.student_id)
        today = datetime.now(timezone.utc).date()

        slot_ids = _parse_slot_ids(
            merged.get("booked_slot_ids") or merged.get("slot_ids")
        )
        slot_rows: List[EducationalTherapistSlot] = []
        if slot_ids:
            slot_rows = list(
                (
                    await self.db.execute(
                        select(EducationalTherapistSlot).where(
                            EducationalTherapistSlot.id.in_(slot_ids)
                        )
                    )
                ).scalars().all()
            )
        slot_weekdays = sorted({int(s.day_of_week) for s in slot_rows}) if slot_rows else []

        first = _parse_first_date(merged.get("first_session_date"))
        if first is None:
            if slot_weekdays:
                first = min(_next_on_or_after(today, wd) for wd in slot_weekdays)
            else:
                first = today + timedelta(days=1)

        ws_raw = merged.get("weekly_sessions")
        if ws_raw is None and student is not None:
            ws_raw = student.weekly_sessions
        try:
            ws = int(ws_raw) if ws_raw is not None else (len(slot_weekdays) or 1)
        except (TypeError, ValueError):
            ws = len(slot_weekdays) or 1
        ws = max(1, min(ws, 12))

        tid = merged.get("therapist_id")
        if not tid and student is not None and student.therapist_id:
            tid = str(student.therapist_id)
        if not tid and slot_rows:
            tid = str(slot_rows[0].therapist_user_id)
        if not tid:
            raise ValueError("therapist_id در پروندهٔ این مرحله ثبت نشده است.")

        try:
            tid_uuid = uuid.UUID(str(tid))
        except (TypeError, ValueError) as e:
            raise ValueError("شناسهٔ درمانگر نامعتبر است.") from e

        if first <= today:
            bump_from = today + timedelta(days=1)
            if slot_weekdays:
                first = min(_next_on_or_after(bump_from, wd) for wd in slot_weekdays)
            else:
                first = bump_from

        from app.services.therapy_session_schedule import (
            expand_session_dates_for_slots,
            expand_weekly_session_dates,
            fallback_weekdays,
            resolve_term_end_date,
        )
        from app.utils.shamsi_calendar_utils import TEHRAN

        note_tag = f"start_therapy_instance:{instance.id}"
        final_session_dates: List[date] = []
        weekdays_for_seed = list(slot_weekdays) if slot_weekdays else fallback_weekdays(first, ws)
        term_end = await resolve_term_end_date(self.db, student, fallback_from=first)
        if term_end < first:
            term_end = first + timedelta(weeks=16)

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
            # بذر جلسات تا پایان ترم (با week_interval هر اسلات)
            if slot_rows:
                session_dates = expand_session_dates_for_slots(first, slot_rows, term_end)
            else:
                session_dates = expand_weekly_session_dates(first, weekdays_for_seed, term_end)
            if not session_dates:
                session_dates = [_next_on_or_after(first, weekdays_for_seed[0])]

            slot_by_weekday = {int(s.day_of_week): s for s in slot_rows} if slot_rows else {}

            created_sessions: List[TherapySession] = []
            for d in session_dates:
                starts_at = None
                slot = slot_by_weekday.get(d.weekday())
                if slot is not None and getattr(slot, "start_local_time", None) is not None:
                    starts_at = datetime.combine(
                        d, slot.start_local_time, tzinfo=TEHRAN
                    ).astimezone(timezone.utc)
                ts = TherapySession(
                    id=uuid.uuid4(),
                    student_id=instance.student_id,
                    therapist_id=tid_uuid,
                    session_date=d,
                    session_starts_at=starts_at,
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
                final_session_dates = session_dates
                break
            first = first + timedelta(days=7)
        else:
            logger.warning(
                "start_therapy: 24h rule not satisfied after bumps instance=%s",
                instance.id,
            )
            final_session_dates = session_dates if session_dates else [first]

        effective_first = min(final_session_dates) if final_session_dates else first

        fd_st = await get_effective_financial_program_defaults(self.db)
        fee = int(fd_st["start_therapy_first_session_fee_rial"])
        if merged.get("payment_amount_rial") is not None:
            try:
                fee = int(merged["payment_amount_rial"])
            except (TypeError, ValueError):
                pass

        ctx = _as_mapping(instance.context_data)
        ctx.update(merged)
        ctx["therapist_id"] = str(tid_uuid)
        ctx["weekly_sessions"] = ws
        ctx["first_session_date"] = effective_first.isoformat()
        ctx["first_session_date_effective"] = effective_first.isoformat()
        ctx["therapy_schedule_term_end"] = term_end.isoformat()
        ctx["therapy_sessions_seeded_count"] = len(final_session_dates)
        ctx["payment_amount_rial"] = fee
        ctx["start_therapy_sessions_seeded"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        # از همین مرحله درمانگر روی پروندهٔ دانشجو ثبت شود تا قبل از پرداخت هم در پنل دیده شود
        if student is not None:
            student.therapist_id = tid_uuid
            student.weekly_sessions = ws
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
        return (
            f"start_therapy_schedule_applied fee_rial={fee} "
            f"sessions={len(final_session_dates)} term_end={term_end.isoformat()} "
            f"to_state={res.to_state}"
        )

    async def _handle_prefill_return_context(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.return_to_full_education_service import build_return_context

        if instance.process_code != "return_to_full_education":
            return "skip_not_return_to_full_education"
        ctx = await build_return_context(
            self.db, instance.student_id, _as_mapping(instance.context_data),
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await self.db.flush()
        return "prefill_return_context"

    async def _handle_apply_return_therapy_session_schedule(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.core.engine import StateMachineEngine
        from app.services.return_to_full_education_service import (
            apply_24h_bump,
            therapy_payment_fee_rial,
            validate_weekly_sessions,
        )

        if instance.process_code != "return_to_full_education":
            return "skip_not_return_to_full_education"

        merged = {**_as_mapping(instance.context_data), **(context or {})}

        def _parse_first_date(val):
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
        course_type = str(merged.get("course_type") or (student.course_type if student else "") or "introductory")
        ws = int(merged.get("weekly_sessions") or 1)
        err = validate_weekly_sessions(course_type, ws)
        if err:
            raise ValueError(err)

        first = _parse_first_date(merged.get("first_session_date"))
        if first is None:
            first = datetime.now(timezone.utc).date() + timedelta(days=1)
        first = await apply_24h_bump(first, instance.student_id, self.db)

        tid = merged.get("therapist_id")
        if not tid:
            raise ValueError("therapist_id در پروندهٔ این مرحله ثبت نشده است.")
        tid_uuid = uuid.UUID(str(tid))

        fee = await therapy_payment_fee_rial(self.db, merged)
        ctx = _as_mapping(instance.context_data)
        ctx.update(merged)
        ctx["therapist_id"] = str(tid_uuid)
        ctx["weekly_sessions"] = ws
        ctx["therapy_first_session_at"] = first.isoformat()
        ctx["therapy_payment_amount_rial"] = fee
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await self.db.flush()

        engine = StateMachineEngine(self.db)
        actor = await self._resolve_system_actor_id_for_actions()
        res = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="therapy_24h_passed",
            actor_id=actor,
            actor_role="system",
            payload={},
        )
        if not res.success:
            logger.error(
                "return_to_full_education therapy_24h_passed failed instance=%s err=%s",
                instance.id,
                res.error,
            )
            return f"nested_transition_failed: {res.error}"
        await self.db.refresh(instance)
        return f"return_therapy_schedule_applied fee_rial={fee}"

    async def _handle_apply_return_supervision_schedule(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.core.engine import StateMachineEngine
        from app.services.return_to_full_education_service import (
            apply_24h_bump,
            supervision_payment_fee_rial,
        )

        if instance.process_code != "return_to_full_education":
            return "skip_not_return_to_full_education"

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        sid = merged.get("supervisor_id")
        if not sid:
            raise ValueError("supervisor_id در پرونده ثبت نشده است.")

        def _parse_first_date(val):
            if val is None:
                return None
            s = str(val).strip()
            if not s:
                return None
            try:
                return date.fromisoformat(s[:10])
            except (TypeError, ValueError):
                return None

        first = _parse_first_date(merged.get("first_supervision_date"))
        if first is None:
            first = datetime.now(timezone.utc).date() + timedelta(days=1)
        first = await apply_24h_bump(first, instance.student_id, self.db)

        fee = await supervision_payment_fee_rial(self.db, merged)
        ctx = _as_mapping(instance.context_data)
        ctx.update(merged)
        ctx["supervisor_id"] = str(sid)
        ctx["supervision_first_session_at"] = first.isoformat()
        ctx["supervision_payment_amount_rial"] = fee
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await self.db.flush()

        engine = StateMachineEngine(self.db)
        actor = await self._resolve_system_actor_id_for_actions()
        res = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="supervision_24h_passed",
            actor_id=actor,
            actor_role="system",
            payload={},
        )
        if not res.success:
            logger.error(
                "return_to_full_education supervision_24h_passed failed instance=%s err=%s",
                instance.id,
                res.error,
            )
            return f"nested_transition_failed: {res.error}"
        await self.db.refresh(instance)
        return f"return_supervision_schedule_applied fee_rial={fee}"

    async def _handle_apply_full_leave_therapist_decision(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        if instance.process_code != "full_education_leave":
            return "skip_not_full_education_leave"
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        decision = str(merged.get("therapist_decision") or "").strip()
        if decision == "release_slot":
            return await self._handle_auto_release_therapist_slot(action, instance, context)
        if decision == "continue_general":
            student = await self._get_student(instance.student_id)
            if student:
                extra = _as_mapping(student.extra_data)
                extra["therapy_relationship"] = "general_therapy"
                extra["transferred_to_general_therapy_at"] = datetime.now(timezone.utc).isoformat()
                student.extra_data = extra
                flag_modified(student, "extra_data")
            ctx = _as_mapping(instance.context_data)
            ctx["therapist_decision"] = "continue_general"
            ctx["therapy_continues_as_general"] = True
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            return "therapist_continue_general"
        return "therapist_decision_missing"

    async def _handle_set_full_education_leave_flag(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        now = datetime.now(timezone.utc)
        extra["on_full_education_leave"] = True
        extra["full_education_leave_active"] = True
        extra["full_education_leave_started_at"] = now.isoformat()
        merged = {**_as_mapping(instance.context_data), **(context or {})}
        lt = merged.get("leave_terms")
        try:
            terms = int(lt) if lt is not None else None
        except (TypeError, ValueError):
            terms = None
        if terms is not None:
            extra["full_education_leave_terms"] = terms
        student.extra_data = extra
        flag_modified(student, "extra_data")
        ctx = _as_mapping(instance.context_data)
        ctx["leave_activated_at"] = now.isoformat()
        if terms is not None:
            ctx["leave_terms"] = terms
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "set_full_education_leave_flag"

    async def _handle_apply_full_leave_intern_effects(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.full_education_leave_service import apply_intern_effects

        if instance.process_code != "full_education_leave":
            return "skip_not_full_education_leave"
        result = await apply_intern_effects(self.db, instance)
        if result == "not_intern_skipped":
            return result
        try:
            await self._handle_start_process(
                {"process_code": "intern_bulk_patient_referral", "type": "start_process"},
                instance,
                context,
            )
        except Exception:
            logger.exception(
                "full_education_leave intern_bulk_patient_referral start failed instance=%s",
                instance.id,
            )
        return "apply_full_leave_intern_effects"

    async def _handle_notify_therapy_coordination(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.full_education_leave_service import (
            THERAPY_COORD_SMS_FA,
            build_leave_context,
        )

        if instance.process_code != "full_education_leave":
            return "skip_not_full_education_leave"
        ctx = await build_leave_context(
            self.db, instance.student_id, _as_mapping(instance.context_data),
        )
        if not ctx.get("has_active_therapist"):
            return "notify_therapy_coordination_skipped_no_therapist"
        ctx["therapy_coord_notified_at"] = datetime.now(timezone.utc).isoformat()
        ctx["student_portal_alert_fa"] = THERAPY_COORD_SMS_FA
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await self._handle_notification(
            {
                "type": "notification",
                "notification_type": "sms",
                "template": "leave_approved",
                "template_text_fa": THERAPY_COORD_SMS_FA,
                "recipients": ["student"],
            },
            instance,
            context,
        )
        return "notify_therapy_coordination"

    async def _handle_auto_release_therapist_slot(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        from app.services.admission_type_service import set_has_active_therapist_flag

        prev = str(student.therapist_id) if student.therapist_id else None
        student.therapist_id = None
        student.therapy_started = False
        set_has_active_therapist_flag(student, False)
        extra = _as_mapping(student.extra_data)
        extra["therapy_relationship"] = "released_on_full_leave"
        extra["therapist_auto_released_at"] = datetime.now(timezone.utc).isoformat()
        log = list(extra.get("therapist_slot_release_log") or [])
        log.append({
            "at": datetime.now(timezone.utc).isoformat(),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "source": "full_education_leave_sla",
            "therapist_id": prev,
        })
        extra["therapist_slot_release_log"] = log
        student.extra_data = extra
        flag_modified(student, "extra_data")
        ctx = _as_mapping(instance.context_data)
        ctx["therapist_decision"] = "release_slot"
        ctx["therapist_auto_released"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "auto_release_therapist_slot"

    async def _handle_clear_full_education_leave_flag(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        student = await self._get_student(instance.student_id)
        if student:
            extra = _as_mapping(student.extra_data)
            extra["on_full_education_leave"] = False
            extra["full_education_leave_active"] = False
            student.extra_data = extra
            flag_modified(student, "extra_data")
        ctx = _as_mapping(instance.context_data)
        ctx["return_completed_at"] = datetime.now(timezone.utc).isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        if instance.process_code == "return_to_full_education":
            try:
                from app.core.engine import StateMachineEngine
                from app.services.full_education_leave_service import complete_leave_on_return

                engine = StateMachineEngine(self.db)
                actor = uuid.UUID(str(context.get("actor_id"))) if context and context.get("actor_id") else uuid.UUID("00000000-0000-0000-0000-000000000001")
                await complete_leave_on_return(self.db, engine, instance.student_id, actor)
            except Exception:
                logger.exception(
                    "complete full_education_leave on return failed student=%s",
                    instance.student_id,
                )
        return "clear_full_education_leave_flag"

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
        from app.services.admission_type_service import set_has_active_therapist_flag

        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        student.therapy_started = False
        if action.get("clear_therapist", True):
            student.therapist_id = None
        set_has_active_therapist_flag(student, False)
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
        student = await self._get_student(instance.student_id)
        ctx = _as_mapping(instance.context_data)
        blocks = []
        attendance = ctx.get("current_supervision_block_attendance")
        if student:
            extra = _as_mapping(student.extra_data)
            lms = _as_mapping(extra.get("lms"))
            blocks = list(lms.get("supervision_blocks") or [])
            if attendance is None:
                active = next(
                    (b for b in blocks if isinstance(b, dict) and b.get("status") == "active"),
                    blocks[-1] if blocks else None,
                )
                if isinstance(active, dict) and active.get("hours") is not None:
                    try:
                        attendance = int(active.get("hours") or 0)
                    except (TypeError, ValueError):
                        attendance = 0
                elif ctx.get("current_supervision_block_attendance") is None:
                    attendance = int(extra.get("supervision_block_attendance") or lms.get("current_block_hours") or 0)
        ctx["supervision_history"] = blocks
        ctx["supervision_blocks"] = blocks
        if attendance is not None:
            ctx["current_supervision_block_attendance"] = int(attendance)
        ctx.setdefault("ui_hints", []).append({"action": "display_supervision_history", "payload": {}})
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"supervision_history_displayed n={len(blocks)}"

    async def _handle_display_available_supervisor_slots(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        from app.services.educational_therapist_slot_service import list_available_grouped_by_supervisor
        from app.services.workflow import portal_notifications as _svc_portal

        student = await self._get_student(instance.student_id)
        course_type = (student.course_type if student else None) or "introductory"
        grouped = await list_available_grouped_by_supervisor(self.db, course_type=course_type)
        supervisors = grouped.get("supervisors") or grouped.get("therapists") or []
        by_sup: dict = {}
        for row in supervisors:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("id") or "")
            by_sup[sid or row.get("label_fa") or "supervisor"] = row.get("slots") or []
        ctx = _as_mapping(instance.context_data)
        ctx["available_supervisor_slots"] = by_sup
        ctx["supervisor_slots"] = by_sup
        ctx["displayed_supervisor_slots"] = by_sup
        ctx["available_supervisors"] = supervisors
        if not ctx.get("mandatory_message_fa"):
            ctx["mandatory_message_fa"] = (
                "دانشجوی گرامی، برای پرداخت جهت حضور در 50مین جلسه سوپرویژن باید اول زمان و "
                "سوپرویژن بعدی خود را انتخاب کنید تا قادر به پرداخت برای حضور در 50مین جلسه سوپرویژن باشید"
            )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await _svc_portal.handle(
            self.db,
            instance,
            {"type": "display_available_supervisor_slots"},
            context or {},
        )
        return f"supervisor_slots_loaded n={len(supervisors)}"

    async def _handle_remove_slot_from_available(self, action: dict, instance: ProcessInstance, context: dict):
        from app.services.educational_therapist_slot_service import (
            book_slots_from_context,
            build_slot_summary_for_context,
            _parse_slot_ids,
        )
        from app.models.operational_models import EducationalTherapistSlot
        from sqlalchemy import select

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        # Ensure weekly count for supervision = 1
        merged.setdefault("weekly_sessions", 1)
        merged.setdefault("selected_supervision_weekly_count", 1)
        result = await book_slots_from_context(
            self.db,
            instance_id=instance.id,
            student_id=instance.student_id,
            context=merged,
            therapist_id_key="new_supervisor_id",
            slot_ids_key="slot_ids",
            weekly_sessions_key="weekly_sessions",
            skip_weekly_course_rule=True,
        )
        ctx = _as_mapping(instance.context_data)
        ctx["supervisor_slot_removed_from_available"] = True
        slot_ids = merged.get("slot_ids")
        ids = _parse_slot_ids(slot_ids)
        if ids:
            rows = (
                await self.db.execute(
                    select(EducationalTherapistSlot).where(EducationalTherapistSlot.id.in_(ids))
                )
            ).scalars().all()
            summary = build_slot_summary_for_context(rows)
            ctx.update(summary)
            ctx["booked_slot_ids"] = summary.get("slot_ids")
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return result if result != "skip_no_slot_ids" else "slot_removed_from_available_sheet"

    async def _handle_prepare_supervision_block_payment(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """مبلغ جلسه اول بلوک جدید / جلسه ۵۰ام را برای SepPaymentPanel آماده می‌کند."""
        from app.services.return_to_full_education_service import supervision_payment_fee_rial

        if instance.process_code != "supervision_block_transition":
            return "skip"
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        fee_rial = await supervision_payment_fee_rial(self.db, merged)
        purpose = (action.get("purpose") or merged.get("supervision_payment_purpose") or "new_block_first").strip()
        ctx["payment_amount_rial"] = int(fee_rial)
        ctx["invoice_amount"] = float(fee_rial) / 10.0
        ctx["supervision_payment_amount_rial"] = int(fee_rial)
        ctx["supervision_payment_purpose"] = purpose
        if purpose == "session_50th":
            ctx["payment_unlocked_for_50th_session"] = True
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"supervision_block_payment_ready purpose={purpose} fee_rial={fee_rial}"

    async def _handle_book_supervision_block_slots(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """رزرو اسلات سوپروایزر هنگام انتخاب در supervision_block_transition."""
        from app.services.educational_therapist_slot_service import (
            book_slots_from_context,
            build_slot_summary_for_context,
            _parse_slot_ids,
        )
        from app.models.operational_models import EducationalTherapistSlot
        from sqlalchemy import select

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        merged.setdefault("weekly_sessions", 1)
        merged.setdefault("selected_supervision_weekly_count", 1)
        # Map supervisor picker field if form used therapist_id alias
        if not merged.get("new_supervisor_id") and merged.get("therapist_id"):
            merged["new_supervisor_id"] = merged["therapist_id"]
        result = await book_slots_from_context(
            self.db,
            instance_id=instance.id,
            student_id=instance.student_id,
            context=merged,
            therapist_id_key="new_supervisor_id",
            slot_ids_key="slot_ids",
            weekly_sessions_key="weekly_sessions",
            skip_weekly_course_rule=True,
        )
        ctx = _as_mapping(instance.context_data)
        if merged.get("new_supervisor_id"):
            ctx["new_supervisor_id"] = str(merged["new_supervisor_id"])
            ctx["supervisor_id"] = str(merged["new_supervisor_id"])
        ctx["weekly_sessions"] = 1
        ctx["selected_supervision_weekly_count"] = 1
        ids = _parse_slot_ids(merged.get("slot_ids"))
        if ids:
            rows = (
                await self.db.execute(
                    select(EducationalTherapistSlot).where(EducationalTherapistSlot.id.in_(ids))
                )
            ).scalars().all()
            summary = build_slot_summary_for_context(rows)
            ctx.update(summary)
            ctx["booked_slot_ids"] = summary.get("slot_ids")
            if rows:
                ctx["requested_start_date"] = ctx.get("requested_start_date") or ctx.get("first_session_date")
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return result

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
        if instance.process_code == "ta_track_completion":
            from app.services.ta_track_portfolio_service import apply_track_completion_from_context

            result = apply_track_completion_from_context(student, merged)
            return result
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
        from app.services.tuition_installment_service import (
            apply_tuition_payment_context,
            mark_installment_paid,
            refresh_instance_tuition_context,
        )

        system_actor = uuid.UUID("00000000-0000-0000-0000-000000000001")
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        mode = action.get("mode", "initial_payment")

        from app.services.installment_settings_service import get_installment_policy

        policy = await get_installment_policy(self.db)
        term2_installment_gap_days = int(policy.get("term2_installment_gap_days") or 25)

        merged = await refresh_instance_tuition_context(
            self.db,
            instance.process_code,
            instance.current_state_code or "",
            merged,
        )

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
                plan = merged.get("installment_plan") or []
                if plan and len(plan) > 1:
                    merged["next_installment_due_at"] = plan[1].get("due_at") or merged.get(
                        "next_installment_due_at"
                    )
        elif mode == "installment_paid":
            amount_rial = context.get("amount_rial")
            if amount_rial is None and context.get("amount") is not None:
                try:
                    amount_rial = int(round(float(context["amount"]) * 10))
                except (TypeError, ValueError):
                    amount_rial = 0
            else:
                try:
                    amount_rial = int(amount_rial or 0)
                except (TypeError, ValueError):
                    amount_rial = 0
            merged = mark_installment_paid(
                merged,
                str(context.get("ref_id") or context.get("payment_ref") or ""),
                amount_rial,
                gap_days=term2_installment_gap_days,
            )

        merged = apply_tuition_payment_context(merged, gap_days=term2_installment_gap_days)

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
        code = (
            action.get("process_code")
            or action.get("subprocess_code")
            or action.get("subprocess")
            or "violation_registration"
        )
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

    # ─── Workflow service delegations (Services A–I) ─────────────
    # These replace the legacy log-only _handle_external_integration stub with
    # real, domain-mutating behavior implemented in app/services/workflow/.

    async def _handle_svc_portal(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_portal.handle(self.db, instance, action, context)

    async def _handle_svc_lms(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_lms.handle(self.db, instance, action, context)

    async def _handle_svc_document(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_document.handle(self.db, instance, action, context)

    async def _handle_svc_evaluation(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_evaluation.handle(self.db, instance, action, context)

    async def _handle_svc_capacity(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_capacity.handle(self.db, instance, action, context)

    async def _handle_svc_termination(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_termination.handle(self.db, instance, action, context)

    async def _handle_svc_calendar(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_calendar.handle(self.db, instance, action, context)

    async def _handle_publish_term_course_offerings(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        from app.core.engine import StateMachineEngine
        from app.services.term_course_offering_service import publish_offerings_from_prep

        merged = StateMachineEngine._as_mapping(context)
        if instance.context_data:
            inst_ctx = StateMachineEngine._as_mapping(instance.context_data)
            inst_ctx.update(merged)
            merged = inst_ctx
        result = await publish_offerings_from_prep(self.db, instance, merged)
        return f"publish_term_course_offerings count={result.get('count', 0)}"

    async def _handle_sync_financial_defaults_from_prep(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """همگام‌سازی شهریهٔ آماده‌سازی ترم با پیش‌فرض‌های داشبورد مالی."""
        from app.core.engine import StateMachineEngine
        from app.services.financial_program_defaults_service import sync_term_tuition_from_prep_context

        merged = StateMachineEngine._as_mapping(context)
        if instance.context_data:
            inst_ctx = StateMachineEngine._as_mapping(instance.context_data)
            inst_ctx.update(merged)
            merged = inst_ctx
        result = await sync_term_tuition_from_prep_context(self.db, merged)
        from app.services.financial_program_defaults_service import PREP_FINANCIAL_FORM_KEYS

        keys = []
        for k in PREP_FINANCIAL_FORM_KEYS:
            try:
                n = float(result.get(k) or 0)
            except (TypeError, ValueError):
                continue
            if n > 0:
                keys.append(k)
        return f"sync_financial_defaults_from_prep keys={','.join(keys) or 'none'}"

    async def _handle_sync_institute_license_from_prep(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """همگام‌سازی شماره پروانه فعالیت انستیتو وقتی معاون «تغییر کرده» را ثبت کند."""
        from app.core.engine import StateMachineEngine
        from app.services.institute_activity_license_service import (
            sync_activity_license_from_prep_context,
        )

        merged = StateMachineEngine._as_mapping(context)
        if instance.context_data:
            inst_ctx = StateMachineEngine._as_mapping(instance.context_data)
            inst_ctx.update(merged)
            merged = inst_ctx
        result = await sync_activity_license_from_prep_context(self.db, merged)
        number = result.get("activity_license_number") or ""
        return f"sync_institute_license_from_prep number={number or 'unchanged'}"

    async def _handle_svc_gate(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_gate.handle(self.db, instance, action, context)

    async def _handle_svc_role(self, action: dict, instance: ProcessInstance, context: dict):
        return await _svc_role.handle(self.db, instance, action, context)

    async def _handle_external_integration(self, action: dict, instance: ProcessInstance, context: dict):
        """یکپارچه‌سازی LMS/وب‌هوک + راهنمای UI؛ برای اکشن‌های «ثبت در LMS» و مشابه."""
        name = action.get("type", "unknown")
        detail = {k: v for k, v in action.items() if k != "type"}
        append_integration_event(instance, name, {"detail": detail, "context_keys": list((context or {}).keys())})
        ctx = _as_mapping(instance.context_data)
        hint = {"action": name, "detail": detail}
        hints = ctx.setdefault("ui_hints", [])
        # از تکرار همان راهنمای UI هنگام اجرای مجدد ترنزیشن جلوگیری کن
        if hint not in hints:
            hints.append(hint)
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

    async def _handle_record_class_cancellation(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """اعمال کنسلی کلاس — فرایند ۵۶."""
        from app.services.class_session_cancellation_service import apply_class_cancellation

        actor_id = context.get("actor_id") or context.get("triggered_by")
        result = await apply_class_cancellation(self.db, instance, actor_id)
        return f"class_cancellation_applied n={result.get('students_updated', 0)}"

    async def _handle_record_process_artifact(self, action: dict, instance: ProcessInstance, context: dict):
        """Generic artifact recorder for record_* actions (grades, attendance, evaluations, etc.)."""
        from datetime import datetime, timezone

        atype = (action.get("type") or "record_artifact").strip()
        ctx = _as_mapping(instance.context_data)
        now_iso = datetime.now(timezone.utc).isoformat()
        ctx["artifact"] = {"produced": True, "action_type": atype, "at": now_iso}
        ctx.setdefault("submitted_at", now_iso)

        if atype == "record_course_grades" or ctx.get("students_grades"):
            student = await self._get_student(instance.student_id)
            if student:
                extra = _as_mapping(student.extra_data)
                lms = _as_mapping(extra.get("lms"))
                grades = ctx.get("students_grades")
                if isinstance(grades, list):
                    enrolled = list(lms.get("enrolled_courses") or [])
                    by_id = {str(g.get("student_id")): g for g in grades if isinstance(g, dict)}
                    updated = []
                    for row in enrolled:
                        if not isinstance(row, dict):
                            updated.append(row)
                            continue
                        sid = str(row.get("student_id") or instance.student_id)
                        g = by_id.get(sid) or {}
                        merged = {**row}
                        if g.get("grade") not in (None, ""):
                            merged["grade"] = g.get("grade")
                            merged["status_fa"] = merged.get("status_fa") or "قفل"
                            merged["grades_locked"] = True
                            merged["grade_locked"] = True
                        updated.append(merged)
                    if not enrolled and grades:
                        updated = list(grades)
                    lms["enrolled_courses"] = updated
                    lms["grades_locked"] = True
                    try:
                        lms["grades_pending"] = max(0, int(lms.get("grades_pending") or 0) - 1)
                    except (TypeError, ValueError):
                        lms["grades_pending"] = 0
                    extra["lms"] = lms
                    student.extra_data = extra
                    flag_modified(student, "extra_data")

        if atype == "record_class_attendance":
            merged_att = {**ctx, **(context or {})}
            rows = merged_att.get("students_attendance") or []
            if rows:
                from app.services.class_attendance_service import apply_session_attendance

                course_code = (
                    merged_att.get("course_code")
                    or merged_att.get("lesson_course_label")
                    or merged_att.get("course_id")
                    or merged_att.get("lesson_name")
                    or ""
                )
                summary = await apply_session_attendance(
                    self.db,
                    str(course_code),
                    str(merged_att.get("session_date") or ""),
                    rows,
                    course_type=merged_att.get("course_type"),
                    actor_id=instance.started_by or instance.student_id,
                    session_number=merged_att.get("session_number"),
                )
                ctx["attendance_summary"] = summary
                ctx["course_code"] = summary.get("course_code") or course_code
                ctx["course_type"] = summary.get("course_type") or merged_att.get("course_type")
                ctx["students_attendance"] = rows
                if merged_att.get("session_date"):
                    ctx["session_date"] = merged_att["session_date"]
                if merged_att.get("lesson_name"):
                    ctx["lesson_name"] = merged_att["lesson_name"]
                inst_sid = str(instance.student_id)
                per = (summary.get("per_student") or {}).get(inst_sid) or {}
                if per.get("student_absence_count") is not None:
                    ctx["student_absence_count"] = per["student_absence_count"]
                elif merged_att.get("student_absence_count") is not None:
                    ctx["student_absence_count"] = merged_att["student_absence_count"]

        if atype == "record_evaluation_closed" and instance.process_code == "student_instructor_evaluation":
            from app.services.student_instructor_evaluation_service import aggregate_term_results
            from app.services.institute_calendar_service import get_active_calendar

            term_code = str(ctx.get("term_code") or "").strip()
            if not term_code:
                cal = await get_active_calendar(self.db)
                term_code = cal.term_code if cal else "default"
            agg = await aggregate_term_results(self.db, term_code)
            ctx["evaluation_aggregated_at"] = agg.get("aggregated_at")
            ctx["evaluation_term_code"] = term_code

        if atype == "record_session_prep":
            merged = {**ctx, **(context or {})}
            ctx["session_time_registered"] = True
            for key in ("session_date", "session_time", "instructor_id", "therapist_id", "course_code"):
                if merged.get(key) not in (None, ""):
                    ctx[key] = merged[key]

        instance.context_data = ctx
        flag_modified(instance, "context_data")

        student = await self._get_student(instance.student_id)
        if student:
            extra = _as_mapping(student.extra_data)
            extra["student_portal_result_recorded"] = True
            pa = _as_mapping(extra.get("process_artifacts"))
            pa[instance.process_code] = {"at": now_iso, "action": atype}
            extra["process_artifacts"] = pa
            student.extra_data = extra
            flag_modified(student, "extra_data")
        return atype

    async def _handle_record_student_performance_traits(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        """ثبت ویژگی‌های مثبت/منفی سوال ۷ و ۸ در گزارش عملکرد دانشجو."""
        from datetime import datetime, timezone

        from app.services.trait_catalog_service import trait_label

        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        now_iso = datetime.now(timezone.utc).isoformat()
        source = (action.get("payload") or {}).get("source") or instance.process_code

        reporter_name = merged.get("instructor_name") or merged.get("reporter_name") or "مدرس"
        reporter_role = "instructor"

        entries: list[dict] = []

        if merged.get("q7_has_positive") == "yes":
            traits_raw = merged.get("q7_positive_traits") or []
            traits = [str(t) for t in traits_raw] if isinstance(traits_raw, list) else []
            if traits:
                entries.append({
                    "at": now_iso,
                    "kind": "positive",
                    "traits": traits,
                    "trait_labels_fa": [trait_label("positive", t) for t in traits],
                    "note": (merged.get("q7_positive_note") or "").strip() or None,
                    "reporter_role": reporter_role,
                    "reporter_name": reporter_name,
                    "process_code": source,
                    "question": "q7",
                })

        if merged.get("q8_has_negative") == "yes":
            traits_raw = merged.get("q8_negative_traits") or []
            traits = [str(t) for t in traits_raw] if isinstance(traits_raw, list) else []
            if traits:
                entries.append({
                    "at": now_iso,
                    "kind": "negative",
                    "traits": traits,
                    "trait_labels_fa": [trait_label("negative", t) for t in traits],
                    "note": (merged.get("q8_negative_note") or "").strip() or None,
                    "reporter_role": reporter_role,
                    "reporter_name": reporter_name,
                    "process_code": source,
                    "question": "q8",
                })

        ctx["performance_traits_recorded_at"] = now_iso
        ctx["performance_traits_snapshot"] = entries
        instance.context_data = ctx
        flag_modified(instance, "context_data")

        student = await self._get_student(instance.student_id)
        if student and entries:
            extra = _as_mapping(student.extra_data)
            log = list(extra.get("monitoring_performance_log") or [])
            log.extend(entries)
            extra["monitoring_performance_log"] = log
            student.extra_data = extra
            flag_modified(student, "extra_data")

        return "record_student_performance_traits"

    _VIOLATION_TYPE_FA = {
        "professional": "حرفه‌ای",
        "educational": "آموزشی",
        "disciplinary": "انضباطی",
    }
    _VIOLATION_VERDICT_FA = {
        "cleared": "مبرا",
        "notice": "تذکر",
        "warning_1": "اخطار مرحله اول",
        "warning_2": "اخطار مرحله دوم",
        "warning_3": "اخطار مرحله سوم",
        "suspension_next_term": "تعلیق از ترم بعد",
        "suspension_immediate": "تعلیق آنی",
        "refer_education": "ارجاع به کمیته آموزش",
        "no_expulsion": "عدم اخراج",
        "expulsion": "اخراج از آموزش",
    }

    async def _handle_record_violation_performance_entry(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        """ثبت حکم/تخلف در جدول گزارش عملکرد دانشجو."""
        ctx = _as_mapping(instance.context_data)
        merged = {**ctx, **(context or {})}
        now_iso = datetime.now(timezone.utc).isoformat()
        verdict = merged.get("verdict") or merged.get("final_decision")
        vtype = merged.get("violation_type")
        entry = {
            "at": now_iso,
            "kind": "violation",
            "violation_type": vtype,
            "violation_type_fa": self._VIOLATION_TYPE_FA.get(str(vtype or ""), vtype),
            "description": (merged.get("description") or "").strip() or None,
            "verdict_action": verdict,
            "verdict_action_fa": self._VIOLATION_VERDICT_FA.get(str(verdict or ""), verdict),
            "compensatory_conditions": (merged.get("compensatory_conditions") or "").strip() or None,
            "final_status": merged.get("final_decision"),
            "final_status_fa": self._VIOLATION_VERDICT_FA.get(
                str(merged.get("final_decision") or ""), merged.get("final_decision")
            ),
            "reporter_name": merged.get("reporter_name") or "کمیته نظارت",
            "reporter_role": "monitoring_committee",
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "source_process_code": merged.get("source_process_code"),
            "source_reason": merged.get("source_reason"),
        }
        ctx["verdict_action"] = entry["verdict_action_fa"]
        ctx["final_status"] = entry["final_status_fa"] or ctx.get("final_status")
        ctx["last_performance_entry_at"] = now_iso
        instance.context_data = ctx
        flag_modified(instance, "context_data")

        student = await self._get_student(instance.student_id)
        if student:
            extra = _as_mapping(student.extra_data)
            log = list(extra.get("monitoring_performance_log") or [])
            log.append(entry)
            extra["monitoring_performance_log"] = log
            student.extra_data = extra
            flag_modified(student, "extra_data")
        return "record_violation_performance_entry"

    async def _handle_lift_suspension_restrictions(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        """برداشتن محدودیت‌های تعلیق (ثبت‌نام، حضور، کلاس)."""
        student = await self._get_student(instance.student_id)
        if not student:
            return "student_not_found"
        extra = _as_mapping(student.extra_data)
        extra["class_access_blocked"] = False
        gates = dict(extra.get("gates") or {})
        gates["next_term_registration_blocked"] = False
        gates["next_term_registration_blocked_at"] = datetime.now(timezone.utc).isoformat()
        extra["gates"] = gates
        lms = dict(extra.get("lms") or {})
        lms["attendance_enabled"] = {"global": {"enabled": True, "unblocked_at": datetime.now(timezone.utc).isoformat()}}
        extra["lms"] = lms
        extra["violation_suspension_lifted_at"] = datetime.now(timezone.utc).isoformat()
        student.extra_data = extra
        flag_modified(student, "extra_data")
        ctx = _as_mapping(instance.context_data)
        ctx["suspension_lifted_at"] = datetime.now(timezone.utc).isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return "lift_suspension_restrictions"

    async def _handle_record_live_supervision_attendance(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.live_supervision_course_service import record_dual_attendance

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        course_type = str(merged.get("course_type") or "").lower()
        if course_type != "live_supervision" and not merged.get("live_supervision_session"):
            return "record_live_supervision_attendance_skipped"
        course_code = (
            merged.get("course_code")
            or merged.get("lesson_course_label")
            or merged.get("course_name")
            or ""
        )
        rows = merged.get("dual_attendance") or merged.get("students_dual_attendance") or []
        if not rows and merged.get("students_attendance"):
            for r in merged.get("students_attendance") or []:
                if not isinstance(r, dict):
                    continue
                status = str(r.get("status") or "present").lower()
                rows.append({
                    "student_id": r.get("student_id"),
                    "normal_present": status == "present" and not r.get("mirror_present"),
                    "mirror_present": bool(r.get("mirror_present")),
                    "absent": status in ("absent", "غایب", "absent_unexcused"),
                })
        actor_id = instance.started_by or instance.student_id
        summary = await record_dual_attendance(
            self.db,
            course_code=str(course_code),
            session_date=str(merged.get("session_date") or ""),
            attendance_rows=rows,
            actor_id=actor_id,
            calendar_session_increment=str(merged.get("course_type") or "") == "live_supervision"
            or bool(merged.get("live_supervision_session")),
        )
        ctx = _as_mapping(instance.context_data)
        ctx["live_supervision_attendance_summary"] = summary
        ctx["course_type"] = ctx.get("course_type") or "live_supervision"
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        return f"record_live_supervision_attendance updated={summary.get('updated', 0)}"

    async def _handle_record_skills_session_17_grades(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.skills_course_completion_service import on_session_17_submit

        return await on_session_17_submit(self.db, instance, context)

    async def _handle_record_skills_session_18_grades(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.skills_course_completion_service import on_session_18_submit

        return await on_session_18_submit(self.db, instance, context)

    async def _handle_compute_skills_final_grades(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.skills_course_completion_service import auto_compute_grades

        return await auto_compute_grades(self.db, instance)

    async def _handle_record_skills_ta_grades(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.skills_course_completion_service import on_ta_grades_submit

        return await on_ta_grades_submit(self.db, instance, context)

    async def _handle_record_skills_qualitative_eval(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.skills_course_completion_service import on_qualitative_submit

        return await on_qualitative_submit(self.db, instance, context)

    async def _handle_record_theory_session_18_grades(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.theory_course_completion_service import on_session_18_submit

        return await on_session_18_submit(self.db, instance, context)

    async def _handle_compute_theory_final_grades(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.theory_course_completion_service import auto_compute_grades

        return await auto_compute_grades(self.db, instance, context)

    async def _handle_compute_theory_retake_grades(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.theory_course_completion_service import on_retake_compute

        return await on_retake_compute(self.db, instance, context)

    async def _handle_finalize_theory_borderline_fail(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.theory_course_completion_service import on_borderline_fail

        return await on_borderline_fail(self.db, instance, context)

    async def _handle_activate_theory_retake_exam(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.theory_course_completion_service import on_activate_retake

        return await on_activate_retake(self.db, instance, context)

    async def _handle_record_theory_qualitative_eval(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.theory_course_completion_service import on_qualitative_submit

        return await on_qualitative_submit(self.db, instance, context)

    async def _handle_record_group_supervision_pass_fail(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.group_supervision_course_completion_service import on_pass_fail_submit

        return await on_pass_fail_submit(self.db, instance, context)

    async def _handle_record_group_supervision_ta_grades(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.group_supervision_course_completion_service import on_ta_grades_submit

        return await on_ta_grades_submit(self.db, instance, context)

    async def _handle_record_group_supervision_qualitative_eval(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.group_supervision_course_completion_service import on_qualitative_submit

        return await on_qualitative_submit(self.db, instance, context)

    async def _handle_activate_compensation_payment(
        self, action: dict, instance: ProcessInstance, context: dict,
    ):
        from app.services.live_supervision_course_service import activate_compensation_payment

        merged = {**_as_mapping(instance.context_data), **(context or {})}
        course_code = str(merged.get("course_code") or merged.get("course_name") or "")
        n = int(merged.get("compensation_sessions_pending") or merged.get("sessions_count") or 0)
        result = await activate_compensation_payment(
            self.db, instance.student_id, course_code, n,
        )
        return f"activate_compensation_payment {result}"

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

    async def _instructor_course_assignment_row(
        self, instructor_user_id: Any, process_code: str
    ) -> Optional[dict]:
        try:
            user = await self._get_user_direct(uuid.UUID(str(instructor_user_id)))
        except (ValueError, TypeError):
            return None
        if not user:
            return None
        meta = _as_mapping(user.profile_meta)
        items = meta.get("semester_course_assignments") or []
        kws = _LIVE_SESSION_COURSE_KEYWORDS.get(process_code, ())
        fallback: Optional[dict] = None
        for row in items:
            if not isinstance(row, dict):
                continue
            if row.get("role_kind") not in (None, "instructor"):
                continue
            code = str(
                row.get("course_code") or row.get("code") or row.get("course_name") or ""
            ).strip()
            if not code:
                continue
            if fallback is None:
                fallback = row
            code_l = code.lower()
            if not kws or any(k.lower() in code_l or k in code for k in kws):
                return row
        return fallback

    async def _live_session_course_code(self, instance: ProcessInstance) -> Optional[str]:
        ctx = _as_mapping(instance.context_data)
        if ctx.get("course_code"):
            return str(ctx["course_code"]).strip() or None
        iuid = ctx.get("instructor_id")
        if not iuid:
            return None
        row = await self._instructor_course_assignment_row(iuid, instance.process_code)
        if not row:
            return None
        return str(
            row.get("course_code") or row.get("code") or row.get("course_name") or ""
        ).strip() or None

    async def _resolve_live_session_ta_contact(
        self, instance: ProcessInstance, course_code: str
    ) -> Optional[str]:
        stmt = select(User).where(User.role == "teaching_assistant", User.is_active == True)
        result = await self.db.execute(stmt)
        code = str(course_code or "").strip()
        for user in result.scalars().all():
            meta = _as_mapping(user.profile_meta)
            for row in meta.get("semester_course_assignments") or []:
                if not isinstance(row, dict):
                    continue
                if row.get("role_kind") not in (None, "teaching_assistant"):
                    continue
                row_code = str(
                    row.get("course_code") or row.get("code") or row.get("course_name") or ""
                ).strip()
                if row_code == code:
                    return user.phone or user.email
        return None

    async def _resolve_class_student_contacts(
        self, instance: ProcessInstance, course_code: str
    ) -> list[str]:
        from app.services.instructor_course_roster_service import get_course_roster

        roster = await get_course_roster(self.db, course_code)
        contacts: list[str] = []
        seen: set[str] = set()
        for entry in roster:
            sid = entry.get("student_id")
            if not sid:
                continue
            try:
                st = await self.db.get(Student, uuid.UUID(str(sid)))
            except (ValueError, TypeError):
                continue
            if not st or not st.user_id:
                continue
            user = await self._get_user_direct(st.user_id)
            if not user:
                continue
            contact = user.phone or user.email
            if contact and contact not in seen:
                seen.add(contact)
                contacts.append(contact)
        return contacts

    async def _resolve_finance_contacts(self, ntype: str) -> list[str]:
        """همهٔ کاربران فعال نقش finance/accounting — SOP سند شهریه."""
        from app.core.user_roles import user_matches_role_sql

        stmt = select(User).where(
            user_matches_role_sql("finance"),
            User.is_active == True,  # noqa: E712
        )
        result = await self.db.execute(stmt)
        users = list(result.scalars().all())
        contacts: list[str] = []
        seen: set[str] = set()
        for user in users:
            contact = user.phone if ntype == "sms" else (user.email or user.phone)
            if ntype == "sms" and not contact:
                contact = user.email
            if contact and contact not in seen:
                seen.add(contact)
                contacts.append(contact)
        return contacts

    async def _resolve_contact(self, role: str, instance: ProcessInstance, ntype: str) -> Optional[str]:
        """Resolve a contact (phone/email) for a role in the context of an instance."""
        student = await self._get_student(instance.student_id)
        if not student:
            return None

        if role in ("accounting", "finance"):
            contacts = await self._resolve_finance_contacts(ntype)
            return contacts[0] if contacts else None

        if role in ("student", "applicant"):
            user = await self._get_user(student.user_id)
            return user.phone or user.email if user else None

        if role == "interviewer":
            merged = _as_mapping(instance.context_data)
            iuid = merged.get("interviewer_user_id")
            if iuid:
                try:
                    user = await self._get_user_direct(uuid.UUID(str(iuid)))
                    return user.phone or user.email if user else None
                except (ValueError, TypeError):
                    pass
            stmt = (
                select(InterviewSlot.interviewer_user_id)
                .where(InterviewSlot.assigned_instance_id == instance.id)
                .where(InterviewSlot.interviewer_user_id.isnot(None))
                .limit(1)
            )
            r = await self.db.execute(stmt)
            row = r.scalars().first()
            if row is not None:
                user = await self._get_user_direct(row)
                return user.phone or user.email if user else None
            return None

        if role == "supervisor" and student.supervisor_id:
            user = await self._get_user_direct(student.supervisor_id)
            return user.phone or user.email if user else None

        if role == "therapist" and student.therapist_id:
            user = await self._get_user_direct(student.therapist_id)
            return user.phone or user.email if user else None

        if role in ("site_manager", "deputy_education", "monitoring_committee_officer",
                     "therapy_committee_chair", "therapy_committee_executor"):
            from app.core.user_roles import user_matches_role_sql

            stmt = select(User).where(user_matches_role_sql(role), User.is_active == True).limit(1)
            result = await self.db.execute(stmt)
            user = result.scalars().first()
            return user.phone or user.email if user else None

        from app.services.process_role_user_resolver import resolve_contact_for_assigned_role

        if role in (
            "deputy_education_director",
            "education_director",
            "course_committee_executive",
            "scientific_officer_course_committee",
            "admissions_officer",
            "staff",
            "admin",
        ):
            contact = await resolve_contact_for_assigned_role(self.db, role)
            if contact:
                return contact

        ctx = _as_mapping(instance.context_data)
        if role == "new_supervisor" and ctx.get("new_supervisor_id"):
            user = await self._get_user_direct(uuid.UUID(ctx["new_supervisor_id"]))
            return user.phone or user.email if user else None

        if instance.process_code in _LIVE_SESSION_PREP_CODES:
            if role == "instructor" and ctx.get("instructor_id"):
                try:
                    user = await self._get_user_direct(uuid.UUID(str(ctx["instructor_id"])))
                    return user.phone or user.email if user else None
                except (ValueError, TypeError):
                    pass
            if role == "teaching_assistant":
                course_code = await self._live_session_course_code(instance)
                if course_code:
                    return await self._resolve_live_session_ta_contact(instance, course_code)
            if role == "therapist" and ctx.get("therapist_id"):
                try:
                    user = await self._get_user_direct(uuid.UUID(str(ctx["therapist_id"])))
                    return user.phone or user.email if user else None
                except (ValueError, TypeError):
                    pass

        _PROGRESS_RECIPIENT_TO_ASSIGNED = {
            "progress_scientific": "progress_committee_scientific",
            "progress_project": "progress_committee_project",
        }
        if role in _PROGRESS_RECIPIENT_TO_ASSIGNED:
            contact = await resolve_contact_for_assigned_role(
                self.db, _PROGRESS_RECIPIENT_TO_ASSIGNED[role]
            )
            if contact:
                return contact

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

        # مبلغ شهریه برای SMS حسابداری (SOP 40)
        if not notif_ctx.get("amount"):
            from app.services.workflow.termination_records import _tuition_amount_toman

            amt = _tuition_amount_toman(notif_ctx)
            if amt > 0:
                notif_ctx["amount"] = f"{int(round(amt)):,}"

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
        if instance.process_code == "ta_track_change" and (
            notif_ctx.get("meeting_date") or notif_ctx.get("meeting_time")
        ):
            from app.services.ta_track_change_service import format_meeting_summary_fa

            notif_ctx["meeting_summary_fa"] = format_meeting_summary_fa(notif_ctx)
            notif_ctx.setdefault("meeting_date", notif_ctx.get("meeting_date") or "")
            notif_ctx.setdefault("meeting_time", notif_ctx.get("meeting_time") or "")
            notif_ctx.setdefault("meeting_link", notif_ctx.get("meeting_link") or "")
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

        if instance.process_code in (
            "introductory_course_registration",
            "comprehensive_course_registration",
        ):
            slot_extra = await enrich_interview_notification_context(self.db, instance)
            if slot_extra:
                notif_ctx = {**notif_ctx, **slot_extra}
            if instance.process_code == "introductory_course_registration":
                notif_ctx.setdefault(
                    "course_label",
                    "دوره آشنایی کاربردی با روانکاوی معاصر",
                )
                notif_ctx.setdefault("term_label", notif_ctx.get("term_label") or "ترم جاری")
                notif_ctx.setdefault(
                    "deadline",
                    notif_ctx.get("registration_payment_deadline")
                    or notif_ctx.get("documents_upload_deadline")
                    or notif_ctx.get("documents_correction_deadline")
                    or notif_ctx.get("lms_login_deadline")
                    or "—",
                )
                notif_ctx.setdefault("username", notif_ctx.get("portal_username") or "")
                notif_ctx.setdefault(
                    "password",
                    notif_ctx.get("portal_password_display") or "",
                )
                raw_def = notif_ctx.get("deficiency_list")
                if not raw_def and notif_ctx.get("__documents_resubmit_fields"):
                    labels = notif_ctx.get("__document_field_labels_fa") or {}
                    lines = []
                    for i, fname in enumerate(notif_ctx["__documents_resubmit_fields"], 1):
                        lines.append(f"{i}- {labels.get(fname) or fname}")
                    notif_ctx["deficiency_list"] = "\n".join(lines) if lines else "—"

        if instance.process_code == "internship_12month_conditional_review":
            link = (notif_ctx.get("interview_link") or "").strip()
            loc = (notif_ctx.get("interview_location") or "").strip()
            if link:
                notif_ctx["interview_location_or_link"] = f"(لینک جلسه: {link})"
            elif loc:
                notif_ctx["interview_location_or_link"] = f"(مکان: {loc})"
            else:
                notif_ctx["interview_location_or_link"] = "(مکان: انستیتو روانکاوی تهران)"
            notif_ctx.setdefault("interview_date", "—")
            notif_ctx.setdefault("interview_time", "—")

        if instance.process_code in _LIVE_SESSION_PREP_CODES:
            ctxm = _as_mapping(instance.context_data)
            sd = ctxm.get("session_date")
            st = str(ctxm.get("session_time") or "").strip()
            # Keep full value; normalize_sms_context_dates formats Shamsi in Tehran.
            date_fa = sd if sd not in (None, "") else "—"
            notif_ctx["تاریخ ثبت شده"] = date_fa
            notif_ctx["ساعت ثبت شده"] = st or "—"
            notif_ctx.setdefault("session_date_fa", date_fa)
            notif_ctx.setdefault("session_date", date_fa)
            notif_ctx.setdefault("session_time", st or "—")
            # #region agent log
            try:
                import json as _json
                from pathlib import Path as _Path
                from time import time as _time
                from app.utils.shamsi_calendar_utils import format_shamsi_date as _fsd
                _line = {
                    "sessionId": "8e31fd",
                    "hypothesisId": "E",
                    "location": "action_handler.py:_build_notification_context:live_session",
                    "message": "live session sms date (no utc slice)",
                    "data": {
                        "process_code": instance.process_code,
                        "session_date_raw": str(sd)[:80] if sd is not None else None,
                        "date_fa_passed": str(date_fa)[:80],
                        "date_fa_shamsi": _fsd(date_fa) if date_fa not in (None, "—") else "—",
                        "session_time": st or "—",
                    },
                    "timestamp": int(_time() * 1000),
                    "runId": "post-fix",
                }
                with open(_Path(__file__).resolve().parents[2] / "debug-8e31fd.log", "a", encoding="utf-8") as _f:
                    _f.write(_json.dumps(_line, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion

        if instance.process_code == "start_therapy":
            ctxm = _as_mapping(instance.context_data)
            # درمانگر از پرونده دانشجو یا context
            if not notif_ctx.get("therapist_name"):
                tid = ctxm.get("therapist_id") or (str(student.therapist_id) if student and student.therapist_id else None)
                if tid:
                    try:
                        th_user = await self._get_user_direct(uuid.UUID(str(tid)))
                        if th_user:
                            notif_ctx["therapist_name"] = th_user.full_name_fa or "درمانگر"
                    except (ValueError, TypeError):
                        pass
            notif_ctx.setdefault("therapist_name", "درمانگر")

            summary = ctxm.get("selected_slots_summary_fa") or notif_ctx.get("selected_slots_summary_fa")
            if isinstance(summary, list) and summary:
                notif_ctx["weekly_schedule_fa"] = " و ".join(str(x) for x in summary if x)
            elif summary:
                notif_ctx["weekly_schedule_fa"] = str(summary)
            else:
                notif_ctx.setdefault("weekly_schedule_fa", "طبق برنامهٔ هفتگی ثبت‌شده")

            course = (student.course_type if student else None) or ctxm.get("course_type") or ""
            course_fa = {
                "introductory": "آشنایی",
                "comprehensive": "جامع",
            }.get(str(course).strip(), str(course).strip() or "—")
            notif_ctx.setdefault("course_type_fa", course_fa)
            notif_ctx.setdefault(
                "first_session_date",
                ctxm.get("first_session_date_effective") or ctxm.get("first_session_date") or "—",
            )

            link = (
                (notif_ctx.get("last_session_link") or notif_ctx.get("meeting_url") or "")
                .strip()
            )
            if link and "/meet/therapy/" not in link:
                notif_ctx["session_link_line"] = f"لینک ورود به جلسه:\n{link}"
            elif link:
                notif_ctx["session_link_line"] = (
                    "لینک ورود به جلسه در پورتال دانشجویی (تب جلسات آنلاین) در دسترس است."
                )
            else:
                notif_ctx["session_link_line"] = (
                    "لینک ورود به جلسه پس از آماده‌سازی در پورتال (تب جلسات آنلاین) نمایش داده می‌شود."
                )

        from app.utils.shamsi_calendar_utils import normalize_sms_context_dates

        notif_ctx = normalize_sms_context_dates(notif_ctx)
        if instance.process_code == "ta_track_change" and (
            notif_ctx.get("meeting_date") or notif_ctx.get("meeting_time")
        ):
            from app.services.ta_track_change_service import format_meeting_summary_fa

            notif_ctx["meeting_summary_fa"] = format_meeting_summary_fa(notif_ctx)
        if instance.process_code == "educational_leave" and notif_ctx.get("committee_meeting_at"):
            notif_ctx["meeting_summary_fa"] = self._format_committee_meeting_summary_fa(notif_ctx)

        return notif_ctx

    @staticmethod
    def _format_committee_meeting_summary_fa(ctx: dict) -> str:
        """خلاصهٔ خوانا برای پیامک/ایمیل جلسه کمیته مرخصی."""
        from app.utils.shamsi_calendar_utils import format_shamsi_datetime_for_sms

        raw = format_shamsi_datetime_for_sms(ctx.get("committee_meeting_at") or "")
        mode = (ctx.get("committee_meeting_mode") or "").strip()
        mode_fa = "آنلاین" if mode == "online" else ("حضوری" if mode == "in_person" else mode or "—")
        parts = [f"زمان (ثبت‌شده در سامانه): {raw or '—'}", f"نوع: {mode_fa}"]
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

    async def _handle_evaluate_et_therapy_readiness(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        from app.services.educational_therapist_upgrade_service import run_auto_readiness_transition

        actor = await self._resolve_system_actor_id_for_actions()
        to_state = await run_auto_readiness_transition(
            self.db, instance, phase="therapy", actor_id=actor
        )
        return f"therapy_readiness_auto to_state={to_state}"

    async def _handle_evaluate_et_supervision_readiness(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        from app.services.educational_therapist_upgrade_service import run_auto_readiness_transition

        actor = await self._resolve_system_actor_id_for_actions()
        to_state = await run_auto_readiness_transition(
            self.db, instance, phase="supervision", actor_id=actor
        )
        return f"supervision_readiness_auto to_state={to_state}"

    async def _handle_register_et_availability_slots(
        self, action: dict, instance: ProcessInstance, context: dict
    ):
        from app.services.educational_therapist_upgrade_service import register_et_availability_slots

        merged = {**_as_mapping(instance.context_data), **_as_mapping(context)}
        return await register_et_availability_slots(self.db, instance, merged)

    # ─── Action Registry ─────────────────────────────────────────

    _registry = {
        "notification": _handle_notification,
        "start_process": _handle_start_process,

        "add_recurring_therapy_session": _handle_add_recurring_session,
        "add_recurring_supervision_session": _handle_add_recurring_session,
        "remove_selected_therapy_sessions": _handle_remove_therapy_sessions,
        "remove_selected_supervision_sessions": _handle_remove_selected_sessions,
        "release_therapist_slots_to_available_sheet": _handle_release_therapist_slots,
        "reopen_student_step_forms": _handle_reopen_student_step_forms,
        "book_educational_therapist_slots": _handle_book_educational_therapist_slots,
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
        "prefill_return_context": _handle_prefill_return_context,
        "apply_return_therapy_session_schedule": _handle_apply_return_therapy_session_schedule,
        "apply_return_supervision_schedule": _handle_apply_return_supervision_schedule,
        "set_full_education_leave_flag": _handle_set_full_education_leave_flag,
        "apply_full_leave_intern_effects": _handle_apply_full_leave_intern_effects,
        "apply_full_leave_therapist_decision": _handle_apply_full_leave_therapist_decision,
        "notify_therapy_coordination": _handle_notify_therapy_coordination,
        "auto_release_therapist_slot": _handle_auto_release_therapist_slot,
        "clear_full_education_leave_flag": _handle_clear_full_education_leave_flag,
        "delete_future_therapy_appointments": _handle_delete_future_appointments,
        "release_therapist_slots": _handle_release_therapist_slots,
        "update_therapy_status": _handle_update_therapy_status,
        "mark_therapy_relationship_terminated": _handle_mark_terminated,
        "log_termination_request": _handle_log_termination,
        "set_student_status": _handle_set_student_status,

        "send_45_48_reminder_if_applicable": _handle_send_reminder,
        "unlock_payment_for_50th_session": _handle_unlock_payment_50th,
        "display_supervision_history": _handle_display_supervision_history,
        "display_available_supervisor_slots": _handle_display_available_supervisor_slots,
        "remove_slot_from_available": _handle_remove_slot_from_available,
        "prepare_supervision_block_payment": _handle_prepare_supervision_block_payment,
        "book_supervision_block_slots": _handle_book_supervision_block_slots,

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
        "record_course_grades": _handle_record_process_artifact,
        "record_class_attendance": _handle_record_process_artifact,
        "record_live_supervision_attendance": _handle_record_live_supervision_attendance,
        "record_skills_session_17_grades": _handle_record_skills_session_17_grades,
        "record_skills_session_18_grades": _handle_record_skills_session_18_grades,
        "compute_skills_final_grades": _handle_compute_skills_final_grades,
        "record_skills_ta_grades": _handle_record_skills_ta_grades,
        "record_skills_qualitative_eval": _handle_record_skills_qualitative_eval,
        "record_theory_session_18_grades": _handle_record_theory_session_18_grades,
        "compute_theory_final_grades": _handle_compute_theory_final_grades,
        "compute_theory_retake_grades": _handle_compute_theory_retake_grades,
        "finalize_theory_borderline_fail": _handle_finalize_theory_borderline_fail,
        "activate_theory_retake_exam": _handle_activate_theory_retake_exam,
        "record_theory_qualitative_eval": _handle_record_theory_qualitative_eval,
        "record_group_supervision_pass_fail": _handle_record_group_supervision_pass_fail,
        "record_group_supervision_ta_grades": _handle_record_group_supervision_ta_grades,
        "record_group_supervision_qualitative_eval": _handle_record_group_supervision_qualitative_eval,
        "activate_compensation_payment": _handle_activate_compensation_payment,
        "record_class_cancellation": _handle_record_class_cancellation,
        "record_cancellation_applied": _handle_record_process_artifact,
        "record_supervision_cancellation": _handle_record_process_artifact,
        "record_leave_request": _handle_record_process_artifact,
        "record_return_request": _handle_record_process_artifact,
        "record_upgrade_decision": _handle_record_process_artifact,
        "evaluate_et_therapy_readiness": _handle_evaluate_et_therapy_readiness,
        "evaluate_et_supervision_readiness": _handle_evaluate_et_supervision_readiness,
        "register_et_availability_slots": _handle_register_et_availability_slots,
        "record_intern_referral": _handle_record_process_artifact,
        "record_article_milestone": _handle_record_process_artifact,
        "record_student_performance_traits": _handle_record_student_performance_traits,
        "record_violation_performance_entry": _handle_record_violation_performance_entry,
        "lift_suspension_restrictions": _handle_lift_suspension_restrictions,
        "record_session_prep": _handle_record_process_artifact,
        "record_ta_leave": _handle_record_process_artifact,
        "record_evaluation_submission": _handle_record_process_artifact,
        "record_evaluation_closed": _handle_record_process_artifact,
        "record_merged_stub": _handle_record_process_artifact,
        "ensure_therapist_slots_freed": _handle_release_therapist_slots,

        "send_unlock_to_lms": _handle_svc_lms,
        "unlock_student_therapist_selection": _handle_svc_lms,
        "record_commission_result": _handle_svc_evaluation,
        "store_nezarat_recommendation": _handle_svc_evaluation,
        "generate_termination_letter": _handle_svc_document,
        "register_new_supervision_block_in_lms": _handle_svc_lms,
        "enable_attendance_for_new_supervisor": _handle_svc_lms,
        "create_online_link_50th": _handle_svc_lms,
        "enable_attendance_for_current_supervisor_50th": _handle_svc_lms,
        "display_available_supervisor_slots": _handle_display_available_supervisor_slots,
        "display_mandatory_message": _handle_svc_portal,
        "apply_24h_rule_for_start_date": _handle_svc_calendar,
        "display_calculated_start_date": _handle_svc_portal,
        "cancel_supervision_session": _handle_cancel_session,
        "add_supervision_credit_if_paid": _handle_add_credit,
        "register_supervision_makeup_session": _handle_register_makeup,
        "enable_attendance_registration": _handle_unlock_attendance_registration,
        "release_supervisor_slot": _handle_release_supervisor_slot,
        "move_supervisor_to_past_list": _handle_move_supervisor_to_past_list,
        "record_interruption_dates": _handle_svc_calendar,
        "monitor_return_at_end_date": _handle_svc_calendar,
        "run_patient_referral": _handle_run_patient_referral,
        "move_ta_to_instructor": _handle_svc_role,
        "upgrade_rank_to_assistant_faculty": _handle_svc_role,
        "unlock_next_course_in_track": _handle_svc_lms,
        "publish_courses_to_website": _handle_publish_term_course_offerings,
        "publish_term_course_offerings": _handle_publish_term_course_offerings,
        "sync_financial_defaults_from_prep": _handle_sync_financial_defaults_from_prep,
        "sync_institute_license_from_prep": _handle_sync_institute_license_from_prep,
        "publish_academic_calendar_to_profiles": _handle_svc_calendar,
        "show_popup": _handle_svc_portal,
        "load_available_courses": _handle_svc_lms,
        "register_courses_in_portal": _handle_svc_lms,
        "create_online_class_links": _handle_create_online_class_links,
        "schedule_installment_reminders": _handle_svc_portal,
        "block_attendance_registration": _handle_block_attendance,
        "set_installment_portal_lock": _handle_set_installment_portal_lock,
        "notify_instructor": _handle_svc_portal,
        "unblock_attendance_registration": _handle_unlock_attendance_registration,
        "clear_installment_portal_lock": _handle_clear_installment_portal_lock,

        "record_commission_result_in_student_portal": _handle_svc_evaluation,
        "record_evaluation_completion": _handle_svc_evaluation,
        "lock_block_counter": _handle_svc_evaluation,
        "display_evaluation_warning_to_supervisor": _handle_svc_portal,
        "create_evaluation_task": _handle_svc_evaluation,
        "suspend_class_registration": _handle_block_class_access,
        "revoke_intern_status": _handle_revoke_intern_status,
        "set_leave_return_schedule": _handle_set_leave_return_schedule,
        "warn_if": _handle_warn_if,

        # نام‌های اضافهٔ متادیتا (هم‌ارز یا استاب یکپارچه‌سازی)
        "add_ta_score": _handle_svc_evaluation,
        "apply_electronic_signature_and_seal": _handle_svc_document,
        "archive_letter_in_student_file": _handle_svc_document,
        "block_future_applications": _handle_svc_gate,
        "block_future_enrollment": _handle_svc_gate,
        "block_next_term_registration": _handle_svc_gate,
        "cancel_all_future_sessions": _handle_delete_future_appointments,
        "create_education_committee_task": _handle_svc_evaluation,
        "sync_extra_session_reenter_fields": _handle_sync_extra_session_reenter_fields,
        "prepare_extra_session_payment": _handle_prepare_extra_session_payment,
        "create_extra_session_record": _handle_create_extra_session_record,
        "note_extra_session_calendar": _handle_note_extra_session_calendar,
        "add_extra_session_therapy_hours": _handle_add_extra_session_therapy_hours,
        "create_lms_course_links": _handle_svc_lms,
        "create_user_account": _handle_svc_role,
        "deduct_credit_if_has": _handle_deduct_credit_session,
        "display_error_message": _handle_svc_portal,
        "display_meeting_in_portal": _handle_svc_portal,
        "display_rejection_explanations": _handle_svc_portal,
        "enable_pdf_export": _handle_svc_document,
        "generate_certificate": _handle_svc_document,
        "generate_cumulative_transcript": _handle_svc_document,
        "generate_decline_list": _handle_svc_document,
        "generate_pdf_export": _handle_svc_document,
        "generate_term_transcript": _handle_svc_document,
        "increase_intern_capacity": _handle_svc_capacity,
        "load_term3_courses": _handle_svc_lms,
        "log_sla_breach_in_portals": _handle_svc_portal,
        "move_to_past_lists": _handle_svc_capacity,
        "process_refund": _handle_process_refund_action,
        "reactivate_class_registration": _handle_reactivate_class_registration,
        "record_accounting": _handle_svc_termination,
        "record_pause_dates_in_lms": _handle_svc_lms,
        "record_termination_date": _handle_svc_termination,
        "record_termination_in_student_portal": _handle_svc_termination,
        "refer_to_violation_registration": _handle_refer_to_violation_registration,
        "register_in_calendar": _handle_svc_calendar,
        "register_student_in_courses": _handle_svc_lms,
        "record_lms_links_placed": _handle_svc_lms,
        "build_class_attendance_list": _handle_svc_lms,
        "register_lesson_teaching_assistants": _handle_svc_lms,
        "release_supervisor_slots": _handle_release_slots,
        "reset_therapy_sessions": _handle_reset_therapy_sessions,
        "retain_patients": _handle_svc_capacity,
        "retain_supervisor": _handle_svc_capacity,
        "retain_therapist_and_supervisor": _handle_svc_capacity,
        "revoke_student_access": _handle_svc_role,
        "schedule_reminder": _handle_svc_portal,
        "scheduled_notification": _handle_svc_portal,
        "send_to_dashboard": _handle_svc_portal,
        "send_to_progress_committee": _handle_svc_portal,
        "share_document_with_interviewer": _handle_svc_portal,
        "show_payment_confirmation": _handle_svc_portal,
        "store_executive_advisory_opinion": _handle_svc_evaluation,
        "store_rejection_reason_confidential": _handle_svc_evaluation,
        "unblock_next_term_registration": _handle_svc_gate,
        "update_schedule": _handle_update_therapy_schedule,
        "update_therapist": _handle_update_therapist,
        "update_total_hours": _handle_svc_lms,
        "upload_certificate_to_portal": _handle_svc_document,
    }
