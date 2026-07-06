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
from app.meta.process_data_access import (
    apply_data_update_to_context,
    editable_field_names,
    extract_values,
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
    filter_forms_for_student,
    sanitize_form_values,
    sanitize_operator_form_values,
    validate_operator_step_forms,
    validate_student_step_forms,
)
from app.services.student_service import StudentService
from app.services.edit_request_router import (
    find_edit_request_rule,
    normalize_requested_fields,
    resolve_edit_request_assignee,
)
from app.api.ticket_routes import resolve_triage_assignee

router = APIRouter(prefix="/api/process", tags=["Process"])


def _normalize_actor_role(role: Optional[str]) -> str:
    """نقش‌ها در متادیتا lowercase هستند؛ اگر DB رشتۀ متفاوت داشت، RBAC از بین نرود."""
    s = (role or "").strip().lower()
    return s or "student"


def _portal_role_can_act_on_state(actor_role: str, process_code: str, state_code: str) -> bool:
    from app.meta.operator_state_catalog import (
        normalize_assigned_role,
        portal_role_can_act_on_assigned_role,
    )

    if actor_role == "admin":
        return True
    assigned = get_state_assigned_role(process_code, state_code)
    if not assigned:
        return True
    return portal_role_can_act_on_assigned_role(actor_role, normalize_assigned_role(assigned))


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


def _enrich_lesson_start_context(
    initial_context: Optional[dict],
    student_row: Student,
) -> Optional[dict]:
    """دروس قابل انتخاب را از lms پروندهٔ دانشجو برای فرم ثبت‌نام در درس seed می‌کند."""
    out = dict(initial_context or {})
    extra = StateMachineEngine._as_mapping(student_row.extra_data)
    lms = StateMachineEngine._as_mapping(extra.get("lms"))
    available = list(lms.get("available_courses") or lms.get("enrolled_courses") or [])
    if not available:
        term = int(student_row.current_term or 1)
        ctype = student_row.course_type or "introductory"
        available = [f"{ctype}_term{term}_course{i}" for i in range(1, 4)]
    out.setdefault("lms", dict(lms))
    out["lms"].setdefault("available_courses", available)
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
    student_id: str
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
    actor_role = _normalize_actor_role(current_user.role)
    raw_forms = get_process_forms(process_code, state_code=state)
    forms = visible_forms_for_role(raw_forms, actor_role) if actor_role != "student" else raw_forms
    can_act_on_state = _portal_role_can_act_on_state(actor_role, process_code, state or "")
    forms = _lock_forms_when_cannot_act(forms, can_act=can_act_on_state)
    state_assigned_role = get_state_assigned_role(process_code, state or "") if state else None
    suggested_context: dict = {}
    if instance_id and state:
        try:
            iid = uuid.UUID(instance_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="instance_id نامعتبر")
        inst = await db.get(ProcessInstance, iid)
        if inst and inst.process_code == process_code:
            from app.services.process_form_prefill import apply_pre_filled_fields

            base_ctx = StateMachineEngine._as_mapping(inst.context_data)
            suggested_context = await apply_pre_filled_fields(
                db, process_code, state, base_ctx, student_id=inst.student_id,
            )
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
    """Start a new process instance for a student."""
    student_uuid = uuid.UUID(request.student_id)
    stmt = select(Student).where(Student.id == student_uuid)
    student_row = (await db.execute(stmt)).scalars().first()
    if not student_row:
        raise HTTPException(status_code=404, detail="Student not found")

    if _normalize_actor_role(current_user.role) == "student" and student_row.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط می‌توانید فرایند را برای پروفایل خودتان آغاز کنید.",
        )

    extra = StateMachineEngine._as_mapping(student_row.extra_data)
    if (
        request.process_code in _REGISTRATION_PROCESS_CODES_BLOCKED_UNDER_CLASS_ACCESS
        and extra.get("class_access_blocked")
    ):
        raise HTTPException(
            status_code=400,
            detail="به‌دلیل مرخصی آموزشی فعال، ثبت‌نام ترم/درس تا زمان بازگشت و رفع مسدودیت در سامانه مجاز نیست.",
        )

    if request.process_code == "introductory_course_registration":
        from app.services.registration_readiness_service import check_intro_registration_gate

        gate = await check_intro_registration_gate(db)
        if not gate.allowed:
            raise HTTPException(status_code=403, detail=gate.reason_fa)

    initial_ctx = request.initial_context
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
        initial_ctx = _enrich_lesson_start_context(initial_ctx, student_row)
    if request.process_code == "class_session_cancellation":
        initial_ctx = await _enrich_class_session_cancellation_start(
            db, initial_ctx, student_row, current_user
        )

    engine = StateMachineEngine(db)
    try:
        instance = await engine.start_process(
            process_code=request.process_code,
            student_id=student_uuid,
            actor_id=current_user.id,
            actor_role=_normalize_actor_role(current_user.role),
            initial_context=initial_ctx,
        )
        await db.flush()
        if request.process_code in ("educational_leave", "session_payment"):
            svc = StudentService(db)
            await svc.set_primary_instance_for_student(student_row, instance.id)
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
    current_user: User = Depends(require_role("admin", "deputy_education", "staff")),
):
    """بازگرداندن فرایند به وضعیت قبلی بر اساس آخرین رکورد تاریخچه (مدیر آموزش / کارمند / ادمین)."""
    engine = StateMachineEngine(db)
    try:
        result = await engine.rollback_to_previous_state(
            instance_id=uuid.UUID(instance_id),
            actor_id=current_user.id,
            actor_role=_normalize_actor_role(current_user.role),
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
    """بایگانی پروندهٔ فعلی و شروع دوباره از مرحلهٔ اول (پرسنل یا دانشجو برای پروندهٔ خود)."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="برای شروع دوباره باید تأیید صریح بدهید.")

    inst = await _get_instance_or_404(db, instance_id)
    actor_role = _normalize_actor_role(current_user.role)

    is_own_instance = False
    if actor_role == "student":
        await _ensure_student_owns_instance(db, current_user, inst)
        is_own_instance = True
    elif actor_role not in ("admin", "deputy_education", "staff"):
        raise HTTPException(status_code=403, detail="شما مجوز شروع دوباره این فرایند را ندارید.")

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

    forms = get_process_forms(instance.process_code, state_code=instance.current_state_code)
    ctx_before = instance.context_data or {}
    ok, missing = validate_student_step_forms(forms, request.form_values or {}, ctx_before)
    if not ok:
        raise HTTPException(status_code=400, detail={"error": "validation_failed", "missing": missing})

    sanitized = sanitize_form_values(forms, request.form_values or {}, ctx_before)
    if instance.process_code == "educational_leave" and "leave_terms" in sanitized:
        try:
            sanitized["leave_terms"] = int(sanitized["leave_terms"])
        except (TypeError, ValueError):
            pass
    if (
        instance.process_code == "upgrade_to_ta"
        and instance.current_state_code == "commitment_signature"
    ):
        if sanitized.get("step_otp_verified") is not True:
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
    ctx = apply_register_to_context(
        instance.context_data or {},
        instance.current_state_code,
        sanitized,
    )
    if sanitized.get("final_report_pdf"):
        ctx["final_report_uploaded_at"] = datetime.now(timezone.utc).isoformat()
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()

    auto_advanced = False
    if (
        instance.current_state_code == "documents_upload"
        and instance.process_code == "introductory_course_registration"
    ):
        engine = StateMachineEngine(db)
        try:
            adv = await engine.execute_transition(
                uuid.UUID(instance_id),
                "documents_submitted",
                current_user.id,
                _normalize_actor_role(current_user.role),
                None,
            )
            auto_advanced = bool(adv.success)
            if not adv.success and adv.error:
                logger.info(
                    "register_student_step_forms: auto documents_submitted skipped (%s)",
                    adv.error,
                )
        except (InvalidTransitionError, UnauthorizedError, InstanceNotFoundError) as e:
            logger.info("register_student_step_forms: auto documents_submitted not run: %s", e)
        except Exception:
            logger.exception("register_student_step_forms: auto documents_submitted failed")

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
    from app.services.otp_service import request_otp as do_request

    result = await do_request(db, phone)
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
    ok, err = validate_selected_courses_for_process(instance.process_code, ctx, new_codes)
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
    actor_role = _normalize_actor_role(current_user.role)
    if actor_role == "student":
        raise HTTPException(status_code=403, detail="Only operators can download marketing pack")

    instance = await _get_instance_or_404(db, instance_id)
    from app.services.semester_prep_service import PREP_PROCESS_CODES

    if instance.process_code not in PREP_PROCESS_CODES:
        raise HTTPException(status_code=400, detail="این خروجی فقط برای فرایند آماده‌سازی ترم است")
    if (instance.current_state_code or "") != "marketing_campaign":
        raise HTTPException(status_code=400, detail="خروجی PDF فقط در مرحلهٔ کمپین بازاریابی در دسترس است")
    if not _portal_role_can_act_on_state(actor_role, instance.process_code, "marketing_campaign"):
        raise HTTPException(
            status_code=403,
            detail="دانلود PDF این مرحله فقط برای مسئول پذیرش مجاز است.",
        )

    from app.services.semester_prep_marketing_pdf import build_marketing_campaign_pdf_bytes

    ctx = StateMachineEngine._as_mapping(instance.context_data)
    name = (current_user.full_name_fa or current_user.username or "").strip()
    try:
        pdf_bytes = build_marketing_campaign_pdf_bytes(
            instance.process_code,
            ctx,
            recipient_display_name=name,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

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
    actor_role = _normalize_actor_role(current_user.role)
    if actor_role == "student":
        raise HTTPException(status_code=403, detail="Only operators can register operator step forms")

    instance = await _get_instance_or_404(db, instance_id)
    if instance.is_completed or instance.is_cancelled:
        raise HTTPException(status_code=400, detail="فرایند تکمیل یا لغو شده؛ ثبت فرم مجاز نیست.")

    state = (request.state_code or instance.current_state_code or "").strip()
    if not state:
        raise HTTPException(status_code=400, detail="No state code")
    if state != (instance.current_state_code or ""):
        raise HTTPException(status_code=400, detail="فقط فرم مرحلهٔ فعلی قابل ثبت است.")

    if not _portal_role_can_act_on_state(actor_role, instance.process_code, state):
        raise HTTPException(
            status_code=403,
            detail="شما مسئول اقدام در این مرحله نیستید؛ فقط مشاهده مجاز است.",
        )

    raw_forms = get_process_forms(instance.process_code, state_code=state)
    forms = visible_forms_for_role(raw_forms, actor_role)
    if not forms:
        raise HTTPException(
            status_code=403,
            detail="شما اجازهٔ ثبت فرم این مرحله را ندارید.",
        )

    edit_names = editable_field_names(forms, actor_role)
    if not edit_names:
        raise HTTPException(
            status_code=403,
            detail="شما اجازهٔ ویرایش فرم این مرحله را ندارید.",
        )

    from app.services.process_form_prefill import apply_pre_filled_fields

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

    ok, missing = validate_operator_step_forms(forms, form_values, instance.context_data or {})
    if not ok:
        raise HTTPException(status_code=400, detail={"error": "validation_failed", "missing": missing})

    sanitized = sanitize_operator_form_values(forms, form_values)
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
    sanitized = sanitize_editable_payload(forms, role, request.field_values or {})
    if not sanitized:
        raise HTTPException(
            status_code=403,
            detail="هیچ فیلدی برای ویرایش با مجوز نقش شما در این درخواست وجود ندارد.",
        )

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all process instances for a student."""
    from app.core.resource_access import ensure_can_read_student

    await ensure_can_read_student(db, current_user, uuid.UUID(student_id))
    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == uuid.UUID(student_id)
    )
    if is_completed is not None:
        stmt = stmt.where(ProcessInstance.is_completed == is_completed)
    stmt = stmt.order_by(ProcessInstance.started_at.desc())

    result = await db.execute(stmt)
    instances = result.scalars().all()

    return {
        "instances": [
            {
                "instance_id": str(i.id),
                "process_code": i.process_code,
                "current_state": i.current_state_code,
                "is_completed": i.is_completed,
                "is_cancelled": i.is_cancelled,
                "started_at": i.started_at.isoformat() if i.started_at else None,
                "completed_at": i.completed_at.isoformat() if i.completed_at else None,
            }
            for i in instances
        ]
    }


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
