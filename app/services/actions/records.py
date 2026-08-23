"""Workflow service delegations and process artifact records.

Part of the ActionHandler split. Every method below runs as a mixin method
on ActionHandler, so `self` exposes the whole handler surface.
"""

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
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
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.orm.attributes import flag_modified
import uuid

from app.services.actions._shared import (
    _as_mapping,
)


class RecordActionsMixin:
    """Workflow service delegations and process artifact records."""

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
        from app.services.hub_student_flags import clear_violation_suspension

        clear_violation_suspension(extra)
        lms = dict(extra.get("lms") or {})
        lms["attendance_enabled"] = {"global": {"enabled": True, "unblocked_at": datetime.now(timezone.utc).isoformat()}}
        extra["lms"] = lms
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


# action type -> handler; merged into ActionHandler._registry
REGISTRY = {
    'redirect_to_process': RecordActionsMixin._handle_redirect_to_process,
    'move_therapist_to_past': RecordActionsMixin._handle_move_therapist_to_past,
    'record_result_in_student_portal': RecordActionsMixin._handle_unlock_student_portal_flag,
    'record_course_grades': RecordActionsMixin._handle_record_process_artifact,
    'record_class_attendance': RecordActionsMixin._handle_record_process_artifact,
    'record_live_supervision_attendance': RecordActionsMixin._handle_record_live_supervision_attendance,
    'record_skills_session_17_grades': RecordActionsMixin._handle_record_skills_session_17_grades,
    'record_skills_session_18_grades': RecordActionsMixin._handle_record_skills_session_18_grades,
    'compute_skills_final_grades': RecordActionsMixin._handle_compute_skills_final_grades,
    'record_skills_ta_grades': RecordActionsMixin._handle_record_skills_ta_grades,
    'record_skills_qualitative_eval': RecordActionsMixin._handle_record_skills_qualitative_eval,
    'record_theory_session_18_grades': RecordActionsMixin._handle_record_theory_session_18_grades,
    'compute_theory_final_grades': RecordActionsMixin._handle_compute_theory_final_grades,
    'compute_theory_retake_grades': RecordActionsMixin._handle_compute_theory_retake_grades,
    'finalize_theory_borderline_fail': RecordActionsMixin._handle_finalize_theory_borderline_fail,
    'activate_theory_retake_exam': RecordActionsMixin._handle_activate_theory_retake_exam,
    'record_theory_qualitative_eval': RecordActionsMixin._handle_record_theory_qualitative_eval,
    'record_group_supervision_pass_fail': RecordActionsMixin._handle_record_group_supervision_pass_fail,
    'record_group_supervision_ta_grades': RecordActionsMixin._handle_record_group_supervision_ta_grades,
    'record_group_supervision_qualitative_eval': RecordActionsMixin._handle_record_group_supervision_qualitative_eval,
    'activate_compensation_payment': RecordActionsMixin._handle_activate_compensation_payment,
    'record_class_cancellation': RecordActionsMixin._handle_record_class_cancellation,
    'record_cancellation_applied': RecordActionsMixin._handle_record_process_artifact,
    'record_supervision_cancellation': RecordActionsMixin._handle_record_process_artifact,
    'record_leave_request': RecordActionsMixin._handle_record_process_artifact,
    'record_return_request': RecordActionsMixin._handle_record_process_artifact,
    'record_upgrade_decision': RecordActionsMixin._handle_record_process_artifact,
    'record_intern_referral': RecordActionsMixin._handle_record_process_artifact,
    'record_article_milestone': RecordActionsMixin._handle_record_process_artifact,
    'record_student_performance_traits': RecordActionsMixin._handle_record_student_performance_traits,
    'record_violation_performance_entry': RecordActionsMixin._handle_record_violation_performance_entry,
    'lift_suspension_restrictions': RecordActionsMixin._handle_lift_suspension_restrictions,
    'record_session_prep': RecordActionsMixin._handle_record_process_artifact,
    'record_ta_leave': RecordActionsMixin._handle_record_process_artifact,
    'record_evaluation_submission': RecordActionsMixin._handle_record_process_artifact,
    'record_evaluation_closed': RecordActionsMixin._handle_record_process_artifact,
    'record_merged_stub': RecordActionsMixin._handle_record_process_artifact,
    'send_unlock_to_lms': RecordActionsMixin._handle_svc_lms,
    'unlock_student_therapist_selection': RecordActionsMixin._handle_svc_lms,
    'record_commission_result': RecordActionsMixin._handle_svc_evaluation,
    'store_nezarat_recommendation': RecordActionsMixin._handle_svc_evaluation,
    'generate_termination_letter': RecordActionsMixin._handle_svc_document,
    'register_new_supervision_block_in_lms': RecordActionsMixin._handle_svc_lms,
    'enable_attendance_for_new_supervisor': RecordActionsMixin._handle_svc_lms,
    'create_online_link_50th': RecordActionsMixin._handle_svc_lms,
    'enable_attendance_for_current_supervisor_50th': RecordActionsMixin._handle_svc_lms,
    'display_mandatory_message': RecordActionsMixin._handle_svc_portal,
    'apply_24h_rule_for_start_date': RecordActionsMixin._handle_svc_calendar,
    'display_calculated_start_date': RecordActionsMixin._handle_svc_portal,
    'move_supervisor_to_past_list': RecordActionsMixin._handle_move_supervisor_to_past_list,
    'record_interruption_dates': RecordActionsMixin._handle_svc_calendar,
    'monitor_return_at_end_date': RecordActionsMixin._handle_svc_calendar,
    'run_patient_referral': RecordActionsMixin._handle_run_patient_referral,
    'move_ta_to_instructor': RecordActionsMixin._handle_svc_role,
    'upgrade_rank_to_assistant_faculty': RecordActionsMixin._handle_svc_role,
    'unlock_next_course_in_track': RecordActionsMixin._handle_svc_lms,
    'publish_courses_to_website': RecordActionsMixin._handle_publish_term_course_offerings,
    'publish_term_course_offerings': RecordActionsMixin._handle_publish_term_course_offerings,
    'sync_financial_defaults_from_prep': RecordActionsMixin._handle_sync_financial_defaults_from_prep,
    'sync_institute_license_from_prep': RecordActionsMixin._handle_sync_institute_license_from_prep,
    'publish_academic_calendar_to_profiles': RecordActionsMixin._handle_svc_calendar,
    'show_popup': RecordActionsMixin._handle_svc_portal,
    'load_available_courses': RecordActionsMixin._handle_svc_lms,
    'register_courses_in_portal': RecordActionsMixin._handle_svc_lms,
    'schedule_installment_reminders': RecordActionsMixin._handle_svc_portal,
    'notify_instructor': RecordActionsMixin._handle_svc_portal,
    'record_commission_result_in_student_portal': RecordActionsMixin._handle_svc_evaluation,
    'record_evaluation_completion': RecordActionsMixin._handle_svc_evaluation,
    'lock_block_counter': RecordActionsMixin._handle_svc_evaluation,
    'display_evaluation_warning_to_supervisor': RecordActionsMixin._handle_svc_portal,
    'create_evaluation_task': RecordActionsMixin._handle_svc_evaluation,
    'add_ta_score': RecordActionsMixin._handle_svc_evaluation,
    'apply_electronic_signature_and_seal': RecordActionsMixin._handle_svc_document,
    'archive_letter_in_student_file': RecordActionsMixin._handle_svc_document,
    'block_future_applications': RecordActionsMixin._handle_svc_gate,
    'block_future_enrollment': RecordActionsMixin._handle_svc_gate,
    'block_next_term_registration': RecordActionsMixin._handle_svc_gate,
    'create_education_committee_task': RecordActionsMixin._handle_svc_evaluation,
    'create_lms_course_links': RecordActionsMixin._handle_svc_lms,
    'create_user_account': RecordActionsMixin._handle_svc_role,
    'display_error_message': RecordActionsMixin._handle_svc_portal,
    'display_meeting_in_portal': RecordActionsMixin._handle_svc_portal,
    'display_rejection_explanations': RecordActionsMixin._handle_svc_portal,
    'enable_pdf_export': RecordActionsMixin._handle_svc_document,
    'generate_certificate': RecordActionsMixin._handle_svc_document,
    'generate_cumulative_transcript': RecordActionsMixin._handle_svc_document,
    'generate_decline_list': RecordActionsMixin._handle_svc_document,
    'generate_pdf_export': RecordActionsMixin._handle_svc_document,
    'generate_term_transcript': RecordActionsMixin._handle_svc_document,
    'increase_intern_capacity': RecordActionsMixin._handle_svc_capacity,
    'load_term3_courses': RecordActionsMixin._handle_svc_lms,
    'log_sla_breach_in_portals': RecordActionsMixin._handle_svc_portal,
    'move_to_past_lists': RecordActionsMixin._handle_svc_capacity,
    'process_refund': RecordActionsMixin._handle_process_refund_action,
    'record_accounting': RecordActionsMixin._handle_svc_termination,
    'record_pause_dates_in_lms': RecordActionsMixin._handle_svc_lms,
    'record_termination_date': RecordActionsMixin._handle_svc_termination,
    'record_termination_in_student_portal': RecordActionsMixin._handle_svc_termination,
    'refer_to_violation_registration': RecordActionsMixin._handle_refer_to_violation_registration,
    'register_in_calendar': RecordActionsMixin._handle_svc_calendar,
    'register_student_in_courses': RecordActionsMixin._handle_svc_lms,
    'record_lms_links_placed': RecordActionsMixin._handle_svc_lms,
    'build_class_attendance_list': RecordActionsMixin._handle_svc_lms,
    'register_lesson_teaching_assistants': RecordActionsMixin._handle_svc_lms,
    'reset_therapy_sessions': RecordActionsMixin._handle_reset_therapy_sessions,
    'retain_patients': RecordActionsMixin._handle_svc_capacity,
    'retain_supervisor': RecordActionsMixin._handle_svc_capacity,
    'retain_therapist_and_supervisor': RecordActionsMixin._handle_svc_capacity,
    'revoke_student_access': RecordActionsMixin._handle_svc_role,
    'schedule_reminder': RecordActionsMixin._handle_svc_portal,
    'scheduled_notification': RecordActionsMixin._handle_svc_portal,
    'send_to_dashboard': RecordActionsMixin._handle_svc_portal,
    'send_to_progress_committee': RecordActionsMixin._handle_svc_portal,
    'share_document_with_interviewer': RecordActionsMixin._handle_svc_portal,
    'show_payment_confirmation': RecordActionsMixin._handle_svc_portal,
    'store_executive_advisory_opinion': RecordActionsMixin._handle_svc_evaluation,
    'store_rejection_reason_confidential': RecordActionsMixin._handle_svc_evaluation,
    'unblock_next_term_registration': RecordActionsMixin._handle_svc_gate,
    'update_schedule': RecordActionsMixin._handle_update_therapy_schedule,
    'update_therapist': RecordActionsMixin._handle_update_therapist,
    'update_total_hours': RecordActionsMixin._handle_svc_lms,
    'upload_certificate_to_portal': RecordActionsMixin._handle_svc_document,
}
