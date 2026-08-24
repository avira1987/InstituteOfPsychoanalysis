"""Process execution API endpoints."""

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import AliasChoices, BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import get_settings
from app.api.auth import get_current_user, require_role
from app.models.operational_models import User, ProcessInstance, Student, SupportTicket, TicketComment
from app.services.panel_notification_dismiss import dismiss_notifications_for_instance
from app.core.engine import (
    StateMachineEngine, ProcessNotFoundError,
    InstanceNotFoundError, InvalidTransitionError, UnauthorizedError,
)
from sqlalchemy.orm.attributes import flag_modified

from app.meta.loader import MetadataLoader
from app.meta.process_forms import get_process_forms, get_process_ui_requirements, get_state_assigned_role
from app.services.installment_settings_service import (
    forms_with_installment_policy,
    new_installment_disabled_reason,
)
from app.meta.process_data_access import (
    apply_data_update_to_context,
    editable_field_names,
    extract_values,
    first_role_that_can_edit_forms,
    sanitize_editable_payload,
    visible_field_names,
    visible_forms_for_role,
)
from app.meta.course_selection_validation import (
    course_selection_config,
    normalize_course_codes,
    validate_selected_courses_for_process,
)
from app.meta.student_step_forms import (
    apply_register_to_context,
    apply_unlock_to_context,
    clear_step_otp_verified_flags,
    context_has_step_otp_verified,
    filter_forms_for_student,
    process_state_requires_step_otp,
    sanitize_form_values,
    sanitize_operator_form_values,
    stamp_step_otp_verified,
    validate_operator_step_forms,
    validate_student_step_forms,
)
from app.services.student_service import REGISTRATION_PROCESS_CODES, StudentService
from app.services.edit_request_router import (
    find_edit_request_rule,
    normalize_requested_fields,
    resolve_edit_request_assignee,
)
from app.api.ticket_routes import resolve_triage_assignee

router = APIRouter(prefix="/api/process", tags=["Process"])


def _normalize_actor_role(role: Optional[str]) -> str:
    """نقش‌ها در متادیتا lowercase هستند؛ اگر DB رشتۀ متفاوت داشت، RBAC از بین نرود."""
    from app.core.user_roles import canonical_portal_role

    s = canonical_portal_role(role)
    return s or "student"


async def _ensure_step_otp_verified_for_register(
    db: AsyncSession,
    *,
    current_user: User,
    instance: ProcessInstance,
    sanitized: dict,
) -> dict:
    """دروازه OTP مرحله: فلگ سروری پس از /step-otp/verify، یا تأیید otp_code در همان register."""
    if not process_state_requires_step_otp(instance.process_code, instance.current_state_code):
        return sanitized

    if context_has_step_otp_verified(instance.context_data, instance.current_state_code):
        sanitized["step_otp_verified"] = True
        return sanitized

    otp_code = str(sanitized.get("otp_code") or "").strip()
    if not otp_code:
        raise HTTPException(status_code=400, detail="کد پیامکی الزامی است.")
    phone = (current_user.phone or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="شماره موبایل در پروفایل شما ثبت نشده است.")
    from app.services.otp_service import verify_otp_code_only

    otp_res = await verify_otp_code_only(db, phone, otp_code)
    if not otp_res.get("success"):
        raise HTTPException(
            status_code=400,
            detail=otp_res.get("error") or "کد پیامکی نامعتبر است.",
        )
    sanitized["step_otp_verified"] = True
    return sanitized


def _portal_role_can_act_on_state(actor_role: str, process_code: str, state_code: str) -> bool:
    from app.meta.operator_state_catalog import (
        normalize_assigned_role,
        portal_role_can_act_on_assigned_role,
    )
    from app.services.semester_prep_rbac import portal_role_can_act_on_prep_state

    if actor_role == "admin":
        return True
    prep_ok = portal_role_can_act_on_prep_state(actor_role, process_code, state_code)
    if prep_ok is not None:
        return prep_ok
    assigned = get_state_assigned_role(process_code, state_code)
    if not assigned:
        return True
    norm_assigned = normalize_assigned_role(assigned)
    # پورتال دانشجو/متقاضی روی مراحل assigned به student یا applicant اقدام می‌کند
    if actor_role in ("student", "applicant") and norm_assigned in ("student", "applicant"):
        return True
    return portal_role_can_act_on_assigned_role(actor_role, norm_assigned)


def _user_can_act_on_state(user: User, process_code: str, state_code: str) -> bool:
    """اجتماع نقش‌های کاربر — اگر هر نقش بتواند روی مرحله اقدام کند."""
    from app.core.user_roles import normalize_user_roles

    roles = normalize_user_roles(user)
    if "admin" in roles:
        return True
    return any(_portal_role_can_act_on_state(r, process_code, state_code) for r in roles)


def _lock_forms_when_cannot_act(forms: list, *, can_act: bool) -> list:
    """اگر نقش جاری مسئول این مرحله نیست، همهٔ فیلدها را فقط‌خواندنی می‌کند."""
    if can_act:
        return forms
    locked: list = []
    for form in forms:
        form_copy = dict(form)
        fields = []
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            f = dict(field)
            f["__editable"] = False
            fields.append(f)
        form_copy["fields"] = fields
        locked.append(form_copy)
    return locked


async def _ensure_student_owns_instance(
    db: AsyncSession,
    current_user: User,
    instance: Optional[ProcessInstance],
) -> None:
    """دانشجو فقط فرایندهای خودش را ببیند/اجرا کند (از دور زدن با instance_id غیر)."""
    if instance is None:
        return
    if _normalize_actor_role(current_user.role) != "student":
        return
    r = await db.execute(select(Student).where(Student.user_id == current_user.id))
    st = r.scalars().first()
    if not st or st.id != instance.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این فرایند متعلق به حساب شما نیست.",
        )


# فیلدهای محرمانهٔ مصاحبه/ارزیابی که هرگز نباید به دانشجو نمایش داده شوند.
# (فرم نتیجهٔ مصاحبه در هر دو فرایند ثبت‌نام confidential است.)
_STUDENT_REDACTED_CONTEXT_KEYS = frozenset(
    {
        # دوره آشنایی
        "interviewer_notes",
        # دوره جامع
        "interview_evaluation_notes",
        "interview_rejection_reason",
        "interview_suggestion_text",
        "rejection_reason",
        "evaluation_notes",
        "suggestion_text",
    }
)


def _redact_confidential_for_student(status: dict, current_user: User) -> dict:
    """اگر درخواست‌کننده دانشجو است، فیلدهای محرمانهٔ ارزیابی مصاحبه را از context_data حذف کن."""
    if _normalize_actor_role(current_user.role) != "student":
        return status
    if not isinstance(status, dict):
        return status
    ctx = status.get("context_data")
    if isinstance(ctx, dict) and any(k in ctx for k in _STUDENT_REDACTED_CONTEXT_KEYS):
        status = dict(status)
        status["context_data"] = {
            k: v for k, v in ctx.items() if k not in _STUDENT_REDACTED_CONTEXT_KEYS
        }
    return status


def _debug_log_process_event(message: str, data: dict) -> None:
    """NDJSON برای جلسهٔ دیباگ (بدون PII/رمز)."""
    try:
        log_path = Path(__file__).resolve().parents[3] / "debug-a0eba8.log"
        payload = {
            "sessionId": "a0eba8",
            "location": "api/process/routes.py",
            "message": message,
            "data": data,
            "timestamp": int(__import__("time").time() * 1000),
        }
        with open(log_path, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _enrich_therapy_session_increase_start(
    initial_context: Optional[dict],
    student_row: Student,
) -> Optional[dict]:
    """پیش‌فرض therapist_id و شمارندهٔ جلسات هنگام آغاز فرایند افزایش جلسات هفتگی."""
    out = dict(initial_context or {})
    if student_row.therapist_id:
        out.setdefault("therapist_id", str(student_row.therapist_id))
    out.setdefault("weekly_sessions_at_start", student_row.weekly_sessions)
    return out


def _enrich_supervision_session_increase_start(
    initial_context: Optional[dict],
    student_row: Student,
) -> Optional[dict]:
    """پیش‌فرض شمارندهٔ جلسات هفتگی سوپرویژن هنگام آغاز فرایند ۲۱."""
    out = dict(initial_context or {})
    extra = StateMachineEngine._as_mapping(student_row.extra_data)
    sup_weekly = extra.get("supervision_weekly_sessions")
    if sup_weekly is None:
        sup_weekly = extra.get("weekly_supervision_sessions")
    if sup_weekly is not None:
        try:
            out.setdefault("supervision_weekly_sessions", int(sup_weekly))
        except (TypeError, ValueError):
            pass
    return out


async def _enrich_class_session_cancellation_start(
    db: AsyncSession,
    initial_context: Optional[dict],
    student_row: Student,
    actor_user: User,
) -> Optional[dict]:
    """پیش‌بارگذاری دروس و جلسات هنگام آغاز فرایند ۵۶."""
    from app.services.class_session_cancellation_service import (
        build_class_session_cancellation_context,
    )

    role = (actor_user.role or "").strip()
    all_term = role in (
        "scientific_officer_course_committee",
        "course_committee_executive",
        "admin",
        "staff",
        "deputy_education",
    )
    out = dict(initial_context or {})
    extra = await build_class_session_cancellation_context(
        db,
        actor_user,
        out,
        all_term=all_term,
        student=student_row,
    )
    out.update(extra)
    return out


def _apply_class_session_cancellation_trigger_rules(
    trigger_event: str,
    payload: dict,
    context_data: Optional[dict],
) -> dict:
    """اعتبارسنجی رویداد cancellation_confirmed (فرایند ۵۶)."""
    p = dict(payload or {})
    ctx = StateMachineEngine._as_mapping(context_data)
    merged = {**ctx, **p}

    if trigger_event == "cancellation_confirmed":
        lesson = str(merged.get("lesson_id") or merged.get("course_code") or "").strip()
        session = merged.get("session_to_cancel")
        makeup_date = str(merged.get("makeup_date") or "").strip()
        makeup_time = str(merged.get("makeup_time") or "").strip()
        if not lesson:
            raise HTTPException(status_code=400, detail="نام درس الزامی است.")
        if not session or str(session).strip() == "":
            raise HTTPException(status_code=400, detail="جلسه جهت کنسلی الزامی است.")
        if not makeup_date or not makeup_time:
            raise HTTPException(
                status_code=400,
                detail="تاریخ و ساعت جلسه جبرانی الزامی است؛ ابتدا درس و جلسه را در فرم انتخاب کنید.",
            )
        p.setdefault("lesson_id", lesson)
        p.setdefault("session_to_cancel", session)
        p.setdefault("makeup_date", makeup_date)
        p.setdefault("makeup_time", makeup_time)
    return p


async def _enrich_supervisor_session_cancellation_start(
    db: AsyncSession,
    initial_context: Optional[dict],
    student_row: Student,
) -> Optional[dict]:
    """پیش‌بارگذاری لیست جلسات ۴ هفته آینده هنگام آغاز فرایند ۲۶."""
    from app.services.supervisor_session_cancellation_service import (
        get_supervisor_sessions_next_4_weeks,
    )

    out = dict(initial_context or {})
    if student_row.supervisor_id:
        out.setdefault("supervisor_id", str(student_row.supervisor_id))
    sessions = await get_supervisor_sessions_next_4_weeks(
        db,
        student_row.supervisor_id,
        student_row.id,
        display_weeks=4,
    )
    out["supervisor_sessions_next_4_weeks"] = sessions
    return out


def _apply_supervisor_session_cancellation_trigger_rules(
    trigger_event: str,
    payload: dict,
    context_data: Optional[dict],
) -> dict:
    """اعتبارسنجی رویدادهای supervisor_session_cancellation (فرایند ۲۶)."""
    p = dict(payload or {})
    ctx = StateMachineEngine._as_mapping(context_data)
    merged = {**ctx, **p}

    if trigger_event in ("makeup_date_entered", "supervisor_entered_new_time"):
        if merged.get("makeup_option") != "no_makeup":
            pd = (merged.get("proposed_date") or "").strip()
            pt = (merged.get("proposed_time") or "").strip()
            if not pd or not pt:
                raise HTTPException(
                    status_code=400,
                    detail="تاریخ و ساعت جلسه جبرانی الزامی است.",
                )
            p.setdefault("proposed_date", pd)
            p.setdefault("proposed_time", pt)
    elif trigger_event == "student_counter_proposed":
        if not str(merged.get("counter_proposal_text") or "").strip():
            raise HTTPException(
                status_code=400,
                detail="لطفاً تاریخ و ساعت پیشنهادی خود را در توضیحات بنویسید.",
            )
    return p


async def _enrich_supervision_session_reduction_start(
    db: AsyncSession,
    initial_context: Optional[dict],
    student_row: Student,
) -> Optional[dict]:
    """پیش‌فرض شمارندهٔ جلسات و ساعات آموزشی هنگام آغاز فرایند ۲۴."""
    from app.services.attendance_service import AttendanceService

    out = dict(initial_context or {})
    extra = StateMachineEngine._as_mapping(student_row.extra_data)
    sup_weekly = extra.get("supervision_weekly_sessions")
    if sup_weekly is None:
        sup_weekly = extra.get("weekly_supervision_sessions")
    if sup_weekly is not None:
        try:
            out.setdefault("supervision_weekly_sessions", int(sup_weekly))
        except (TypeError, ValueError):
            pass
    else:
        out.setdefault("supervision_weekly_sessions", 1)

    att = AttendanceService(db)
    m = await att.get_therapy_completion_metrics(student_row.id)
    out.setdefault("therapy_hours_2x", float(m["therapy_hours_2x"]))
    out.setdefault("clinical_hours", float(m["clinical_hours"]))
    out.setdefault("supervision_hours", float(m["supervision_hours"]))
    out.setdefault("therapy_threshold", float(extra.get("therapy_threshold", 250)))
    out.setdefault("clinical_threshold", float(extra.get("clinical_threshold", 750)))
    out.setdefault("supervision_threshold", float(extra.get("supervision_threshold", 150)))
    return out


async def _enrich_lesson_start_context(
    db: AsyncSession,
    initial_context: Optional[dict],
    student_row: Student,
) -> Optional[dict]:
    """دروس قابل انتخاب را از TermCourseOffering فعال (و در صورت نبود از lms) seed می‌کند."""
    from app.services.term_course_offering_service import (
        list_offerings,
        offering_to_option,
    )

    out = dict(initial_context or {})
    extra = StateMachineEngine._as_mapping(student_row.extra_data)
    lms = StateMachineEngine._as_mapping(extra.get("lms"))
    program_kind = (student_row.course_type or "introductory").strip() or "introductory"
    term_number = int(student_row.current_term or 1)
    offerings = await list_offerings(
        db,
        program_kind=program_kind,
        term_number=term_number,
        active_only=True,
    )
    offering_options = [offering_to_option(r) for r in offerings]
    available_codes = [o["value"] for o in offering_options if o.get("value")]
    if not available_codes:
        available_codes = list(lms.get("available_courses") or lms.get("enrolled_courses") or [])
        # normalize string codes from enrolled list
        available_codes = [
            (c.get("code") or c.get("course_code") or c) if isinstance(c, dict) else c
            for c in available_codes
        ]
        available_codes = [str(c).strip() for c in available_codes if c]
    if not available_codes:
        # demo/empty fallback — marked so UI/tests can detect synthetic catalog
        term = int(student_row.current_term or 1)
        ctype = student_row.course_type or "introductory"
        available_codes = [f"{ctype}_term{term}_course{i}" for i in range(1, 4)]
        out["lesson_catalog_synthetic"] = True
    else:
        out["lesson_catalog_synthetic"] = False
    out.setdefault("lms", dict(lms))
    out["lms"]["available_courses"] = available_codes
    if offering_options:
        out["lms"]["available_course_options"] = offering_options
        out["prep_course_rows"] = [
            {
                "course_code": o.get("value"),
                "course_name": o.get("label_fa") or o.get("value"),
                "teaching_assistant": o.get("teaching_assistant_name") or "",
                "instructor": o.get("instructor_name") or "",
                "day": o.get("day"),
                "time": o.get("time_text"),
            }
            for o in offering_options
        ]
    return out


def _apply_therapy_session_increase_trigger_rules(
    trigger_event: str,
    payload: dict,
) -> dict:
    """اعتبارسنجی فیلدهای رویداد برای therapy_session_increase؛ نگاشت فیلدهای جدید به first_session_date."""
    p = dict(payload or {})
    if trigger_event == "day_time_entered":
        fd = (p.get("first_session_date") or "").strip()
        tm = (p.get("preferred_time_hhmm") or "").strip()
        if not fd or not tm:
            raise HTTPException(
                status_code=400,
                detail="تاریخ و ساعت جلسه الزامی است (first_session_date، preferred_time_hhmm).",
            )
    elif trigger_event == "therapist_proposed_alternative":
        ad = (p.get("therapist_alternative_date") or "").strip()
        at = (p.get("therapist_alternative_time_hhmm") or "").strip()
        if not ad or not at:
            raise HTTPException(
                status_code=400,
                detail="برای پیشنهاد جایگزین، تاریخ و ساعت جایگزین را وارد کنید.",
            )
    elif trigger_event == "student_reentered_time":
        nd = (p.get("new_first_session_date") or "").strip()
        nt = (p.get("new_preferred_time_hhmm") or "").strip()
        if not nd or not nt:
            raise HTTPException(
                status_code=400,
                detail="برای ارسال زمان جدید، تاریخ و ساعت جدید الزامی است.",
            )
        p["first_session_date"] = nd
        p["preferred_time_hhmm"] = nt
    return p


def _apply_supervision_session_increase_trigger_rules(
    trigger_event: str,
    payload: dict,
) -> dict:
    """اعتبارسنجی رویدادهای supervision_session_increase (فرایند ۲۱)."""
    p = dict(payload or {})
    if trigger_event == "day_time_entered":
        fd = (p.get("first_session_date") or "").strip()
        tm = (p.get("preferred_time_hhmm") or "").strip()
        if not fd or not tm:
            raise HTTPException(
                status_code=400,
                detail="تاریخ و ساعت جلسه الزامی است (first_session_date، preferred_time_hhmm).",
            )
    elif trigger_event == "supervisor_proposed_alternative":
        ad = (p.get("supervisor_alternative_date") or "").strip()
        at = (p.get("supervisor_alternative_time_hhmm") or "").strip()
        if not ad or not at:
            raise HTTPException(
                status_code=400,
                detail="برای پیشنهاد جایگزین، تاریخ و ساعت جایگزین را وارد کنید.",
            )
    elif trigger_event == "student_reentered_time":
        nd = (p.get("new_first_session_date") or "").strip()
        nt = (p.get("new_preferred_time_hhmm") or "").strip()
        if not nd or not nt:
            raise HTTPException(
                status_code=400,
                detail="برای ارسال زمان جدید، تاریخ و ساعت جدید الزامی است.",
            )
        p["first_session_date"] = nd
        p["preferred_time_hhmm"] = nt
    return p


def _parse_supervision_reduction_selected(raw) -> list[str]:
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


def _apply_supervision_session_reduction_trigger_rules(
    trigger_event: str,
    payload: dict,
    context_data: Optional[dict] = None,
) -> dict:
    """اعتبارسنجی رویدادهای supervision_session_reduction (فرایند ۲۴)."""
    p = dict(payload or {})
    ctx = StateMachineEngine._as_mapping(context_data)

    if trigger_event == "frequency_day_time_entered":
        freq = (p.get("frequency") or ctx.get("frequency") or "").strip()
        day = (p.get("day") or ctx.get("day") or "").strip()
        tm = (p.get("time") or ctx.get("time") or "").strip()
        if not freq or not day or not tm:
            raise HTTPException(
                status_code=400,
                detail="توالی، روز هفته و ساعت برگزاری الزامی است (frequency، day، time).",
            )
        if freq not in ("2", "3", "4"):
            raise HTTPException(
                status_code=400,
                detail="توالی باید ۲، ۳ یا ۴ هفته یک‌بار باشد.",
            )
    elif trigger_event == "sessions_selected":
        merged = {**ctx, **p}
        selected = _parse_supervision_reduction_selected(merged.get("selected_sessions"))
        if not selected:
            raise HTTPException(
                status_code=400,
                detail="حداقل یک جلسهٔ سوپرویژن برای حذف انتخاب کنید.",
            )
        try:
            weekly = int(merged.get("supervision_weekly_sessions") or 1)
        except (TypeError, ValueError):
            weekly = 1
        remaining = weekly - len(selected)
        if remaining < 1:
            raise HTTPException(
                status_code=400,
                detail="حداقل یک جلسهٔ سوپرویژن در هفته باید باقی بماند.",
            )
        p["supervision_remaining_after_reduction"] = remaining
        p["selected_sessions"] = selected
    return p


_EDUCATIONAL_LEAVE_MEETING_KEYS = (
    "committee_meeting_at",
    "committee_meeting_mode",
    "committee_meeting_link",
    "committee_meeting_location_fa",
)


def _merge_educational_leave_payload_from_context(
    instance: ProcessInstance,
    payload: dict,
) -> dict:
    """فیلدهای ثبت‌شده در فرم اپراتور را به payload ترنزیشن اضافه می‌کند."""
    p = dict(payload or {})
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    for key in _EDUCATIONAL_LEAVE_MEETING_KEYS + ("rejection_reason_fa", "committee_notes_internal"):
        if key not in p or p.get(key) in (None, ""):
            if ctx.get(key) not in (None, ""):
                p[key] = ctx[key]
    return p


def _validate_educational_leave_committee_set_meeting(payload: dict) -> None:
    p = payload or {}
    cat = (p.get("committee_meeting_at") or "").strip() if isinstance(p.get("committee_meeting_at"), str) else p.get("committee_meeting_at")
    if not cat:
        raise HTTPException(
            status_code=400,
            detail="تاریخ و ساعت جلسه الزامی است؛ ابتدا فرم مرحله را ثبت کنید (committee_meeting_at).",
        )
    mode = (p.get("committee_meeting_mode") or "").strip()
    if mode not in ("online", "in_person"):
        raise HTTPException(
            status_code=400,
            detail="نحوهٔ برگزاری جلسه را مشخص کنید: committee_meeting_mode = online یا in_person",
        )
    if mode == "online" and not (p.get("committee_meeting_link") or "").strip():
        raise HTTPException(status_code=400, detail="برای جلسه آنلاین، لینک جلسه (committee_meeting_link) الزامی است.")
    if mode == "in_person" and not (p.get("committee_meeting_location_fa") or "").strip():
        raise HTTPException(
            status_code=400,
            detail="برای جلسه حضوری، آدرس یا محل (committee_meeting_location_fa) الزامی است.",
        )


def _validate_educational_leave_committee_rejected(payload: dict) -> None:
    reason = (payload.get("rejection_reason_fa") or "").strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail="علت رد الزامی است؛ ابتدا فرم مرحله را با فیلد «علت رد» ثبت کنید.",
        )


_TA_TRACK_MEETING_KEYS = (
    "meeting_date",
    "meeting_time",
    "meeting_type",
    "meeting_link",
    "meeting_location_fa",
    "path",
    "new_tracks",
    "result",
)


def _merge_ta_track_change_payload_from_context(
    instance: ProcessInstance,
    payload: dict,
) -> dict:
    p = dict(payload or {})
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    for key in _TA_TRACK_MEETING_KEYS:
        if key not in p or p.get(key) in (None, ""):
            if ctx.get(key) not in (None, ""):
                p[key] = ctx[key]
    return p


def _ta_track_form_submitted(ctx: dict, state_code: str) -> bool:
    submitted = StateMachineEngine._as_mapping(ctx.get("__student_forms_submitted_states"))
    return bool(submitted.get(state_code))


def _validate_ta_track_change_meeting_registered(
    instance: ProcessInstance,
    payload: dict,
) -> dict:
    from app.services.ta_track_change_service import ensure_meeting_fields

    ctx = StateMachineEngine._as_mapping(instance.context_data)
    if not _ta_track_form_submitted(ctx, "course_committee_review"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم «ثبت زمان و مشخصات جلسه» را تکمیل و ثبت کنید.",
        )
    p = _merge_ta_track_change_payload_from_context(instance, payload)
    p = ensure_meeting_fields(p, instance.id)
    date = (p.get("meeting_date") or "").strip() if isinstance(p.get("meeting_date"), str) else p.get("meeting_date")
    if not date:
        raise HTTPException(status_code=400, detail="تاریخ جلسه الزامی است.")
    time = (p.get("meeting_time") or "").strip() if isinstance(p.get("meeting_time"), str) else p.get("meeting_time")
    if not time:
        raise HTTPException(status_code=400, detail="ساعت جلسه الزامی است.")
    mode = (p.get("meeting_type") or "").strip()
    if mode not in ("online", "in_person"):
        raise HTTPException(status_code=400, detail="نحوهٔ برگزاری جلسه (حضوری/آنلاین) الزامی است.")
    if mode == "online" and not (p.get("meeting_link") or "").strip():
        raise HTTPException(status_code=400, detail="لینک جلسه آنلاین تولید نشد.")
    return p


async def _validate_ta_track_change_approved(
    db: AsyncSession,
    instance: ProcessInstance,
    payload: dict,
) -> dict:
    from app.models.operational_models import Student
    from app.services.ta_track_change_service import validate_new_tracks

    ctx = StateMachineEngine._as_mapping(instance.context_data)
    if not _ta_track_form_submitted(ctx, "meeting_scheduled"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم «نتیجه جلسه و تخصیص رسته‌ها» را تکمیل و ثبت کنید.",
        )
    p = _merge_ta_track_change_payload_from_context(instance, payload)
    result = (p.get("result") or ctx.get("result") or "").strip()
    if result != "approve":
        raise HTTPException(status_code=400, detail="در فرم «موافقت» انتخاب نشده است.")
    path = (p.get("path") or ctx.get("path") or "").strip()
    raw_tracks = p.get("new_tracks") or ctx.get("new_tracks") or []
    tracks = (
        [str(x).strip() for x in raw_tracks if x is not None and str(x).strip()]
        if isinstance(raw_tracks, list)
        else [str(raw_tracks).strip()] if str(raw_tracks).strip() else []
    )
    student = await db.get(Student, instance.student_id)
    err = validate_new_tracks(student, path, tracks)
    if err:
        raise HTTPException(status_code=400, detail=err)
    p["path"] = path
    p["new_tracks"] = tracks
    return p


def _validate_ta_track_change_path_chosen(instance: ProcessInstance, payload: dict) -> None:
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    if not _ta_track_form_submitted(ctx, "ta_click"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم «انتخاب مسیر» را تکمیل و ثبت کنید.",
        )
    path = (payload.get("path") or ctx.get("path") or "").strip()
    if path not in ("add", "change"):
        raise HTTPException(status_code=400, detail="مسیر درخواست (add/change) در فرم ثبت نشده است.")


def _validate_educational_leave_student_return(instance: ProcessInstance) -> None:
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    if not ctx.get("return_registration_confirmed"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم تأیید بازگشت را تکمیل و ثبت کنید (تیک «ثبت‌نام ترم آینده را انجام داده‌ام»).",
        )


def _merge_non_registration_payload_from_context(
    instance: ProcessInstance,
    payload: dict,
) -> dict:
    p = dict(payload or {})
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    for key in _EDUCATIONAL_LEAVE_MEETING_KEYS + ("decision", "weeks_since_start", "weeks_since_term_start"):
        if key not in p or p.get(key) in (None, ""):
            if ctx.get(key) not in (None, ""):
                p[key] = ctx[key]
    return p


def _non_registration_form_submitted(ctx: dict, state_code: str) -> bool:
    submitted = StateMachineEngine._as_mapping(ctx.get("__student_forms_submitted_states"))
    return bool(submitted.get(state_code))


def _validate_student_non_registration_meeting_scheduled(instance: ProcessInstance, payload: dict) -> None:
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    if not _non_registration_form_submitted(ctx, "list_generated"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم «تعیین جلسه» را تکمیل و ثبت کنید، سپس دکمهٔ ثبت جلسه را بزنید.",
        )
    _validate_educational_leave_committee_set_meeting(payload)


def _validate_student_non_registration_choice(
    instance: ProcessInstance,
    payload: dict,
    trigger_event: str,
) -> None:
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    if not _non_registration_form_submitted(ctx, "meeting_held"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم «ثبت نتیجه جلسه» را تکمیل و ثبت کنید، سپس دکمهٔ تصمیم را بزنید.",
        )
    decision = (payload.get("decision") or ctx.get("decision") or "").strip()
    mapping = {
        "choice_register": "register",
        "choice_leave": "leave",
        "choice_withdrawal": "withdrawal",
    }
    expected = mapping.get(trigger_event)
    if not expected or decision != expected:
        raise HTTPException(
            status_code=400,
            detail="تصمیم ثبت‌شده در فرم با دکمهٔ انتخاب‌شده هم‌خوان نیست.",
        )
    if trigger_event == "choice_register":
        weeks_raw = payload.get("weeks_since_start") or payload.get("weeks_since_term_start")
        if weeks_raw is None:
            weeks_raw = ctx.get("weeks_since_start") or ctx.get("weeks_since_term_start")
        try:
            weeks = int(weeks_raw)
        except (TypeError, ValueError):
            weeks = None
        if weeks is not None and weeks > 4:
            raise HTTPException(
                status_code=400,
                detail="گزینهٔ ثبت‌نام فقط تا ۴ هفته پس از شروع کلاس‌ها مجاز است.",
            )


def _referral_rows_from_payload(ctx: dict, payload: dict) -> list[dict]:
    rows = payload.get("patient_referral_rows")
    if not isinstance(rows, list) or not rows:
        rows = ctx.get("patient_referral_rows")
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _merge_intern_bulk_referral_payload(instance: ProcessInstance, payload: dict) -> dict:
    p = dict(payload or {})
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    for key in (
        "meeting_datetime",
        "meeting_held",
        "referral_conditions",
        "patient_referral_rows",
    ):
        if key not in p or p.get(key) in (None, "", []):
            if ctx.get(key) not in (None, "", []):
                p[key] = ctx[key]
    return p


def _operator_form_submitted(ctx: dict, state_code: str) -> bool:
    from app.meta.student_step_forms import CTX_SUBMITTED

    submitted = StateMachineEngine._as_mapping(ctx.get(CTX_SUBMITTED))
    return bool(submitted.get(state_code))


def _validate_semester_prep_interview_scheduling_form(form_values: dict) -> None:
    """اعتبارسنجی فرم زمان‌بندی مصاحبه در آماده‌سازی ترم."""
    mode_fa = (form_values.get("interview_mode") or "").strip()
    if mode_fa not in ("حضوری", "آنلاین"):
        raise HTTPException(
            status_code=400,
            detail="نوع مصاحبه را مشخص کنید: حضوری یا آنلاین.",
        )
    if mode_fa == "حضوری":
        loc = (
            (form_values.get("interview_location_fa") or form_values.get("interview_location_or_link") or "")
            .strip()
        )
        if not loc:
            raise HTTPException(
                status_code=400,
                detail="برای مصاحبهٔ حضوری، آدرس یا محل برگزاری (interview_location_fa) الزامی است.",
            )


def _validate_semester_prep_interviewer_assignment_form(form_values: dict) -> None:
    """اعتبارسنجی بازه‌های تاریخ مصاحبه در مرحلهٔ تعیین مصاحبه‌کنندگان."""
    from app.services.semester_prep_service import semester_prep_interview_date_range_errors

    errors = semester_prep_interview_date_range_errors(form_values)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=errors[0] if len(errors) == 1 else "؛ ".join(errors),
        )


def _validate_semester_prep_calendar_form(form_values: dict) -> None:
    """اعتبارسنجی تاریخ‌های تقویم آموزشی (سال پرت و ترتیب تاریخ‌ها)."""
    from app.services.semester_prep_service import semester_prep_calendar_date_errors

    errors = semester_prep_calendar_date_errors(form_values)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=errors[0] if len(errors) == 1 else "؛ ".join(errors),
        )


def _validate_semester_prep_calendar_payload_if_present(
    process_code: str,
    field_values: dict,
) -> None:
    """اگر فیلدهای تقویم در payload هستند، اعتبارسنجی شوند."""
    from app.services.semester_prep_service import (
        FALL_PREP,
        SEMESTER_PREP_CALENDAR_DATE_FIELDS,
        SEMESTER_PREP_CALENDAR_DATE_RANGE_LIST_FIELDS,
        semester_prep_calendar_date_errors,
    )

    if process_code != FALL_PREP:
        return
    calendar_keys = set(SEMESTER_PREP_CALENDAR_DATE_FIELDS) | set(
        SEMESTER_PREP_CALENDAR_DATE_RANGE_LIST_FIELDS
    )
    if not calendar_keys.intersection(field_values.keys()):
        return
    errors = semester_prep_calendar_date_errors(field_values)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=errors[0] if len(errors) == 1 else "؛ ".join(errors),
        )


def _validate_semester_prep_step_form_submitted(instance: ProcessInstance, trigger_event: str) -> None:
    """قبل از پیشروی در آماده‌سازی ترم، فرم مرحلهٔ فعلی باید ثبت شده باشد."""
    from app.services.semester_prep_service import PREP_PROCESS_CODES

    if instance.process_code not in PREP_PROCESS_CODES:
        return
    if trigger_event == "sla_expired":
        return
    state = (instance.current_state_code or "").strip()
    if not state:
        return
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    if not _operator_form_submitted(ctx, state):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم این مرحله را با دکمهٔ «ثبت فرم این مرحله» تکمیل و ثبت کنید.",
        )


def _validate_intern_bulk_meeting_logged(instance: ProcessInstance, payload: dict) -> None:
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    if not _operator_form_submitted(ctx, "supervision_start"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم «ثبت جلسه و شرایط ارجاع» را تکمیل و ثبت کنید.",
        )
    conditions = str(payload.get("referral_conditions") or ctx.get("referral_conditions") or "").strip()
    if not conditions:
        raise HTTPException(status_code=400, detail="شرایط ارجاع الزامی است.")
    rows = _referral_rows_from_payload(ctx, payload)
    if not rows:
        raise HTTPException(status_code=400, detail="حداقل یک بیمار در لیست ارجاع ثبت کنید.")
    for i, row in enumerate(rows, start=1):
        if not str(row.get("patient_name") or "").strip():
            raise HTTPException(status_code=400, detail=f"نام بیمار در ردیف {i} الزامی است.")


def _validate_intern_bulk_student_contacts(payload: dict, ctx: dict) -> None:
    rows = _referral_rows_from_payload(ctx, payload)
    if not rows:
        raise HTTPException(status_code=400, detail="لیست بیماران یافت نشد.")
    for i, row in enumerate(rows, start=1):
        if not row.get("contacted"):
            raise HTTPException(
                status_code=400,
                detail=f"برای بیمار ردیف {i} تیک «صحبت انجام شد» الزامی است.",
            )
        if not str(row.get("contact_notes") or "").strip():
            raise HTTPException(
                status_code=400,
                detail=f"توضیحات صحبت با بیمار ردیف {i} الزامی است.",
            )


def _validate_intern_bulk_committee_notes(payload: dict, ctx: dict) -> None:
    if not _operator_form_submitted(ctx, "general_therapy_committee_review"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم کمیته درمان عموم را تکمیل و ثبت کنید.",
        )
    rows = _referral_rows_from_payload(ctx, payload)
    for i, row in enumerate(rows, start=1):
        if not row.get("committee_contacted"):
            raise HTTPException(
                status_code=400,
                detail=f"تیک «صحبت کمیته انجام شد» برای ردیف {i} الزامی است.",
            )
        if not str(row.get("referral_notes") or "").strip():
            raise HTTPException(
                status_code=400,
                detail=f"توضیحات ارجاع برای ردیف {i} الزامی است.",
            )


def _validate_intern_bulk_coordination_followup(payload: dict, ctx: dict) -> None:
    if not _operator_form_submitted(ctx, "coordination_followup"):
        raise HTTPException(
            status_code=400,
            detail="ابتدا فرم پیگیری را تکمیل و ثبت کنید.",
        )
    rows = _referral_rows_from_payload(ctx, payload)
    for i, row in enumerate(rows, start=1):
        if not row.get("followup_done"):
            raise HTTPException(
                status_code=400,
                detail=f"تیک «پیگیری انجام شد» برای ردیف {i} الزامی است.",
            )


# ثبت‌نام ترم/دوره وقتی مرخصی فعال است و class_access_blocked روی دانشجوست
_REGISTRATION_PROCESS_CODES_BLOCKED_UNDER_CLASS_ACCESS = frozenset(
    {
        "intro_second_semester_registration",
    }
)
logger = logging.getLogger(__name__)

_MAX_STEP_DOC_BYTES = 25 * 1024 * 1024
_ALLOWED_STEP_DOC_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/pdf",
    }
)
_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,48}$")


def _file_upload_field_names_for_process(
    process_code: str,
    state_code: Optional[str] = None,
) -> set[str]:
    """فیلدهای file_upload مجاز برای دانشجو — state فعلی + documents_upload (سازگاری عقب‌رو)."""
    states: list[str] = []
    if state_code:
        states.append(state_code)
    if "documents_upload" not in states:
        states.append("documents_upload")
    names: set[str] = set()
    for state in states:
        forms = get_process_forms(process_code, state_code=state)
        for form in filter_forms_for_student(forms):
            for field in form.get("fields") or []:
                if not isinstance(field, dict):
                    continue
                if field.get("type") != "file_upload":
                    continue
                name = field.get("name")
                if name:
                    names.add(name)
    return names


# ─── Request/Response Schemas ───────────────────────────────────

class StartProcessRequest(BaseModel):
    process_code: str
    student_id: Optional[str] = None
    user_id: Optional[str] = None
    initial_context: Optional[dict] = None


class TriggerTransitionRequest(BaseModel):
    trigger_event: str
    payload: Optional[dict] = None
    # شاخهٔ دقیق وقتی چند ترنزیشن trigger یکسان دارند (مثلاً نتیجهٔ مصاحبه)
    to_state: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("to_state", "toState"),
    )
    target_to_state: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("target_to_state", "targetToState"),
    )
    interview_result: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("interview_result", "interviewResult"),
    )


class RollbackRequest(BaseModel):
    """بازگشت نمونه به مرحلهٔ قبلی (اصلاح اشتباه) — فقط نقش‌های مجاز."""
    reason: Optional[str] = Field(None, max_length=2000)


class RestartProcessRequest(BaseModel):
    """شروع دوباره از ابتدا: بایگانی پروندهٔ فعلی و ساخت نمونهٔ جدید."""
    reason: Optional[str] = Field(None, max_length=2000)
    confirm: bool = Field(..., description="تأیید صریح کاربر الزامی است")


class RestartProcessResponse(BaseModel):
    success: bool
    old_instance_id: str
    new_instance_id: str
    process_code: str
    current_state: str
    error: Optional[str] = None


class StudentStepFormsRegisterRequest(BaseModel):
    form_values: dict


class StudentStepFormsUnlockRequest(BaseModel):
    """اگر state خالی باشد، همان وضعیت فعلی نمونه."""
    state_code: Optional[str] = None


class OperatorUpdateSelectedCoursesRequest(BaseModel):
    """ادمین/مسئول پذیرش: تغییر مستقیم دروس انتخاب‌شده در پروندهٔ فرایند."""
    selected_courses: list[str] = Field(..., min_length=1)
    reason: Optional[str] = Field(None, max_length=2000)


class OperatorStepFormsRegisterRequest(BaseModel):
    """اپراتور (نقش غیر دانشجو) پس از پر کردن فرم مرحله؛ مقادیر در context_data ذخیره می‌شود."""
    form_values: dict
    state_code: Optional[str] = None


class ProcessDataUpdateRequest(BaseModel):
    """ویرایش/به‌روزرسانی دادهٔ ثبت‌شدهٔ فرایند بر اساس مجوز نقش (editable_by)."""
    field_values: dict
    reason: Optional[str] = Field(None, max_length=2000)


class StudentEditRequestCreate(BaseModel):
    state_code: str
    form_code: Optional[str] = None
    field_names: list[str] = Field(default_factory=list)
    reason: str = Field(..., min_length=5, max_length=4000)
    proposed_values: Optional[dict] = None


class ProcessInstanceResponse(BaseModel):
    instance_id: str
    process_code: str
    current_state: str
    is_completed: bool
    is_cancelled: bool
    context_data: Optional[dict] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TransitionResultResponse(BaseModel):
    success: bool
    from_state: str
    to_state: Optional[str] = None
    trigger_event: Optional[str] = None
    error: Optional[str] = None
    actions: list[dict] = Field(default_factory=list)
    rule_results: list[dict] = Field(default_factory=list)
    simulated_sms: Optional[dict] = None
    simulated_sms_list: list[dict] = Field(default_factory=list)

    @field_validator("actions", mode="before")
    @classmethod
    def _coerce_actions(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s or s.lower() in ("null", "none"):
                return []
            try:
                parsed = json.loads(s)
            except (json.JSONDecodeError, TypeError):
                return []
            if parsed is None:
                return []
            return parsed if isinstance(parsed, list) else []
        return []


# ─── Endpoints ──────────────────────────────────────────────────

@router.get("/term-offerings")
async def get_term_offerings(
    program_kind: str = Query(..., description="introductory | comprehensive"),
    term_number: int = Query(..., ge=1, le=12),
    term_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Published course offerings for the active (or specified) term."""
    from app.services.term_course_offering_service import build_term_offerings_response

    return await build_term_offerings_response(
        db,
        program_kind=program_kind.strip(),
        term_number=term_number,
        term_code=term_code.strip() if term_code else None,
    )


@router.get("/definitions")
async def list_processes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active process definitions."""
    loader = MetadataLoader(db)
    processes = await loader.load_all_processes()
    return {"processes": processes}


@router.get("/definitions/{process_code}")
async def get_process_definition(
    process_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a full process definition with states and transitions."""
    loader = MetadataLoader(db)
    process = await loader.load_process(process_code)
    if not process:
        raise HTTPException(status_code=404, detail=f"Process '{process_code}' not found")
    return process


@router.get("/definitions/{process_code}/forms")
async def get_process_forms_for_state(
    process_code: str,
    state: Optional[str] = Query(None, description="Filter forms by used_in_state (e.g. current state)"),
    instance_id: Optional[str] = Query(None, description="Optional instance for pre_filled_from merge"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get form metadata for a process (for rendering in UI). Optional state filter for current state forms (BUILD_TODO § ز)."""
    from app.core.user_roles import normalize_user_roles, user_has_role

    raw_forms = get_process_forms(process_code, state_code=state)
    if user_has_role(current_user, "student", admin_bypass=False) and len(normalize_user_roles(current_user)) == 1:
        forms = raw_forms
    else:
        # اجتماع فیلدهای قابل‌رؤیت برای همهٔ نقش‌های کاربر
        seen_codes: set[str] = set()
        forms = []
        for r in normalize_user_roles(current_user):
            for f in visible_forms_for_role(raw_forms, r):
                code = (f.get("code") or f.get("form_code") or id(f))
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                forms.append(f)
        if not forms and user_has_role(current_user, "student", admin_bypass=False):
            forms = raw_forms
    can_act_on_state = _user_can_act_on_state(current_user, process_code, state or "")
    forms = _lock_forms_when_cannot_act(forms, can_act=can_act_on_state)
    state_assigned_role = get_state_assigned_role(process_code, state or "") if state else None
    suggested_context: dict = {}
    ctx_for_policy: dict | None = None
    if instance_id and state:
        try:
            iid = uuid.UUID(instance_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="instance_id نامعتبر")
        inst = await db.get(ProcessInstance, iid)
        if inst and inst.process_code == process_code:
            from app.services.process_form_prefill import apply_pre_filled_fields

            base_ctx = StateMachineEngine._as_mapping(inst.context_data)
            ctx_for_policy = base_ctx
            suggested_context = await apply_pre_filled_fields(
                db, process_code, state, base_ctx, student_id=inst.student_id,
            )
    forms = await forms_with_installment_policy(db, forms, ctx_for_policy)
    return {
        "process_code": process_code,
        "state": state,
        "forms": forms,
        "suggested_context": suggested_context,
        "state_assigned_role": state_assigned_role,
        "can_act_on_state": can_act_on_state,
    }


@router.post("/start", response_model=ProcessInstanceResponse)
async def start_process(
    request: StartProcessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new process instance (student case, or staff subject on INST-OPS carrier)."""
    from app.meta.process_start_scope import (
        MANUAL_START_OPERATOR_ROLES,
        get_manual_start_scope,
    )
    from app.services.institute_operational_anchor import (
        ensure_institute_operational_student,
        is_institute_operational_student,
    )

    actor_role = _normalize_actor_role(current_user.role)
    scope = get_manual_start_scope(request.process_code)
    initial_ctx = dict(request.initial_context or {}) if request.initial_context else {}
    subject_user: User | None = None

    if scope == "institute":
        raise HTTPException(
            status_code=400,
            detail=(
                "فرایندهای آماده‌سازی ترم را از هاب آماده‌سازی ترم "
                "(/panel/semester-prep) شروع کنید؛ شروع از ردیابی دانشجو یا مدیریت کاربران مجاز نیست."
            ),
        )

    if scope == "staff":
        if actor_role not in MANUAL_START_OPERATOR_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط پرسنل مجاز می‌توانند این فرایند را برای کاربر شروع کنند.",
            )
        if not (request.user_id or "").strip():
            raise HTTPException(
                status_code=400,
                detail="برای شروع این فرایند، شناسهٔ کاربر (user_id) الزامی است.",
            )
        try:
            subject_uuid = uuid.UUID(str(request.user_id).strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="شناسهٔ کاربر نامعتبر است.")
        subject_user = await db.get(User, subject_uuid)
        if not subject_user:
            raise HTTPException(status_code=404, detail="کاربر یافت نشد.")
        student_row = await ensure_institute_operational_student(db)
        student_uuid = student_row.id
        initial_ctx["subject_user_id"] = str(subject_user.id)
        initial_ctx["subject_username"] = subject_user.username
        initial_ctx["subject_user_role"] = (subject_user.role or "").strip()
        if subject_user.full_name_fa:
            initial_ctx["subject_user_name_fa"] = subject_user.full_name_fa
    else:
        # student scope
        if not (request.student_id or "").strip():
            raise HTTPException(
                status_code=400,
                detail="برای شروع این فرایند، شناسهٔ دانشجو (student_id) الزامی است.",
            )
        try:
            student_uuid = uuid.UUID(str(request.student_id).strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="شناسهٔ دانشجو نامعتبر است.")
        stmt = select(Student).where(Student.id == student_uuid)
        student_row = (await db.execute(stmt)).scalars().first()
        if not student_row:
            raise HTTPException(status_code=404, detail="Student not found")
        if is_institute_operational_student(student_row):
            raise HTTPException(
                status_code=400,
                detail=(
                    "این رکورد پرونده عملیاتی انستیتو است؛ فرایند دانشجو‌محور را "
                    "روی دانشجوی واقعی شروع کنید."
                ),
            )
        if actor_role == "student" and student_row.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط می‌توانید فرایند را برای پروفایل خودتان آغاز کنید.",
            )

    extra = StateMachineEngine._as_mapping(student_row.extra_data)
    student_svc = StudentService(db)
    if (
        scope == "student"
        and request.process_code in _REGISTRATION_PROCESS_CODES_BLOCKED_UNDER_CLASS_ACCESS
        and extra.get("class_access_blocked")
    ):
        raise HTTPException(
            status_code=400,
            detail="به‌دلیل مرخصی آموزشی فعال، ثبت‌نام ترم/درس تا زمان بازگشت و رفع مسدودیت در سامانه مجاز نیست.",
        )

    if request.process_code == "start_therapy":
        from app.services.admission_type_service import (
            SINGLE_COURSE_NO_START_THERAPY_FA,
            therapy_start_applicable,
            normalize_admission_type,
        )

        await student_svc.hydrate_admission_type(student_row)
        extra_st = StateMachineEngine._as_mapping(student_row.extra_data)
        admission_st = normalize_admission_type(extra_st.get("admission_type"))
        if not therapy_start_applicable(admission_st):
            raise HTTPException(status_code=400, detail=SINGLE_COURSE_NO_START_THERAPY_FA)

    if (
        scope == "student"
        and request.process_code == "intro_second_semester_registration"
    ):
        from app.services.admission_type_service import (
            TERM2_THERAPY_REQUIRED_FA,
            derive_has_active_therapist,
            normalize_admission_type,
            term2_blocked_without_active_therapist,
        )

        await student_svc.hydrate_admission_type(student_row)
        extra = StateMachineEngine._as_mapping(student_row.extra_data)
        gates = extra.get("gates") if isinstance(extra.get("gates"), dict) else {}
        admission_t2 = normalize_admission_type(extra.get("admission_type"))
        has_therapist = derive_has_active_therapist(student_row, extra)
        if gates.get("next_term_registration_blocked") or term2_blocked_without_active_therapist(
            admission_t2, has_active_therapist=has_therapist
        ):
            raise HTTPException(
                status_code=400,
                detail=TERM2_THERAPY_REQUIRED_FA,
            )

    if request.process_code == "introductory_course_registration":
        from app.services.registration_readiness_service import check_intro_registration_gate

        gate = await check_intro_registration_gate(db)
        if not gate.allowed:
            raise HTTPException(status_code=403, detail=gate.reason_fa)

    enrich_actor = subject_user if (scope == "staff" and subject_user is not None) else current_user

    if request.process_code == "therapy_session_increase":
        initial_ctx = _enrich_therapy_session_increase_start(initial_ctx, student_row)
    if request.process_code == "supervision_session_increase":
        initial_ctx = _enrich_supervision_session_increase_start(initial_ctx, student_row)
    if request.process_code == "supervisor_session_cancellation":
        initial_ctx = await _enrich_supervisor_session_cancellation_start(
            db, initial_ctx, student_row
        )
    if request.process_code == "supervision_session_reduction":
        initial_ctx = await _enrich_supervision_session_reduction_start(db, initial_ctx, student_row)
    if request.process_code == "lesson_start_per_term":
        initial_ctx = await _enrich_lesson_start_context(db, initial_ctx, student_row)
    if request.process_code == "class_session_cancellation":
        initial_ctx = await _enrich_class_session_cancellation_start(
            db, initial_ctx, student_row, enrich_actor
        )
    if request.process_code == "intro_second_semester_registration":
        from app.services.admission_type_service import (
            derive_has_active_therapist,
            normalize_admission_type,
        )

        extra_st = StateMachineEngine._as_mapping(student_row.extra_data)
        admission = normalize_admission_type(extra_st.get("admission_type"))
        if admission:
            initial_ctx.setdefault("admission_type", admission)
            initial_ctx.setdefault("interview_result", admission)
        initial_ctx["has_active_therapist"] = derive_has_active_therapist(student_row, extra_st)

    if scope == "student" and request.process_code in REGISTRATION_PROCESS_CODES:
        existing_reg = await student_svc.pick_best_active_registration_instance(
            student_uuid,
            request.process_code,
        )
        if existing_reg:
            await student_svc.set_primary_instance_for_student(student_row, existing_reg.id)
            await db.flush()
            return ProcessInstanceResponse(
                instance_id=str(existing_reg.id),
                process_code=existing_reg.process_code,
                current_state=existing_reg.current_state_code,
                is_completed=existing_reg.is_completed,
                is_cancelled=existing_reg.is_cancelled,
                context_data=existing_reg.context_data,
                started_at=existing_reg.started_at.isoformat() if existing_reg.started_at else None,
            )

    engine = StateMachineEngine(db)
    try:
        instance = await engine.start_process(
            process_code=request.process_code,
            student_id=student_uuid,
            actor_id=current_user.id,
            actor_role=actor_role,
            initial_context=initial_ctx or None,
        )
        await db.flush()
        if scope == "student" and request.process_code in REGISTRATION_PROCESS_CODES.union(
            {"educational_leave", "session_payment"}
        ):
            await student_svc.set_primary_instance_for_student(student_row, instance.id)
        if request.process_code == "intro_second_semester_registration":
            if instance.current_state_code == "eligibility_check":
                await student_svc.advance_intro_second_eligibility(
                    instance.id, current_user.id
                )
                instance = await engine.get_process_instance(instance.id)
            if scope == "student":
                await student_svc.set_primary_instance_for_student(student_row, instance.id)
        return ProcessInstanceResponse(
            instance_id=str(instance.id),
            process_code=instance.process_code,
            current_state=instance.current_state_code,
            is_completed=instance.is_completed,
            is_cancelled=instance.is_cancelled,
            context_data=instance.context_data,
            started_at=instance.started_at.isoformat() if instance.started_at else None,
        )
    except ProcessNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/trigger", response_model=TransitionResultResponse)
async def trigger_transition(
    instance_id: str,
    request: TriggerTransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute a state transition for a process instance."""
    engine = StateMachineEngine(db)
    merged_payload = dict(request.payload or {})
    # همیشه مقدار سطح بالای درخواست را اعمال کن (نه setdefault — ممکن است payload.to_state تهی باشد)
    if request.to_state:
        merged_payload["to_state"] = request.to_state
    if request.target_to_state:
        merged_payload["target_to_state"] = request.target_to_state
    if request.interview_result is not None:
        merged_payload["interview_result"] = request.interview_result

    inst_early = (
        await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))
    ).scalars().first()
    await _ensure_student_owns_instance(db, current_user, inst_early)
    if inst_early and inst_early.process_code == "start_therapy":
        from app.services.admission_type_service import (
            SINGLE_COURSE_NO_START_THERAPY_FA,
            therapy_start_applicable,
        )

        st_row = (
            await db.execute(select(Student).where(Student.id == inst_early.student_id))
        ).scalars().first()
        if st_row:
            svc_st = StudentService(db)
            await svc_st.hydrate_admission_type(st_row)
            extra_st = StateMachineEngine._as_mapping(st_row.extra_data)
            if not therapy_start_applicable(extra_st.get("admission_type")):
                raise HTTPException(status_code=400, detail=SINGLE_COURSE_NO_START_THERAPY_FA)
    if inst_early and inst_early.process_code == "therapy_session_increase":
        merged_payload = _apply_therapy_session_increase_trigger_rules(
            request.trigger_event,
            merged_payload,
        )
    if inst_early and inst_early.process_code == "supervision_session_increase":
        merged_payload = _apply_supervision_session_increase_trigger_rules(
            request.trigger_event,
            merged_payload,
        )
    if inst_early and inst_early.process_code == "supervision_session_reduction":
        merged_payload = _apply_supervision_session_reduction_trigger_rules(
            request.trigger_event,
            merged_payload,
            inst_early.context_data,
        )
    if inst_early and inst_early.process_code == "supervisor_session_cancellation":
        merged_payload = _apply_supervisor_session_cancellation_trigger_rules(
            request.trigger_event,
            merged_payload,
            inst_early.context_data,
        )
    if inst_early and inst_early.process_code == "class_session_cancellation":
        merged_payload = _apply_class_session_cancellation_trigger_rules(
            request.trigger_event,
            merged_payload,
            inst_early.context_data,
        )

    if request.trigger_event == "committee_set_meeting":
        inst_chk = (
            await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))
        ).scalars().first()
        if inst_chk and inst_chk.process_code == "educational_leave":
            merged_payload = _merge_educational_leave_payload_from_context(inst_chk, merged_payload)
            _validate_educational_leave_committee_set_meeting(merged_payload)

    if request.trigger_event == "committee_rejected":
        inst_chk = (
            await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))
        ).scalars().first()
        if inst_chk and inst_chk.process_code == "educational_leave":
            merged_payload = _merge_educational_leave_payload_from_context(inst_chk, merged_payload)
            _validate_educational_leave_committee_rejected(merged_payload)

    if request.trigger_event == "student_registered":
        inst_chk = (
            await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))
        ).scalars().first()
        if (
            inst_chk
            and inst_chk.process_code == "educational_leave"
            and inst_chk.current_state_code == "return_reminder_sent"
        ):
            _validate_educational_leave_student_return(inst_chk)

    inst_nr = (
        await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))
    ).scalars().first()
    if inst_nr and inst_nr.process_code == "student_non_registration":
        if request.trigger_event == "meeting_scheduled":
            merged_payload = _merge_non_registration_payload_from_context(inst_nr, merged_payload)
            _validate_student_non_registration_meeting_scheduled(inst_nr, merged_payload)
        if request.trigger_event in ("choice_register", "choice_leave", "choice_withdrawal"):
            merged_payload = _merge_non_registration_payload_from_context(inst_nr, merged_payload)
            _validate_student_non_registration_choice(inst_nr, merged_payload, request.trigger_event)

    inst_ref = (
        await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))
    ).scalars().first()
    if inst_ref and inst_ref.process_code == "intern_bulk_patient_referral":
        merged_payload = _merge_intern_bulk_referral_payload(inst_ref, merged_payload)
        ctx_ref = StateMachineEngine._as_mapping(inst_ref.context_data)
        if request.trigger_event == "meeting_and_conditions_logged":
            _validate_intern_bulk_meeting_logged(inst_ref, merged_payload)
        if request.trigger_event == "student_patient_contacts_done":
            _validate_intern_bulk_student_contacts(merged_payload, ctx_ref)
        if request.trigger_event == "committee_referral_notes_complete":
            _validate_intern_bulk_committee_notes(merged_payload, ctx_ref)
        if request.trigger_event == "coordination_followup_complete":
            _validate_intern_bulk_coordination_followup(merged_payload, ctx_ref)

    inst_ttc = (
        await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))
    ).scalars().first()
    if inst_ttc and inst_ttc.process_code == "ta_track_change":
        if request.trigger_event == "path_chosen":
            merged_payload = _merge_ta_track_change_payload_from_context(inst_ttc, merged_payload)
            _validate_ta_track_change_path_chosen(inst_ttc, merged_payload)
        if request.trigger_event == "meeting_registered":
            merged_payload = _validate_ta_track_change_meeting_registered(inst_ttc, merged_payload)
        if request.trigger_event == "approved":
            merged_payload = await _validate_ta_track_change_approved(db, inst_ttc, merged_payload)
        if request.trigger_event == "rejected":
            ctx_ttc = StateMachineEngine._as_mapping(inst_ttc.context_data)
            if not _ta_track_form_submitted(ctx_ttc, "meeting_scheduled"):
                raise HTTPException(
                    status_code=400,
                    detail="ابتدا فرم «نتیجه جلسه» را تکمیل و ثبت کنید.",
                )
            result = (merged_payload.get("result") or ctx_ttc.get("result") or "").strip()
            if result != "reject":
                raise HTTPException(status_code=400, detail="در فرم «عدم موافقت» انتخاب نشده است.")

    inst_prep = (
        await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))
    ).scalars().first()
    if inst_prep:
        from app.services.semester_prep_service import PREP_PROCESS_CODES

        _validate_semester_prep_step_form_submitted(inst_prep, request.trigger_event)
        if (
            inst_prep.process_code in PREP_PROCESS_CODES
            and request.trigger_event == "interviewers_assigned"
        ):
            ctx_prep = StateMachineEngine._as_mapping(inst_prep.context_data)
            _validate_semester_prep_interviewer_assignment_form(ctx_prep)

    role_norm = _normalize_actor_role(current_user.role)
    if role_norm == "student" and request.trigger_event in ("timeslot_selected", "interview_time_selected"):
        raise HTTPException(
            status_code=403,
            detail="وقت مصاحبه فقط پس از اعلام زمان‌ها در سامانه، از بخش «رزرو وقت مصاحبه» همین صفحه قابل انتخاب است؛ "
            "با دکمهٔ ثبت مرحله نمی‌توان وقت را عوض یا رد کرد.",
        )

    try:
        result = await engine.execute_transition(
            instance_id=uuid.UUID(instance_id),
            trigger_event=request.trigger_event,
            actor_id=current_user.id,
            actor_role=role_norm,
            payload=merged_payload if merged_payload else None,
        )
        _debug_log_process_event(
            "trigger_result",
            {
                "trigger_event": request.trigger_event,
                "actor_role": role_norm,
                "success": result.success,
                "to_state": result.to_state,
                "error": result.error,
            },
        )
        if result.success:
            await dismiss_notifications_for_instance(
                db,
                user_id=current_user.id,
                instance_id=uuid.UUID(instance_id),
            )
        return TransitionResultResponse(
            success=result.success,
            from_state=result.from_state,
            to_state=result.to_state,
            trigger_event=result.trigger_event,
            error=result.error,
            actions=result.actions,
            rule_results=[r.to_dict() for r in result.rule_results],
        )
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnauthorizedError as e:
        _debug_log_process_event(
            "trigger_unauthorized",
            {"trigger_event": request.trigger_event, "actor_role": role_norm, "detail": str(e)},
        )
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/rollback", response_model=TransitionResultResponse)
async def rollback_process_instance(
    instance_id: str,
    body: RollbackRequest = Body(default_factory=RollbackRequest),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """بازگرداندن فرایند به وضعیت قبلی — فقط مدیر سامانه / معاون آموزش (override SOP)."""
    from app.core.audit import AuditLogger
    from app.core.user_roles import normalize_user_roles
    from app.meta.process_override_policy import OVERRIDE_ROLES, user_can_override_process

    actor_role = _normalize_actor_role(current_user.role)
    if not user_can_override_process(current_user):
        await AuditLogger(db).log(
            action_type="override_denied",
            actor_id=current_user.id,
            actor_role=actor_role,
            instance_id=uuid.UUID(instance_id),
            details={"action": "rollback", "reason_attempt": (body.reason or "")[:500]},
        )
        await db.flush()
        raise HTTPException(status_code=403, detail="شما مجوز بازگشت به مرحلهٔ قبل را ندارید.")

    if actor_role not in OVERRIDE_ROLES:
        for r in normalize_user_roles(current_user):
            nr = _normalize_actor_role(r)
            if nr in OVERRIDE_ROLES:
                actor_role = nr
                break
        else:
            actor_role = "admin"

    engine = StateMachineEngine(db)
    try:
        result = await engine.rollback_to_previous_state(
            instance_id=uuid.UUID(instance_id),
            actor_id=current_user.id,
            actor_role=actor_role,
            reason=body.reason,
        )
        return TransitionResultResponse(
            success=result.success,
            from_state=result.from_state,
            to_state=result.to_state,
            trigger_event=result.trigger_event,
            error=result.error,
            actions=result.actions or [],
            rule_results=[r.to_dict() for r in (result.rule_results or [])],
        )
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        await AuditLogger(db).log(
            action_type="override_denied",
            actor_id=current_user.id,
            actor_role=actor_role,
            instance_id=uuid.UUID(instance_id),
            details={"action": "rollback", "detail": str(e)},
        )
        await db.flush()
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/restart", response_model=RestartProcessResponse)
async def restart_process_instance(
    instance_id: str,
    body: RestartProcessRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """بایگانی پروندهٔ فعلی و شروع دوباره از مرحلهٔ اول (مدیر/معاون یا دانشجو برای پروندهٔ خود)."""
    from app.core.audit import AuditLogger
    from app.core.user_roles import normalize_user_roles
    from app.meta.process_override_policy import OVERRIDE_ROLES, user_can_override_process

    if not body.confirm:
        raise HTTPException(status_code=400, detail="برای شروع دوباره باید تأیید صریح بدهید.")

    inst = await _get_instance_or_404(db, instance_id)
    actor_role = _normalize_actor_role(current_user.role)

    is_own_instance = False
    if actor_role == "student":
        await _ensure_student_owns_instance(db, current_user, inst)
        is_own_instance = True
    elif not user_can_override_process(current_user):
        await AuditLogger(db).log(
            action_type="override_denied",
            actor_id=current_user.id,
            actor_role=actor_role,
            instance_id=inst.id,
            process_code=inst.process_code,
            details={"action": "restart", "reason_attempt": (body.reason or "")[:500]},
        )
        await db.flush()
        raise HTTPException(status_code=403, detail="شما مجوز شروع دوباره این فرایند را ندارید.")
    else:
        # نقش مؤثر برای موتور: یکی از OVERRIDE_ROLES (مثلاً اگر primary متفاوت باشد)
        if actor_role not in OVERRIDE_ROLES:
            for r in normalize_user_roles(current_user):
                nr = _normalize_actor_role(r)
                if nr in OVERRIDE_ROLES:
                    actor_role = nr
                    break
            else:
                actor_role = "admin"

    engine = StateMachineEngine(db)
    try:
        result = await engine.restart_process_instance(
            instance_id=uuid.UUID(instance_id),
            actor_id=current_user.id,
            actor_role=actor_role,
            reason=body.reason,
            is_own_instance=is_own_instance,
        )
        await db.flush()
        return RestartProcessResponse(
            success=result.success,
            old_instance_id=str(result.old_instance_id),
            new_instance_id=str(result.new_instance_id),
            process_code=result.process_code,
            current_state=result.current_state,
            error=result.error,
        )
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except UnauthorizedError as e:
        await AuditLogger(db).log(
            action_type="override_denied",
            actor_id=current_user.id,
            actor_role=actor_role,
            instance_id=inst.id,
            process_code=inst.process_code,
            details={"action": "restart", "detail": str(e)},
        )
        await db.flush()
        raise HTTPException(status_code=403, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProcessNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/status")
async def get_instance_status(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full status of a process instance including history."""
    inst = await _get_instance_or_404(db, instance_id)
    await _ensure_student_owns_instance(db, current_user, inst)
    engine = StateMachineEngine(db)
    try:
        status = await engine.get_instance_status(uuid.UUID(instance_id))
        return _redact_confidential_for_student(status, current_user)
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


async def _get_instance_or_404(db: AsyncSession, instance_id: str) -> ProcessInstance:
    try:
        iid = uuid.UUID(instance_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instance id")
    stmt = select(ProcessInstance).where(ProcessInstance.id == iid)
    result = await db.execute(stmt)
    inst = result.scalars().first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    return inst


@router.post("/{instance_id}/student-step-forms/register")
async def register_student_step_forms(
    instance_id: str,
    request: StudentStepFormsRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """دانشجو پس از پر کردن فرم مرحله؛ مقادیر در context_data ذخیره و فرم برای ویرایش قفل می‌شود تا مسئول باز کند."""
    if _normalize_actor_role(current_user.role) != "student":
        raise HTTPException(status_code=403, detail="Only students can register step forms")
    instance = await _get_instance_or_404(db, instance_id)
    stmt = select(Student).where(Student.id == instance.student_id)
    res = await db.execute(stmt)
    student = res.scalars().first()
    if not student or student.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your process instance")

    if instance.process_code == "start_therapy":
        from app.services.admission_type_service import (
            SINGLE_COURSE_NO_START_THERAPY_FA,
            therapy_start_applicable,
        )

        svc_st = StudentService(db)
        await svc_st.hydrate_admission_type(student)
        extra_st = StateMachineEngine._as_mapping(student.extra_data)
        if not therapy_start_applicable(extra_st.get("admission_type")):
            raise HTTPException(status_code=400, detail=SINGLE_COURSE_NO_START_THERAPY_FA)

    forms = get_process_forms(instance.process_code, state_code=instance.current_state_code)
    ctx_before = instance.context_data or {}
    forms = await forms_with_installment_policy(db, forms, ctx_before)
    blocked = await new_installment_disabled_reason(db, request.form_values or {}, ctx_before)
    if blocked:
        raise HTTPException(status_code=400, detail=blocked)
    ok, missing = validate_student_step_forms(forms, request.form_values or {}, ctx_before)
    if not ok:
        raise HTTPException(status_code=400, detail={"error": "validation_failed", "missing": missing})

    sanitized = sanitize_form_values(forms, request.form_values or {}, ctx_before)
    if instance.process_code == "educational_leave" and "leave_terms" in sanitized:
        try:
            sanitized["leave_terms"] = int(sanitized["leave_terms"])
        except (TypeError, ValueError):
            pass
    sanitized = await _ensure_step_otp_verified_for_register(
        db,
        current_user=current_user,
        instance=instance,
        sanitized=sanitized,
    )
    from app.meta.course_selection_validation import (
        course_selection_config,
        normalize_course_codes,
        validate_selected_courses_for_process,
    )

    course_cfg = course_selection_config(instance.process_code)
    if course_cfg:
        field_name = course_cfg.get("field_name") or "selected_courses"
        selected_raw = sanitized.get(field_name)
        if selected_raw in (None, "", []):
            selected_raw = sanitized.get("selected_courses")
        if selected_raw not in (None, "", []):
            ok_cs, err_cs = await validate_selected_courses_for_process(
                db,
                instance.process_code,
                {**(instance.context_data or {}), **sanitized},
                normalize_course_codes(selected_raw),
                student=student,
                instance=instance,
            )
            if not ok_cs:
                raise HTTPException(status_code=400, detail=err_cs or "انتخاب درس مجاز نیست.")
    ctx = apply_register_to_context(
        clear_step_otp_verified_flags(instance.context_data or {}),
        instance.current_state_code,
        sanitized,
    )
    if sanitized.get("final_report_pdf"):
        ctx["final_report_uploaded_at"] = datetime.now(timezone.utc).isoformat()
    payment_fields_touched = (
        sanitized.get("payment_method") is not None
        or sanitized.get("installment_count") is not None
    )
    if payment_fields_touched:
        from app.services.tuition_installment_service import refresh_instance_tuition_context

        # تعداد/روش عوض شده → برنامه اقساط قبلی نامعتبر است
        if (
            sanitized.get("installment_count") is not None
            and str(sanitized.get("installment_count")) != str(ctx_before.get("installment_count"))
        ) or (
            sanitized.get("payment_method") is not None
            and sanitized.get("payment_method") != ctx_before.get("payment_method")
        ):
            ctx.pop("installment_plan", None)
            ctx.pop("current_installment_index", None)
            ctx.pop("pending_installments_remaining", None)
            ctx.pop("next_installment_due_at", None)
            if sanitized.get("payment_method") == "cash":
                from app.services.tuition_installment_service import cancel_unsent_installment_reminders

                cancel_unsent_installment_reminders(
                    student, instance_id=str(instance.id), reason="switched_to_cash"
                )

        ctx = await refresh_instance_tuition_context(
            db,
            instance.process_code,
            instance.current_state_code,
            ctx,
        )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()

    auto_advanced = False
    if instance.process_code == "introductory_course_registration":
        auto_trigger = None
        if instance.current_state_code == "documents_upload":
            auto_trigger = "documents_submitted"
        elif instance.current_state_code == "documents_incomplete":
            # پس از رد جزئی، ثبت مجدد مدارک باید خودکار به صف بررسی برگردد
            # تا دکمه‌های تأیید/رد برای مدارک جدید دوباره در پنل پذیرش ظاهر شوند.
            auto_trigger = "documents_resubmitted"
        if auto_trigger:
            engine = StateMachineEngine(db)
            try:
                adv = await engine.execute_transition(
                    uuid.UUID(instance_id),
                    auto_trigger,
                    current_user.id,
                    _normalize_actor_role(current_user.role),
                    {"__auto_from_student_step_forms": True},
                )
                auto_advanced = bool(adv.success)
                if not adv.success and adv.error:
                    logger.info(
                        "register_student_step_forms: auto %s skipped (%s)",
                        auto_trigger,
                        adv.error,
                    )
            except (InvalidTransitionError, UnauthorizedError, InstanceNotFoundError) as e:
                logger.info(
                    "register_student_step_forms: auto %s not run: %s",
                    auto_trigger,
                    e,
                )
            except Exception:
                logger.exception(
                    "register_student_step_forms: auto %s failed",
                    auto_trigger,
                )

    await db.refresh(instance)
    return {
        "success": True,
        "context_data": instance.context_data,
        "auto_advanced_to_documents_review": auto_advanced,
    }


class StepOtpVerifyBody(BaseModel):
    code: str


@router.post("/{instance_id}/student-step-forms/step-otp/request")
async def request_student_step_otp(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ارسال کد تأیید پیامکی برای فیلدهای sms_verification در فرم مرحله (مثلاً تعهدنامه)."""
    if _normalize_actor_role(current_user.role) != "student":
        raise HTTPException(status_code=403, detail="Only students can request step OTP")
    instance = await _get_instance_or_404(db, instance_id)
    stmt = select(Student).where(Student.id == instance.student_id)
    student = (await db.execute(stmt)).scalars().first()
    if not student or student.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your process instance")
    phone = (current_user.phone or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="شماره موبایل در پروفایل شما ثبت نشده است.")
    if context_has_step_otp_verified(instance.context_data, instance.current_state_code):
        return {"success": True, "already_verified": True, "expires_in": 0}
    from app.services.otp_service import STEP_OTP_EXPIRY_SECONDS, request_otp as do_request

    result = await do_request(db, phone, expiry_seconds=STEP_OTP_EXPIRY_SECONDS)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "ارسال کد ناموفق بود")
    return result


@router.post("/{instance_id}/student-step-forms/step-otp/verify")
async def verify_student_step_otp(
    instance_id: str,
    body: StepOtpVerifyBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """تأیید کد پیامکی مرحله بدون ورود مجدد به سامانه."""
    if _normalize_actor_role(current_user.role) != "student":
        raise HTTPException(status_code=403, detail="Only students can verify step OTP")
    instance = await _get_instance_or_404(db, instance_id)
    stmt = select(Student).where(Student.id == instance.student_id)
    student = (await db.execute(stmt)).scalars().first()
    if not student or student.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your process instance")
    phone = (current_user.phone or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="شماره موبایل در پروفایل شما ثبت نشده است.")
    from app.services.otp_service import verify_otp_code_only

    result = await verify_otp_code_only(db, phone, body.code)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "کد نامعتبر است")
    instance.context_data = stamp_step_otp_verified(
        instance.context_data,
        instance.current_state_code,
    )
    flag_modified(instance, "context_data")
    await db.commit()
    return {"success": True, "verification_token": body.code.strip()}


@router.post("/{instance_id}/student-step-forms/upload-file")
async def upload_student_step_file(
    instance_id: str,
    field_name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """دانشجو: فایل مدرک را روی دیسک ذخیره می‌کند و همان لحظه در context_data نمونه نیز ثبت می‌شود."""
    if _normalize_actor_role(current_user.role) != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can upload")
    if not _FIELD_NAME_RE.match(field_name or ""):
        raise HTTPException(status_code=400, detail="Invalid field name")
    instance = await _get_instance_or_404(db, instance_id)
    stmt = select(Student).where(Student.id == instance.student_id)
    res = await db.execute(stmt)
    student = res.scalars().first()
    if not student or student.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your process instance")

    allowed = _file_upload_field_names_for_process(
        instance.process_code,
        state_code=instance.current_state_code,
    )
    if field_name not in allowed:
        raise HTTPException(status_code=400, detail="Field not allowed for this process")

    ct = file.content_type or ""
    if ct not in _ALLOWED_STEP_DOC_TYPES:
        raise HTTPException(status_code=400, detail="فرمت مجاز: تصویر یا PDF")

    body = await file.read()
    if len(body) > _MAX_STEP_DOC_BYTES:
        raise HTTPException(status_code=400, detail="حداکثر حجم ۲۵ مگابایت")

    settings = get_settings()
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    safe_dir = upload_root / "process_instances" / str(instance.id)
    safe_dir.mkdir(parents=True, exist_ok=True)
    ext = ".pdf" if ct == "application/pdf" else (
        ".jpg" if ct == "image/jpeg" else ".png" if ct == "image/png" else ".webp" if ct == "image/webp" else ".gif"
    )
    fname = f"{field_name}_{uuid.uuid4().hex}{ext}"
    path = safe_dir / fname
    path.write_bytes(body)

    rel = f"/uploads/process_instances/{instance.id}/{fname}"
    file_meta = {
        "file_name": file.filename or fname,
        "size": len(body),
        "mime": ct,
        "url": rel,
    }
    ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
    ctx[field_name] = file_meta
    if field_name == "final_report_pdf":
        ctx["final_report_uploaded_at"] = datetime.now(timezone.utc).isoformat()
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()
    return file_meta


@router.post("/{instance_id}/student-step-forms/unlock-edit")
async def unlock_student_step_forms_edit(
    instance_id: str,
    request: StudentStepFormsUnlockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """ادمین/اداری: اجازهٔ ویرایش مجدد فرم مرحلهٔ فعلی (یا state مشخص) برای دانشجو."""
    instance = await _get_instance_or_404(db, instance_id)
    state = request.state_code or instance.current_state_code
    if not state:
        raise HTTPException(status_code=400, detail="No state code")
    ctx = apply_unlock_to_context(instance.context_data or {}, state)
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    return {"success": True, "state_code": state, "context_data": instance.context_data}


@router.post("/{instance_id}/operator-step-forms/update-selected-courses")
async def operator_update_selected_courses(
    instance_id: str,
    request: OperatorUpdateSelectedCoursesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """ادمین/مسئول پذیرش: تغییر مستقیم دروس انتخاب‌شده (قبل از ثبت‌نام نهایی)."""
    instance = await _get_instance_or_404(db, instance_id)
    if instance.is_completed or instance.is_cancelled:
        raise HTTPException(status_code=400, detail="فرایند تکمیل یا لغو شده؛ تغییر دروس مجاز نیست.")

    cfg = course_selection_config(instance.process_code)
    if not cfg:
        raise HTTPException(
            status_code=400,
            detail="این فرایند از ویرایش دروس توسط اپراتور پشتیبانی نمی‌شود.",
        )

    current_state = instance.current_state_code or ""
    if current_state not in cfg["editable_states"]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"در وضعیت «{current_state}» امکان تغییر دروس وجود ندارد؛ "
                f"فقط در مراحل {', '.join(sorted(cfg['editable_states']))} مجاز است."
            ),
        )

    ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
    field_name = cfg["field_name"]
    form_state = cfg["form_state"]
    new_codes = normalize_course_codes(request.selected_courses)
    st_row = (
        await db.execute(select(Student).where(Student.id == instance.student_id))
    ).scalars().first()
    ok, err = await validate_selected_courses_for_process(
        db, instance.process_code, ctx, new_codes, student=st_row, instance=instance
    )
    if not ok:
        raise HTTPException(status_code=400, detail=err or "انتخاب دروس نامعتبر است.")

    old_codes = normalize_course_codes(ctx.get(field_name))
    ctx[field_name] = new_codes

    audit_key = "__operator_course_selection_edits"
    edits = list(ctx.get(audit_key) or [])
    edits.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "by_user_id": str(current_user.id),
            "by_role": _normalize_actor_role(current_user.role),
            "old": old_codes,
            "new": new_codes,
            "reason": (request.reason or "").strip() or None,
            "process_state": current_state,
        }
    )
    ctx[audit_key] = edits[-30:]

    ctx = apply_register_to_context(ctx, form_state, {field_name: new_codes})
    from app.services.tuition_installment_service import refresh_instance_tuition_context

    ctx = await refresh_instance_tuition_context(
        db,
        instance.process_code,
        current_state,
        ctx,
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()

    return {
        "success": True,
        "field_name": field_name,
        "selected_courses": new_codes,
        "previous_courses": old_codes,
        "context_data": instance.context_data,
    }


@router.get("/{instance_id}/marketing-campaign-pack.pdf")
async def download_marketing_campaign_pack_pdf(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """خروجی PDF فعالیت‌های مرتبط با کمپین بازاریابی برای انتقال به مدیر مارکتینگ."""
    from app.core.user_roles import normalize_user_roles

    roles = set(normalize_user_roles(current_user))
    if roles <= {"student", "applicant"}:
        raise HTTPException(status_code=403, detail="Only operators can download marketing pack")

    instance = await _get_instance_or_404(db, instance_id)
    from app.services.semester_prep_service import PREP_PROCESS_CODES

    if instance.process_code not in PREP_PROCESS_CODES:
        raise HTTPException(status_code=400, detail="این خروجی فقط برای فرایند آماده‌سازی ترم است")
    if (instance.current_state_code or "") != "marketing_campaign":
        raise HTTPException(status_code=400, detail="خروجی PDF فقط در مرحلهٔ کمپین بازاریابی در دسترس است")
    if not _user_can_act_on_state(current_user, instance.process_code, "marketing_campaign"):
        raise HTTPException(
            status_code=403,
            detail="دانلود PDF این مرحله فقط برای مسئول پذیرش مجاز است.",
        )

    from app.services.semester_prep_marketing_pdf import build_marketing_campaign_pdf_bytes, enrich_marketing_handoff_context

    ctx = StateMachineEngine._as_mapping(instance.context_data)
    ctx = await enrich_marketing_handoff_context(db, instance.process_code, ctx)
    name = (current_user.full_name_fa or current_user.username or "").strip()
    try:
        pdf_bytes = build_marketing_campaign_pdf_bytes(
            instance.process_code,
            ctx,
            recipient_display_name=name,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        import logging

        logging.getLogger(__name__).exception("marketing_campaign_pdf_generation_failed")
        raise HTTPException(
            status_code=500,
            detail="تولید فایل PDF ممکن نشد. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
        ) from e

    safe_slug = "winter" if instance.process_code == "winter_semester_preparation" else "fall"
    filename = f"marketing_campaign_{safe_slug}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{instance_id}/operator-step-forms/register")
async def register_operator_step_forms(
    instance_id: str,
    request: OperatorStepFormsRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """اپراتور (نقش غیر دانشجو) فرم‌های مرحلهٔ فعلی فرایند را پر و در context_data ثبت می‌کند.

    برای فرایندهای آماده‌سازی ترم (۲۹/۳۰): تقویم، شهریه، پروانه، لیست دروس،
    تعیین مصاحبه‌کنندگان و زمان‌بندی. قبل از اجرای ترنزیشن این مرحله فراخوانی می‌شود.
    """
    from app.core.user_roles import normalize_user_roles, primary_role

    roles = set(normalize_user_roles(current_user))
    if roles <= {"student", "applicant"}:
        raise HTTPException(status_code=403, detail="Only operators can register operator step forms")

    instance = await _get_instance_or_404(db, instance_id)
    if instance.is_completed or instance.is_cancelled:
        raise HTTPException(status_code=400, detail="فرایند تکمیل یا لغو شده؛ ثبت فرم مجاز نیست.")

    state = (request.state_code or instance.current_state_code or "").strip()
    if not state:
        raise HTTPException(status_code=400, detail="No state code")
    if state != (instance.current_state_code or ""):
        raise HTTPException(status_code=400, detail="فقط فرم مرحلهٔ فعلی قابل ثبت است.")

    if not _user_can_act_on_state(current_user, instance.process_code, state):
        raise HTTPException(
            status_code=403,
            detail="شما مسئول اقدام در این مرحله نیستید؛ فقط مشاهده مجاز است.",
        )
    roles_list = normalize_user_roles(current_user)
    actor_role = _normalize_actor_role(primary_role(current_user))
    for r in roles_list:
        if _portal_role_can_act_on_state(r, instance.process_code, state):
            actor_role = _normalize_actor_role(r)
            break

    raw_forms = get_process_forms(instance.process_code, state_code=state)
    raw_forms = await forms_with_installment_policy(db, raw_forms, instance.context_data)
    forms = visible_forms_for_role(raw_forms, actor_role)
    edit_names = editable_field_names(forms, actor_role) if forms else set()
    if not forms or not edit_names:
        fallback = first_role_that_can_edit_forms(roles_list, raw_forms)
        if fallback:
            actor_role = _normalize_actor_role(fallback)
            forms = visible_forms_for_role(raw_forms, actor_role)
            edit_names = editable_field_names(forms, actor_role)
    if not forms:
        raise HTTPException(
            status_code=403,
            detail="شما اجازهٔ ثبت فرم این مرحله را ندارید.",
        )

    if not edit_names:
        raise HTTPException(
            status_code=403,
            detail="شما اجازهٔ ویرایش فرم این مرحله را ندارید.",
        )

    from app.services.process_form_prefill import apply_pre_filled_fields
    from app.services.semester_prep_service import PREP_PROCESS_CODES

    merged_ctx = await apply_pre_filled_fields(
        db,
        instance.process_code,
        state,
        StateMachineEngine._as_mapping(instance.context_data),
        student_id=instance.student_id,
    )
    form_values = dict(request.form_values or {})
    for k, v in merged_ctx.items():
        if form_values.get(k) in (None, "", []) and v not in (None, "", []):
            form_values[k] = v

    form_values = sanitize_editable_payload(forms, actor_role, form_values)
    if not form_values:
        raise HTTPException(
            status_code=403,
            detail="شما اجازهٔ ثبت فرم این مرحله را ندارید.",
        )
    blocked = await new_installment_disabled_reason(
        db, form_values, instance.context_data
    )
    if blocked:
        raise HTTPException(status_code=400, detail=blocked)

    if (
        state == "course_finalization"
        and instance.process_code in PREP_PROCESS_CODES
    ):
        from app.services.semester_prep_service import (
            _apply_course_finalization_prefill,
            apply_course_finalization_form_save,
        )

        submitted_finalized = {
            k: list(form_values[k])
            for k in (
                "courses_finalized_fall",
                "courses_finalized_winter",
                "courses_finalized",
            )
            if isinstance(form_values.get(k), list)
        }
        base_ctx = StateMachineEngine._as_mapping(instance.context_data)
        combined = {**base_ctx, **form_values}
        synced_ctx = _apply_course_finalization_prefill(
            instance.process_code, state, combined
        )
        for key in (
            "courses_finalized_fall",
            "courses_finalized_winter",
            "courses_finalized",
        ):
            if key in synced_ctx:
                form_values[key] = synced_ctx[key]
        # روز/ساعت ویرایش‌شده در فرم را نگه دار و به پیش‌نویس مرحلهٔ ۴ بنویس
        form_values = apply_course_finalization_form_save(
            instance.process_code,
            {**base_ctx, **synced_ctx},
            {**form_values, **submitted_finalized},
        )

    ok, missing = validate_operator_step_forms(forms, form_values, instance.context_data or {})
    if not ok:
        raise HTTPException(status_code=400, detail={"error": "validation_failed", "missing": missing})

    course_cfg = course_selection_config(instance.process_code)
    if course_cfg:
        field_name = course_cfg.get("field_name") or "selected_courses"
        selected_raw = form_values.get(field_name)
        if selected_raw in (None, "", []):
            selected_raw = form_values.get("selected_courses")
        if selected_raw not in (None, "", []):
            st_row = (
                await db.execute(select(Student).where(Student.id == instance.student_id))
            ).scalars().first()
            ok_cs, err_cs = await validate_selected_courses_for_process(
                db,
                instance.process_code,
                {**(instance.context_data or {}), **form_values},
                normalize_course_codes(selected_raw),
                student=st_row,
                instance=instance,
            )
            if not ok_cs:
                raise HTTPException(status_code=400, detail=err_cs or "انتخاب درس مجاز نیست.")

    if (
        state == "calendar_entry"
        and instance.process_code in PREP_PROCESS_CODES
    ):
        _validate_semester_prep_calendar_form(form_values)

    if (
        state == "interviewer_assignment"
        and instance.process_code in PREP_PROCESS_CODES
    ):
        _validate_semester_prep_interviewer_assignment_form(form_values)

    if (
        state == "interview_scheduling"
        and instance.process_code in PREP_PROCESS_CODES
    ):
        _validate_semester_prep_interview_scheduling_form(form_values)

    if (
        state in ("course_list_creation", "course_list_review")
        and instance.process_code in PREP_PROCESS_CODES
    ):
        from app.services.course_committee_roster_service import (
            validate_semester_prep_course_table_rows,
        )

        table_keys = (
            ("courses_fall", "courses_winter")
            if state == "course_list_creation"
            else ("courses",)
        )
        all_errors: list[str] = []
        for key in table_keys:
            rows = form_values.get(key)
            if rows is None:
                continue
            errs = await validate_semester_prep_course_table_rows(db, rows)
            all_errors.extend(errs)
        if all_errors:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "roster_validation_failed",
                    "missing": all_errors,
                },
            )

    sanitized = sanitize_operator_form_values(forms, form_values)
    if (
        state == "course_finalization"
        and instance.process_code in PREP_PROCESS_CODES
    ):
        from app.services.semester_prep_service import merge_course_finalization_draft_writeback

        sanitized = merge_course_finalization_draft_writeback(sanitized, form_values)
    from app.services.course_committee_roster_service import enrich_course_table_rows

    sanitized = await enrich_course_table_rows(db, forms, sanitized)
    if instance.process_code == "class_session_cancellation" and state == "cancellation_request":
        from app.services.class_session_cancellation_service import (
            build_class_session_cancellation_context,
        )

        role = (current_user.role or "").strip()
        all_term = role in (
            "scientific_officer_course_committee",
            "course_committee_executive",
            "admin",
            "staff",
            "deputy_education",
        )
        student_row = await db.get(Student, instance.student_id)
        extra = await build_class_session_cancellation_context(
            db,
            current_user,
            {**StateMachineEngine._as_mapping(instance.context_data), **sanitized},
            form_values=sanitized,
            all_term=all_term,
            student=student_row,
        )
        for key in (
            "makeup_date",
            "makeup_time",
            "makeup_summary_fa",
            "cancellation_ordinal",
            "cancellation_ordinal_fa",
            "usual_class_time",
            "term_week_makeup_label",
            "assignable_courses",
            "cancellable_sessions",
            "upcoming_cancellable_sessions",
        ):
            if extra.get(key) not in (None, ""):
                sanitized[key] = extra[key]
    from app.services.course_committee_roster_service import sync_semester_course_assignments

    for form in forms:
        if not isinstance(form, dict):
            continue
        for field in form.get("fields") or []:
            if not isinstance(field, dict) or (field.get("type") or "") != "table":
                continue
            fname = field.get("name")
            if fname and isinstance(sanitized.get(fname), list):
                await sync_semester_course_assignments(
                    db,
                    courses_rows=sanitized[fname],
                    process_code=instance.process_code,
                )
    ctx = apply_register_to_context(instance.context_data or {}, state, sanitized)
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    if (
        state == "interview_scheduling"
        and instance.process_code in PREP_PROCESS_CODES
    ):
        from app.services.interview_slot_service import (
            apply_semester_prep_interview_defaults_to_open_slots,
            interview_mode_fa_to_slot_mode,
            resolve_semester_prep_interview_location,
        )

        slot_mode = interview_mode_fa_to_slot_mode(sanitized.get("interview_mode"))
        slot_loc = (
            resolve_semester_prep_interview_location(sanitized)
            if slot_mode == "in_person"
            else None
        )
        await apply_semester_prep_interview_defaults_to_open_slots(
            db,
            mode=slot_mode,
            location_fa=slot_loc,
        )
    await db.flush()
    await db.refresh(instance)
    return {"success": True, "state_code": state, "context_data": instance.context_data}


@router.get("/{instance_id}/data")
async def get_process_instance_data(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """دادهٔ ثبت‌شدهٔ یک نمونه فرایند برای مشاهده/ویرایش بر اساس نقش.

    لایهٔ عمومی متادیتا-محور: همهٔ فرم‌های فرایند را می‌گیرد، فیلدهای مرئی برای
    نقش جاری را برمی‌گرداند و مشخص می‌کند کدام فیلدها (بر اساس ``editable_by``)
    قابل ویرایش‌اند.
    """
    instance = await _get_instance_or_404(db, instance_id)
    await _ensure_student_owns_instance(db, current_user, instance)

    role = _normalize_actor_role(current_user.role)
    forms = get_process_forms(instance.process_code) or []
    forms = await forms_with_installment_policy(db, forms, instance.context_data)
    vis_forms = visible_forms_for_role(forms, role)
    vis_names = visible_field_names(forms, role)
    edit_names = editable_field_names(forms, role)
    values = extract_values(instance.context_data, vis_names)
    return {
        "instance_id": str(instance.id),
        "process_code": instance.process_code,
        "current_state": instance.current_state_code,
        "is_completed": instance.is_completed,
        "is_cancelled": instance.is_cancelled,
        "forms": vis_forms,
        "values": values,
        "editable_field_names": sorted(edit_names),
        "can_edit": bool(edit_names),
    }


@router.post("/{instance_id}/data/update")
async def update_process_instance_data(
    instance_id: str,
    request: ProcessDataUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ویرایش/به‌روزرسانی دادهٔ ثبت‌شده؛ فقط فیلدهایی که نقش جاری در
    ``editable_by`` آن‌هاست اعمال می‌شوند (بقیه نادیده گرفته می‌شوند)."""
    instance = await _get_instance_or_404(db, instance_id)
    await _ensure_student_owns_instance(db, current_user, instance)

    role = _normalize_actor_role(current_user.role)
    forms = get_process_forms(instance.process_code) or []
    forms = await forms_with_installment_policy(db, forms, instance.context_data)
    sanitized = sanitize_editable_payload(forms, role, request.field_values or {})
    if not sanitized:
        raise HTTPException(
            status_code=403,
            detail="هیچ فیلدی برای ویرایش با مجوز نقش شما در این درخواست وجود ندارد.",
        )
    blocked = await new_installment_disabled_reason(db, sanitized, instance.context_data)
    if blocked:
        raise HTTPException(status_code=400, detail=blocked)

    _validate_semester_prep_calendar_payload_if_present(instance.process_code, sanitized)

    ctx = apply_data_update_to_context(
        instance.context_data,
        sanitized,
        actor_id=current_user.id,
        actor_role=role,
        reason=request.reason,
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()
    await db.refresh(instance)

    from app.services.semester_prep_service import sync_active_institute_calendar_after_prep_correction

    await sync_active_institute_calendar_after_prep_correction(
        db,
        instance,
        updated_field_names=set(sanitized.keys()),
        published_by=current_user.id,
    )

    return {
        "success": True,
        "updated_fields": sorted(sanitized.keys()),
        "context_data": instance.context_data,
    }


@router.post("/{instance_id}/edit-requests", status_code=201)
async def create_student_edit_request(
    instance_id: str,
    request: StudentEditRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ثبت درخواست ویرایش فرم مرحله برای دانشجو/متقاضی (بدون unlock مستقیم)."""
    if _normalize_actor_role(current_user.role) != "student":
        raise HTTPException(status_code=403, detail="Only students can create edit requests")

    instance = await _get_instance_or_404(db, instance_id)
    await _ensure_student_owns_instance(db, current_user, instance)

    state_code = (request.state_code or "").strip()
    if not state_code:
        raise HTTPException(status_code=400, detail="state_code is required")

    ctx = StateMachineEngine._as_mapping(instance.context_data)
    submitted = StateMachineEngine._as_mapping(ctx.get("__student_forms_submitted_states"))
    if not submitted.get(state_code):
        raise HTTPException(
            status_code=400,
            detail="این مرحله هنوز ثبت نشده است و درخواست ویرایش برای آن مجاز نیست.",
        )

    rule = find_edit_request_rule(
        process_code=instance.process_code,
        state_code=state_code,
        form_code=(request.form_code or None),
    )
    if not rule:
        raise HTTPException(status_code=400, detail="برای این مرحله، درخواست ویرایش فعال نشده است.")

    allowed_fields = [str(x) for x in (rule.get("field_names") or []) if x]
    selected_fields = normalize_requested_fields(request.field_names or [], allowed_fields)
    if not selected_fields:
        raise HTTPException(
            status_code=400,
            detail="حداقل یک فیلد معتبر برای درخواست ویرایش انتخاب کنید.",
        )

    triage = await resolve_triage_assignee(db)
    assignee, route_trace = await resolve_edit_request_assignee(
        db,
        instance=instance,
        state_code=state_code,
        rule=rule,
        triage_user=triage,
    )

    student = (await db.execute(select(Student).where(Student.id == instance.student_id))).scalars().first()
    now = datetime.now(timezone.utc)
    title = f"درخواست ویرایش مرحله {state_code}"
    ticket = SupportTicket(
        id=uuid.uuid4(),
        title=title,
        description=request.reason.strip(),
        category="process_edit_request",
        status="open",
        priority=str(rule.get("priority") or "normal"),
        requester_id=current_user.id,
        assignee_id=assignee.id,
        student_id=instance.student_id if student else None,
        process_instance_id=instance.id,
        extra_context={
            "process_code": instance.process_code,
            "state_code": state_code,
            "form_code": request.form_code or rule.get("form_code"),
            "field_names": selected_fields,
            "requested_by_user_id": str(current_user.id),
            "proposed_values": request.proposed_values or {},
            "context_snapshot": {k: ctx.get(k) for k in selected_fields},
            "edit_request_route": route_trace,
        },
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    await db.flush()

    db.add(
        TicketComment(
            id=uuid.uuid4(),
            ticket_id=ticket.id,
            author_id=None,
            kind="system",
            body=(
                "درخواست ویرایش ثبت شد. "
                f"مسیر ارجاع: {route_trace.get('route')} -> {assignee.username} ({assignee.role})."
            ),
        )
    )
    await db.flush()
    return {"success": True, "ticket_id": str(ticket.id), "assignee_role": assignee.role}


@router.get("/{instance_id}/dashboard")
async def get_instance_dashboard(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get instance status + available transitions in one call for dashboard UI (BUILD_TODO § ز)."""
    iid = uuid.UUID(instance_id)
    inst = (await db.execute(select(ProcessInstance).where(ProcessInstance.id == iid))).scalars().first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    await _ensure_student_owns_instance(db, current_user, inst)
    engine = StateMachineEngine(db)
    try:
        status = await engine.get_instance_status(iid)
        transitions = await engine.get_available_transitions(
            instance_id=iid,
            actor_role=_normalize_actor_role(current_user.role),
            actor_id=current_user.id,
        )
        forms = get_process_forms(
            status.get("process_code", ""),
            state_code=status.get("current_state"),
        )
        forms = await forms_with_installment_policy(db, forms, inst.context_data)
        ui_requirements = get_process_ui_requirements(status.get("process_code", ""))
        out = {
            "status": _redact_confidential_for_student(status, current_user),
            "transitions": transitions,
            "forms": forms,
            "ui_requirements": ui_requirements,
        }
        if status.get("process_code") == "introductory_course_registration":
            from app.services.registration_readiness_service import check_intro_registration_gate

            out["registration_gate"] = (await check_intro_registration_gate(db)).to_dict()
        if status.get("process_code") == "ta_track_completion" and inst.student_id:
            from app.services.ta_track_portfolio_service import build_ta_portfolio

            student = (
                await db.execute(select(Student).where(Student.id == inst.student_id))
            ).scalars().first()
            if student:
                user = (
                    await db.execute(select(User).where(User.id == student.user_id))
                ).scalars().first() if student.user_id else None
                out["ta_portfolio"] = build_ta_portfolio(student, user)
        return out
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{instance_id}/transitions")
async def get_available_transitions(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available transitions from the current state for the current user."""
    iid = uuid.UUID(instance_id)
    inst = (await db.execute(select(ProcessInstance).where(ProcessInstance.id == iid))).scalars().first()
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    await _ensure_student_owns_instance(db, current_user, inst)
    engine = StateMachineEngine(db)
    try:
        transitions = await engine.get_available_transitions(
            instance_id=iid,
            actor_role=_normalize_actor_role(current_user.role),
            actor_id=current_user.id,
        )
        return {"transitions": transitions}
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/instances/student/{student_id}")
async def get_student_instances(
    student_id: str,
    is_completed: Optional[bool] = Query(None),
    include_institute_prep: bool = Query(
        False,
        description=(
            "اگر true باشد فقط نمونه‌های آماده‌سازی ترم برگردانده می‌شوند "
            "(برای تب پرونده عملیاتی در ردیابی). در غیر این صورت آن‌ها حذف می‌شوند."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all process instances for a student."""
    from app.core.resource_access import ensure_can_read_student, normalize_role

    await ensure_can_read_student(db, current_user, uuid.UUID(student_id))
    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == uuid.UUID(student_id)
    )
    if is_completed is not None:
        stmt = stmt.where(ProcessInstance.is_completed == is_completed)
    stmt = stmt.order_by(ProcessInstance.started_at.desc())

    result = await db.execute(stmt)
    instances = result.scalars().all()

    from app.services.semester_prep_service import PREP_PROCESS_CODES

    if include_institute_prep:
        if normalize_role(current_user.role) == "student":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="دسترسی به نمونه‌های آماده‌سازی ترم برای دانشجو مجاز نیست.",
            )
        instances = [i for i in instances if i.process_code in PREP_PROCESS_CODES]
    else:
        # آماده‌سازی ترم سطح مؤسسه است؛ با دانشجویان واقعی قاطی نشود.
        instances = [i for i in instances if i.process_code not in PREP_PROCESS_CODES]

    def _list_item(i: ProcessInstance) -> dict:
        item = {
            "instance_id": str(i.id),
            "process_code": i.process_code,
            "current_state": i.current_state_code,
            "is_completed": i.is_completed,
            "is_cancelled": i.is_cancelled,
            "started_at": i.started_at.isoformat() if i.started_at else None,
            "completed_at": i.completed_at.isoformat() if i.completed_at else None,
        }
        # تاریخ جلسه برای attendance_tracking تا UI بتواند ردیف‌های هم‌نام را از هم تشخیص دهد
        if i.process_code == "attendance_tracking":
            ctx = i.context_data if isinstance(i.context_data, dict) else {}
            session_date = ctx.get("session_date") or ctx.get("record_date")
            if session_date:
                item["session_date"] = str(session_date)[:10]
            sid = ctx.get("therapy_session_id") or ctx.get("session_id")
            if sid:
                item["therapy_session_id"] = str(sid)
        return item

    return {"instances": [_list_item(i) for i in instances]}


@router.get("/student/{student_id}/artifacts")
async def get_student_process_artifacts(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """کارنامه‌ها و گواهی‌های قابل نمایش در پورتال دانشجو."""
    from app.core.resource_access import ensure_can_read_student
    from app.services.student_artifacts_service import get_student_artifacts

    sid = uuid.UUID(student_id)
    await ensure_can_read_student(db, current_user, sid)
    payload = await get_student_artifacts(db, sid)
    if payload is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return payload


@router.get("/student/{student_id}/documents/{doc_id}.pdf")
async def download_student_document_pdf(
    student_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """دانلود PDF کارنامه/گواهی/سند رسمی دانشجو."""
    from urllib.parse import quote

    from app.core.resource_access import ensure_can_read_student, normalize_role
    from app.services.student_artifact_pdf_service import (
        artifact_pdf_filename,
        render_student_document_pdf,
    )
    from app.services.student_artifacts_service import (
        _COMMITTEE_READ_ROLES,
        get_student_document_for_pdf,
    )
    from app.services.workflow import _common as C

    sid = uuid.UUID(student_id)
    role = normalize_role(current_user.role)
    if role in _COMMITTEE_READ_ROLES:
        row = (
            await db.execute(select(Student).where(Student.id == sid))
        ).scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Student not found")
    else:
        await ensure_can_read_student(db, current_user, sid)

    student, doc = await get_student_document_for_pdf(db, sid, doc_id, current_user)
    if not student or not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    user = None
    if getattr(student, "user_id", None):
        user = await C.get_user(db, student.user_id)

    try:
        pdf_bytes = render_student_document_pdf(student, doc, user=user)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logging.getLogger(__name__).exception("student_document_pdf_generation_failed")
        raise HTTPException(
            status_code=500,
            detail="تولید فایل PDF ممکن نشد. لطفاً دوباره تلاش کنید.",
        ) from e

    filename = artifact_pdf_filename(doc, student)
    encoded = quote(filename)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )


@router.get("/student/{student_id}/documents/{doc_id}")
async def get_student_document_detail(
    student_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """محتوای یک کارنامه/گواهی قابل نمایش در پورتال دانشجو."""
    from app.core.resource_access import ensure_can_read_student
    from app.services.student_artifacts_service import get_student_document

    sid = uuid.UUID(student_id)
    await ensure_can_read_student(db, current_user, sid)
    doc = await get_student_document(db, sid, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
