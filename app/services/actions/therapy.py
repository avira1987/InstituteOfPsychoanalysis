"""Therapy lifecycle: activation, scheduling, leave and termination.

Part of the ActionHandler split. Every method below runs as a mixin method
on ActionHandler, so `self` exposes the whole handler surface.
"""

from app.config import get_settings
from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from app.services.alocom_provision import provision_therapy_session_alocom
from app.services.attendance_tracking_sync import (
    cancel_attendance_instances_for_therapy_session_ids,
    ensure_attendance_instance_for_session,
)
from app.services.external_integration import append_integration_event, notify_integration
from app.services.financial_program_defaults_service import get_effective_financial_program_defaults
from app.services.notification_service import TEMPLATES, notification_service
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, Any, List
import uuid

from app.services.actions._shared import (
    _as_mapping,
    logger,
    parse_therapy_session_id_list,
)


class TherapyActionsMixin:
    """Therapy lifecycle: activation, scheduling, leave and termination."""

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
        if instance.process_code == "violation_registration":
            from app.services.hub_student_flags import set_is_suspended

            set_is_suspended(extra, True)
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


# action type -> handler; merged into ActionHandler._registry
REGISTRY = {
    'remove_selected_therapy_sessions': TherapyActionsMixin._handle_remove_therapy_sessions,
    'release_therapist_slots_to_available_sheet': TherapyActionsMixin._handle_release_therapist_slots,
    'reopen_student_step_forms': TherapyActionsMixin._handle_reopen_student_step_forms,
    'book_educational_therapist_slots': TherapyActionsMixin._handle_book_educational_therapist_slots,
    'record_therapy_change_history': TherapyActionsMixin._handle_record_change_history,
    'cancel_session': TherapyActionsMixin._handle_cancel_session,
    'add_credit_if_paid': TherapyActionsMixin._handle_add_credit,
    'deduct_credit_session': TherapyActionsMixin._handle_deduct_credit_session,
    'register_makeup_session': TherapyActionsMixin._handle_register_makeup,
    'enable_online_session_link': TherapyActionsMixin._handle_enable_online_link,
    'activate_therapy': TherapyActionsMixin._handle_activate_therapy,
    'block_class_access': TherapyActionsMixin._handle_block_class_access,
    'resolve_access_restrictions': TherapyActionsMixin._handle_resolve_access,
    'create_session_link': TherapyActionsMixin._handle_create_session_link,
    'apply_start_therapy_session_schedule': TherapyActionsMixin._handle_apply_start_therapy_session_schedule,
    'prefill_return_context': TherapyActionsMixin._handle_prefill_return_context,
    'apply_return_therapy_session_schedule': TherapyActionsMixin._handle_apply_return_therapy_session_schedule,
    'apply_return_supervision_schedule': TherapyActionsMixin._handle_apply_return_supervision_schedule,
    'set_full_education_leave_flag': TherapyActionsMixin._handle_set_full_education_leave_flag,
    'apply_full_leave_intern_effects': TherapyActionsMixin._handle_apply_full_leave_intern_effects,
    'apply_full_leave_therapist_decision': TherapyActionsMixin._handle_apply_full_leave_therapist_decision,
    'notify_therapy_coordination': TherapyActionsMixin._handle_notify_therapy_coordination,
    'auto_release_therapist_slot': TherapyActionsMixin._handle_auto_release_therapist_slot,
    'clear_full_education_leave_flag': TherapyActionsMixin._handle_clear_full_education_leave_flag,
    'delete_future_therapy_appointments': TherapyActionsMixin._handle_delete_future_appointments,
    'release_therapist_slots': TherapyActionsMixin._handle_release_therapist_slots,
    'update_therapy_status': TherapyActionsMixin._handle_update_therapy_status,
    'mark_therapy_relationship_terminated': TherapyActionsMixin._handle_mark_terminated,
    'log_termination_request': TherapyActionsMixin._handle_log_termination,
    'set_student_status': TherapyActionsMixin._handle_set_student_status,
    'ensure_therapist_slots_freed': TherapyActionsMixin._handle_release_therapist_slots,
    'cancel_supervision_session': TherapyActionsMixin._handle_cancel_session,
    'add_supervision_credit_if_paid': TherapyActionsMixin._handle_add_credit,
    'register_supervision_makeup_session': TherapyActionsMixin._handle_register_makeup,
    'release_supervisor_slot': TherapyActionsMixin._handle_release_supervisor_slot,
    'suspend_class_registration': TherapyActionsMixin._handle_block_class_access,
    'revoke_intern_status': TherapyActionsMixin._handle_revoke_intern_status,
    'set_leave_return_schedule': TherapyActionsMixin._handle_set_leave_return_schedule,
    'warn_if': TherapyActionsMixin._handle_warn_if,
    'cancel_all_future_sessions': TherapyActionsMixin._handle_delete_future_appointments,
    'deduct_credit_if_has': TherapyActionsMixin._handle_deduct_credit_session,
    'reactivate_class_registration': TherapyActionsMixin._handle_reactivate_class_registration,
}
