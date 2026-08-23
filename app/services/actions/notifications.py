"""Notification dispatch plus recipient and context resolution.

Part of the ActionHandler split. Every method below runs as a mixin method
on ActionHandler, so `self` exposes the whole handler surface.
"""

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from app.services.interview_slot_service import enrich_interview_notification_context
from app.services.notification_service import TEMPLATES, notification_service
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.orm.attributes import flag_modified
from typing import Optional, Any, List
import uuid

from app.services.actions._shared import (
    _LIVE_SESSION_COURSE_KEYWORDS,
    _LIVE_SESSION_PREP_CODES,
    _as_mapping,
    logger,
)


class NotificationActionsMixin:
    """Notification dispatch plus recipient and context resolution."""

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

            if role == "assigned_therapists" and instance.process_code == "patient_referral":
                contacts = await self._resolve_assigned_therapist_contacts(instance, ntype)
                if not contacts:
                    sent.append(f"{role}:no_contact")
                    warning_records.append(
                        {"recipient_role": role, "contact": None, "delivered": False}
                    )
                    continue
                therapist_template = (
                    "patient_referral_therapist_notice"
                    if ntype == "sms"
                    else effective_template
                )
                for contact in contacts:
                    result = await notification_service.send_notification(
                        ntype,
                        therapist_template,
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

    async def _resolve_assigned_therapist_contacts(
        self, instance: ProcessInstance, ntype: str
    ) -> list[str]:
        from app.services.hub_patient_referral import normalize_referral_patients

        ctx = _as_mapping(instance.context_data)
        rows = normalize_referral_patients(ctx.get("referral_patients"))
        contacts: list[str] = []
        seen: set[str] = set()
        for row in rows:
            tid = row.get("assigned_therapist_user_id")
            if not tid:
                continue
            try:
                user = await self._get_user_direct(uuid.UUID(str(tid)))
            except (ValueError, TypeError):
                continue
            if not user:
                continue
            contact = user.phone if ntype == "sms" else (user.email or user.phone)
            if contact and str(contact).strip() and contact not in seen:
                seen.add(contact)
                contacts.append(str(contact).strip())
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
                    from app.meta.student_step_forms import format_documents_deficiency_list

                    notif_ctx["deficiency_list"] = format_documents_deficiency_list(notif_ctx)

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


# action type -> handler; merged into ActionHandler._registry
REGISTRY = {
    'notification': NotificationActionsMixin._handle_notification,
    'evaluate_et_therapy_readiness': NotificationActionsMixin._handle_evaluate_et_therapy_readiness,
    'evaluate_et_supervision_readiness': NotificationActionsMixin._handle_evaluate_et_supervision_readiness,
    'register_et_availability_slots': NotificationActionsMixin._handle_register_et_availability_slots,
}
