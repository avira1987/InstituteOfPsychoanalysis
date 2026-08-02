"""Semester preparation process — institute anchor, start, status, pre-fill."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.process_forms import get_process_state_metadata
from app.meta.role_labels import label_role_fa
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import ProcessInstance
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.utils.shamsi_calendar_utils import farvardin_20_end_tehran, parse_iso_date, shamsi_parts, tehran_today

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

PREP_PROCESS_CODES = frozenset(
    {
        "fall_semester_preparation",
        "winter_semester_preparation",
    }
)

FALL_PREP = "fall_semester_preparation"
WINTER_PREP = "winter_semester_preparation"

# گروه‌های گیرندهٔ هشدار SLA در متادیتا (نه لزوماً نقش پورتال)
_SLA_WARNING_RECIPIENT_LABELS_FA: dict[str, str] = {
    "education_director": "مدیر آموزش",
    "deputy_education_director": "معاون مدیر آموزش",
    "deputy_education": "معاون مدیر آموزش",
    "course_committee_members": "اعضای کمیته دروس",
    "course_committee": "کمیته دروس",
    "course_committee_executive": "مسئول اجرایی کمیته دروس",
    "scientific_officer_course_committee": "مسئول علمی کمیته دروس",
    "admissions_officer": "مسئول پذیرش",
    "site_manager": "مسئول سایت",
}


def _warning_recipients_fa(codes: Any) -> list[str]:
    if not isinstance(codes, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in codes:
        code = str(raw or "").strip()
        if not code:
            continue
        label = _SLA_WARNING_RECIPIENT_LABELS_FA.get(code, code.replace("_", " "))
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def _parse_iso_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _compute_step_sla_deadline(
    *,
    state_code: str,
    ctx: dict[str, Any],
    sla_hours: int | None,
    last_transition_at: datetime | None,
    now: datetime,
) -> tuple[str | None, bool]:
    """(deadline_iso, is_overdue) for current prep step."""
    if state_code == "calendar_entry":
        dl = _parse_iso_datetime(ctx.get("calendar_sla_deadline_at"))
        if dl is not None:
            return dl.isoformat(), now > dl
    if sla_hours and last_transition_at is not None:
        try:
            hours = float(sla_hours)
        except (TypeError, ValueError):
            hours = None
        if hours and hours > 0:
            dl = last_transition_at + timedelta(hours=hours)
            return dl.isoformat(), now > dl
    return None, False


def _ctx(instance: ProcessInstance) -> dict[str, Any]:
    return StateMachineEngine._as_mapping(instance.context_data)


def _set_ctx(instance: ProcessInstance, ctx: dict[str, Any]) -> None:
    instance.context_data = ctx
    flag_modified(instance, "context_data")


def _calendar_sla_context_for_fall_start() -> dict[str, Any]:
    """Absolute deadline for calendar_entry (Farvardin 20 end, Tehran)."""
    deadline = farvardin_20_end_tehran()
    return {
        "calendar_sla_deadline_at": deadline.isoformat(),
        "prep_term_label_fa": f"ترم پاییز {shamsi_parts()[0]}",
    }


async def get_active_prep_instance(
    db: AsyncSession,
    process_code: str,
    *,
    student_id: uuid.UUID | None = None,
) -> ProcessInstance | None:
    if process_code not in PREP_PROCESS_CODES:
        return None
    if student_id is None:
        anchor = await ensure_institute_operational_student(db)
        student_id = anchor.id
    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.process_code == process_code,
            ProcessInstance.student_id == student_id,
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
        )
        .order_by(desc(ProcessInstance.started_at))
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def get_completed_fall_prep_instance(
    db: AsyncSession,
    *,
    student_id: uuid.UUID | None = None,
) -> ProcessInstance | None:
    if student_id is None:
        anchor = await ensure_institute_operational_student(db)
        student_id = anchor.id
    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.process_code == FALL_PREP,
            ProcessInstance.student_id == student_id,
            ProcessInstance.is_completed.is_(True),
            ProcessInstance.is_cancelled.is_(False),
            ProcessInstance.current_state_code == "published",
        )
        .order_by(desc(ProcessInstance.completed_at))
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def get_completed_prep_instance(
    db: AsyncSession,
    process_code: str,
    *,
    student_id: uuid.UUID | None = None,
) -> ProcessInstance | None:
    """آخرین نمونهٔ تکمیل‌شدهٔ (منتشرشدهٔ) یک فرایند آماده‌سازی ترم."""
    if process_code not in PREP_PROCESS_CODES:
        return None
    if student_id is None:
        anchor = await ensure_institute_operational_student(db)
        student_id = anchor.id
    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.process_code == process_code,
            ProcessInstance.student_id == student_id,
            ProcessInstance.is_completed.is_(True),
            ProcessInstance.is_cancelled.is_(False),
        )
        .order_by(desc(ProcessInstance.completed_at))
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


def _term_end_date_from_ctx(ctx: dict[str, Any]):
    """تاریخ پایان ترم برای تصمیم «شروع ترم جدید» (پایان زمستان، سپس پاییز)."""
    return parse_iso_date(ctx.get("winter_end_date")) or parse_iso_date(
        ctx.get("fall_end_date")
    )


async def get_or_start_prep_instance(
    db: AsyncSession,
    process_code: str,
    *,
    actor_id: uuid.UUID | None = None,
    actor_role: str = "system",
) -> tuple[ProcessInstance, bool]:
    """Return (instance, created). Idempotent for active instance."""
    if process_code not in PREP_PROCESS_CODES:
        raise ValueError(f"unsupported process_code: {process_code}")

    anchor = await ensure_institute_operational_student(db)
    existing = await get_active_prep_instance(db, process_code, student_id=anchor.id)
    if existing is not None:
        return existing, False

    if process_code == WINTER_PREP:
        fall_done = await get_completed_fall_prep_instance(db, student_id=anchor.id)
        if fall_done is None:
            raise ValueError("fall_semester_preparation must reach published before winter prep")

    initial_context: dict[str, Any] = {}
    if process_code == FALL_PREP:
        initial_context.update(_calendar_sla_context_for_fall_start())

    engine = StateMachineEngine(db)
    instance = await engine.start_process(
        process_code=process_code,
        student_id=anchor.id,
        actor_id=actor_id or SYSTEM_ACTOR_ID,
        actor_role=actor_role,
        initial_context=initial_context,
    )
    return instance, True


async def ensure_fall_prep_started(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    actor_role: str = "system",
) -> dict[str, Any]:
    inst, created = await get_or_start_prep_instance(
        db, FALL_PREP, actor_id=actor_id, actor_role=actor_role
    )
    return {
        "process_code": FALL_PREP,
        "instance_id": str(inst.id),
        "current_state": inst.current_state_code,
        "created": created,
    }


async def ensure_winter_prep_started(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    actor_role: str = "system",
) -> dict[str, Any]:
    inst, created = await get_or_start_prep_instance(
        db, WINTER_PREP, actor_id=actor_id, actor_role=actor_role
    )
    return {
        "process_code": WINTER_PREP,
        "instance_id": str(inst.id),
        "current_state": inst.current_state_code,
        "created": created,
    }


async def should_auto_start_winter(db: AsyncSession, today=None) -> bool:
    """True when fall is published, no active winter prep, and within auto-start window."""
    from datetime import timedelta

    from app.config import get_settings
    from app.utils.shamsi_calendar_utils import tehran_today

    fall = await get_completed_fall_prep_instance(db)
    if fall is None:
        return False
    if await get_active_prep_instance(db, WINTER_PREP) is not None:
        return False
    ctx = _ctx(fall)
    winter_start = parse_iso_date(ctx.get("winter_start_date"))
    if winter_start is None:
        return False
    ref = today or tehran_today()
    days_before = int(get_settings().WINTER_PREP_AUTO_START_DAYS_BEFORE or 30)
    window_start = winter_start - timedelta(days=days_before)
    return window_start <= ref <= winter_start


async def load_fall_prep_context_field(
    db: AsyncSession,
    field_name: str,
) -> Any:
    """Read a field from fall prep instance context (active first, then latest completed)."""
    anchor = await ensure_institute_operational_student(db)
    active = await get_active_prep_instance(db, FALL_PREP, student_id=anchor.id)
    for inst in (active, await get_completed_fall_prep_instance(db, student_id=anchor.id)):
        if inst is None:
            continue
        ctx = _ctx(inst)
        val = ctx.get(field_name)
        if val is not None:
            return val
        # سازگاری با دادهٔ قدیمی تک‌جدولی
        legacy = ctx.get("courses")
        if field_name == "courses_fall" and isinstance(legacy, list):
            return legacy
        if field_name == "courses_winter" and isinstance(legacy, list):
            return legacy
        if field_name == "courses_finalized_fall":
            legacy_fin = ctx.get("courses_finalized")
            if isinstance(legacy_fin, list):
                return legacy_fin
        if field_name == "courses_finalized_winter":
            legacy_fin = ctx.get("courses_finalized")
            if isinstance(legacy_fin, list):
                return legacy_fin
    return None


def _is_effectively_empty_course_table(rows: Any) -> bool:
    """جدول دروس خالی است یا فقط ردیف placeholder (بدون نام درس) دارد."""
    if not isinstance(rows, list) or not rows:
        return True
    for row in rows:
        if isinstance(row, dict) and str(row.get("course_name") or "").strip():
            return False
    return True


def _build_courses_finalized_from_draft(courses: Any) -> Optional[list[dict[str, Any]]]:
    """لیست دروس مرحلهٔ ۴ را برای جدول نهایی‌سازی (مرحلهٔ ۵) نگاشت می‌کند."""
    if not isinstance(courses, list) or not courses:
        return None
    rows: list[dict[str, Any]] = []
    for row in courses:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "course_name": row.get("course_name") or "",
                "track": row.get("track") or "",
                "day": row.get("proposed_day") or row.get("day") or "",
                "time": row.get("proposed_time") or row.get("time") or "",
                "instructor": row.get("instructor") or "",
                "teaching_assistant": row.get("teaching_assistant") or "",
                "classroom_location": row.get("classroom_location") or "",
                "instructor_coordinated": bool(row.get("instructor_coordinated")),
            }
        )
    return rows or None


def _apply_course_finalization_prefill(
    process_code: str,
    state_code: str,
    context_data: dict[str, Any],
) -> dict[str, Any]:
    """پیش‌پر جدول نهایی از لیست دروس همان نمونه (مرحلهٔ ۴ → ۵)."""
    out = dict(context_data or {})
    if process_code == FALL_PREP and state_code == "course_finalization":
        pairs = (
            ("courses_finalized_fall", "courses_fall"),
            ("courses_finalized_winter", "courses_winter"),
        )
        for final_name, draft_name in pairs:
            if not _is_effectively_empty_course_table(out.get(final_name)):
                continue
            draft = out.get(draft_name)
            if not draft and draft_name == "courses_fall":
                draft = out.get("courses")
            built = _build_courses_finalized_from_draft(draft)
            if built:
                out[final_name] = built
    if process_code == WINTER_PREP and state_code == "course_finalization":
        if _is_effectively_empty_course_table(out.get("courses_finalized")):
            draft = out.get("courses")
            built = _build_courses_finalized_from_draft(draft)
            if built:
                out["courses_finalized"] = built
    return out


async def apply_pre_filled_fields(
    db: AsyncSession,
    process_code: str,
    state_code: str,
    context_data: dict[str, Any],
) -> dict[str, Any]:
    """Merge pre_filled_from field values into context for operator forms."""
    from app.meta.process_forms import get_process_forms
    from app.services.financial_program_defaults_service import (
        OTHER_PAYMENT_DEFAULT_KEYS,
        PREP_FINANCIAL_FORM_KEYS,
        TERM_TUITION_KEYS,
        get_effective_financial_program_defaults,
    )

    out = _apply_course_finalization_prefill(process_code, state_code, context_data)
    forms = get_process_forms(process_code, state_code=state_code)
    for form in forms:
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            pref = field.get("pre_filled_from")
            if not name or not pref or out.get(name) not in (None, "", []):
                continue
            value = await _resolve_pre_filled(db, str(pref))
            if value is not None:
                out[name] = value

    # پیش‌پر شهریه و سایر پیش‌فرض‌های پرداخت از داشبورد مالی (منبع مشترک)
    if process_code == FALL_PREP and state_code == "tuition_entry":
        needs = [k for k in PREP_FINANCIAL_FORM_KEYS if out.get(k) in (None, "", [])]
        if needs:
            fd = await get_effective_financial_program_defaults(db)
            optional_zero = {"class_session_fee_toman", "course_session_fee_toman"}
            for key in needs:
                raw = fd.get(key)
                if raw is None:
                    continue
                try:
                    num = float(raw)
                except (TypeError, ValueError):
                    continue
                if key in optional_zero:
                    if num > 0:
                        out[key] = num
                    continue
                if key in TERM_TUITION_KEYS or key in (
                    "registration_interview_fee_rial",
                    "start_therapy_first_session_fee_rial",
                    "extra_session_fee_rial",
                ):
                    if int(num) >= 1000:
                        out[key] = int(round(num))
                    continue
                if key in OTHER_PAYMENT_DEFAULT_KEYS and num > 0:
                    out[key] = num
    return out


async def _resolve_pre_filled(db: AsyncSession, spec: str) -> Any:
    """spec: 'fall_semester_preparation.courses_winter' یا 'fall_semester_preparation.course_list_form'."""
    parts = spec.split(".", 1)
    if len(parts) != 2:
        return None
    proc, tail = parts[0].strip(), parts[1].strip()
    field = tail
    if tail == "course_list_form":
        field = "courses_winter"
    elif tail.endswith("_form"):
        field = "courses"
    if proc == FALL_PREP:
        return await load_fall_prep_context_field(db, field)
    return None


def _recipient_label_fa(code: Any) -> str:
    c = str(code or "").strip()
    if not c:
        return ""
    return _SLA_WARNING_RECIPIENT_LABELS_FA.get(c, c.replace("_", " "))


def _extract_sla_warning_rows(inst: ProcessInstance, process_code: str) -> list[dict[str, Any]]:
    ctx = _ctx(inst)
    raw_log = ctx.get("__sla_warning_log")
    if not isinstance(raw_log, list):
        return []
    rows: list[dict[str, Any]] = []
    for entry in raw_log:
        if not isinstance(entry, dict):
            continue
        recipients = entry.get("recipients") or []
        recipients_view: list[dict[str, Any]] = []
        any_delivered = False
        for r in recipients:
            if not isinstance(r, dict):
                continue
            delivered = bool(r.get("delivered"))
            any_delivered = any_delivered or delivered
            recipients_view.append(
                {
                    "role": r.get("recipient_role"),
                    "role_fa": _recipient_label_fa(r.get("recipient_role")),
                    "contact": r.get("contact"),
                    "delivered": delivered,
                }
            )
        rows.append(
            {
                "process_code": process_code,
                "instance_id": str(inst.id),
                "state_code": entry.get("state_code"),
                "fired_at": entry.get("fired_at"),
                "notification_type": entry.get("notification_type"),
                "template": entry.get("template"),
                "message": entry.get("message"),
                "recipients": recipients_view,
                "delivered": any_delivered,
            }
        )
    return rows


async def build_prep_sla_warning_log(db: AsyncSession) -> dict[str, Any]:
    """فهرست هشدارهای مهلت ثبت‌شده برای فرایندهای آماده‌سازی ترم (برای UI بررسی)."""
    anchor = await ensure_institute_operational_student(db)
    rows: list[dict[str, Any]] = []
    for code in (FALL_PREP, WINTER_PREP):
        inst = await get_active_prep_instance(db, code, student_id=anchor.id)
        if inst is not None:
            rows.extend(_extract_sla_warning_rows(inst, code))
    fall_done = await get_completed_fall_prep_instance(db, student_id=anchor.id)
    if fall_done is not None:
        rows.extend(_extract_sla_warning_rows(fall_done, FALL_PREP))
    rows.sort(key=lambda r: str(r.get("fired_at") or ""), reverse=True)
    return {
        "anchor_student_code": anchor.student_code,
        "count": len(rows),
        "warnings": rows,
    }


async def build_prep_status(db: AsyncSession) -> dict[str, Any]:
    """Status payload for admin API."""
    anchor = await ensure_institute_operational_student(db)
    out: dict[str, Any] = {
        "anchor_student_code": anchor.student_code,
        "anchor_student_id": str(anchor.id),
        "processes": {},
    }
    engine = StateMachineEngine(db)
    for code in (FALL_PREP, WINTER_PREP):
        inst = await get_active_prep_instance(db, code, student_id=anchor.id)
        entry: dict[str, Any] = {
            "active": inst is not None,
            "instance_id": str(inst.id) if inst else None,
            "current_state": inst.current_state_code if inst else None,
            "is_completed": bool(inst.is_completed) if inst else False,
        }
        if inst is not None:
            entry["student_id"] = str(anchor.id)
            proc_def = await engine.get_process_definition(code)
            sd_stmt = select(StateDefinition).where(
                StateDefinition.process_id == proc_def.id,
                StateDefinition.code == inst.current_state_code,
            )
            sd = (await db.execute(sd_stmt)).scalars().first()
            entry["state_name_fa"] = sd.name_fa if sd else inst.current_state_code
            entry["assigned_role"] = sd.assigned_role if sd else None
            if entry["assigned_role"]:
                entry["assigned_role_fa"] = label_role_fa(entry["assigned_role"])
            if sd and sd.sla_hours:
                entry["sla_hours"] = sd.sla_hours
            ctx = _ctx(inst)
            now = datetime.now(timezone.utc)
            state_meta = get_process_state_metadata(code, inst.current_state_code or "")
            warning_codes = state_meta.get("sla_warning_recipients") or []
            entry["sla_warning_recipients_fa"] = _warning_recipients_fa(warning_codes)
            deadline_at, overdue = _compute_step_sla_deadline(
                state_code=inst.current_state_code or "",
                ctx=ctx,
                sla_hours=sd.sla_hours if sd else None,
                last_transition_at=inst.last_transition_at,
                now=now,
            )
            if deadline_at:
                entry["sla_deadline_at"] = deadline_at
                entry["sla_overdue"] = overdue
            elif sd and sd.sla_hours:
                elapsed = (now - inst.last_transition_at).total_seconds() / 3600
                entry["sla_hours"] = sd.sla_hours
                entry["sla_overdue"] = elapsed > sd.sla_hours
            cal_deadline = ctx.get("calendar_sla_deadline_at")
            if inst.current_state_code == "calendar_entry" and cal_deadline:
                try:
                    dl = _parse_iso_datetime(cal_deadline)
                    if dl is not None:
                        entry["calendar_sla_deadline_at"] = dl.isoformat()
                        if "sla_deadline_at" not in entry:
                            entry["sla_deadline_at"] = dl.isoformat()
                            entry["sla_overdue"] = now > dl
                except (TypeError, ValueError):
                    pass
        else:
            completed = await get_completed_prep_instance(db, code, student_id=anchor.id)
            if completed is not None:
                entry["completed"] = True
                entry["completed_instance_id"] = str(completed.id)
                entry["completed_current_state"] = completed.current_state_code
                entry["completed_at"] = (
                    completed.completed_at.isoformat() if completed.completed_at else None
                )
                cctx = _ctx(completed)
                term_end = _term_end_date_from_ctx(cctx)
                entry["term_end_date"] = term_end.isoformat() if term_end else None
                if term_end is not None:
                    from app.utils.shamsi_calendar_utils import tehran_today

                    # تا پایان ترم قفل؛ فقط بعد از پایان ترم شروع ترم جدید مجاز است.
                    entry["can_start_new_term"] = tehran_today() > term_end
                else:
                    entry["can_start_new_term"] = True
            else:
                entry["can_start_new_term"] = True
            if code == FALL_PREP:
                last = completed or await get_completed_fall_prep_instance(
                    db, student_id=anchor.id
                )
                entry["last_completed_at"] = (
                    last.completed_at.isoformat() if last and last.completed_at else None
                )
        out["processes"][code] = entry
    from app.services.semester_prep_readiness_service import compute_semester_prep_readiness

    out["readiness"] = await compute_semester_prep_readiness(db)
    return out


FALL_MARKETING_CONTEXT_KEYS: tuple[str, ...] = (
    "fall_start_date",
    "fall_end_date",
    "winter_start_date",
    "winter_end_date",
    "registration_payment_window_start",
    "registration_payment_window_end",
    "per_unit_cost_introductory",
    "per_unit_cost_comprehensive",
    "interview_fee_introductory",
    "interview_fee_comprehensive",
    "courses_finalized_fall",
    "courses_finalized_winter",
    "courses_fall",
    "courses_winter",
)

WINTER_MARKETING_CONTEXT_KEYS: tuple[str, ...] = (
    "courses",
    "courses_finalized",
    "courses_winter",
)

FALL_PREP_STEP_STATES: tuple[str, ...] = (
    "calendar_entry",
    "tuition_entry",
    "license_check",
    "course_list_creation",
    "course_finalization",
    "marketing_campaign",
    "interviewer_assignment",
    "interview_scheduling",
)

WINTER_PREP_STEP_STATES: tuple[str, ...] = (
    "license_check",
    "course_list_review",
    "course_finalization",
    "marketing_campaign",
    "interviewer_assignment",
    "interview_scheduling",
)

SEMESTER_PREP_INTERVIEW_DATE_RANGE_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("comprehensive_date_range_start", "comprehensive_date_range_end", "دوره جامع"),
    ("introductory_date_range_start", "introductory_date_range_end", "دوره آشنایی"),
)

# فیلدهای تاریخ فرم تقویم آموزشی (پاییز) — برای اعتبارسنجی و ویرایش پس از calendar_entry
SEMESTER_PREP_CALENDAR_DATE_FIELDS: tuple[str, ...] = (
    "fall_start_date",
    "fall_end_date",
    "winter_start_date",
    "winter_end_date",
    "registration_payment_window_start",
    "registration_payment_window_end",
    "intern_interview_deadline_start",
    "intern_interview_deadline_end",
    "teaching_assistant_interview_deadline_start",
    "teaching_assistant_interview_deadline_end",
    "nowruz_holiday_start",
    "nowruz_holiday_end",
)

SEMESTER_PREP_CALENDAR_DATE_RANGE_LIST_FIELDS: tuple[str, ...] = (
    "fall_break_periods",
    "winter_break_periods",
)

_CALENDAR_FIELD_LABELS_FA: dict[str, str] = {
    "fall_start_date": "تاریخ شروع ترم پاییز",
    "fall_end_date": "تاریخ پایان ترم پاییز",
    "winter_start_date": "تاریخ شروع ترم زمستان",
    "winter_end_date": "تاریخ پایان ترم زمستان",
    "registration_payment_window_start": "شروع پنجره ثبت‌نام",
    "registration_payment_window_end": "پایان پنجره ثبت‌نام",
    "intern_interview_deadline_start": "شروع بازه مصاحبه انترن‌ها",
    "intern_interview_deadline_end": "پایان بازه مصاحبه انترن‌ها",
    "teaching_assistant_interview_deadline_start": "شروع بازه مصاحبه کمک مدرسی",
    "teaching_assistant_interview_deadline_end": "پایان بازه مصاحبه کمک مدرسی",
    "nowruz_holiday_start": "شروع تعطیلات نوروز",
    "nowruz_holiday_end": "پایان تعطیلات نوروز",
    "fall_break_periods": "دوره‌های تعطیلی ترم پاییز",
    "winter_break_periods": "دوره‌های تعطیلی ترم زمستان",
}

# نسبت به سال شمسی جاری (تهران): یک سال قبل تا یک سال بعد
_CALENDAR_SHAMSI_YEAR_OFFSET_MIN = -1
_CALENDAR_SHAMSI_YEAR_OFFSET_MAX = 1


def semester_prep_calendar_shamsi_year_bounds(
    today: date | None = None,
) -> tuple[int, int]:
    """(حداقل سال شمسی، حداکثر سال شمسی) مجاز برای تاریخ‌های تقویم آماده‌سازی ترم."""
    ref = today or tehran_today()
    jy = shamsi_parts(ref)[0]
    return jy + _CALENDAR_SHAMSI_YEAR_OFFSET_MIN, jy + _CALENDAR_SHAMSI_YEAR_OFFSET_MAX


def _shamsi_year_of_iso(value: Any) -> int | None:
    d = parse_iso_date(value)
    if d is None:
        return None
    return shamsi_parts(d)[0]


def _calendar_year_outlier_message(field_key: str, jy: int, min_jy: int, max_jy: int) -> str:
    label = _CALENDAR_FIELD_LABELS_FA.get(field_key, field_key)
    return (
        f"«{label}» (سال {jy}) خارج از بازهٔ مجاز سال شمسی {min_jy} تا {max_jy} نسبت به سال جاری است."
    )


def semester_prep_calendar_date_errors(
    form_values: dict[str, Any] | None,
    *,
    today: date | None = None,
) -> list[str]:
    """خطاهای تاریخ تقویم: سال پرت نسبت به سال جاری و ترتیب نادرست تاریخ‌ها."""
    errors: list[str] = []
    vals = form_values or {}
    min_jy, max_jy = semester_prep_calendar_shamsi_year_bounds(today=today)

    def check_iso_field(key: str) -> None:
        raw = vals.get(key)
        if raw in (None, ""):
            return
        jy = _shamsi_year_of_iso(raw)
        if jy is None:
            return
        if jy < min_jy or jy > max_jy:
            errors.append(_calendar_year_outlier_message(key, jy, min_jy, max_jy))

    for key in SEMESTER_PREP_CALENDAR_DATE_FIELDS:
        check_iso_field(key)

    for list_key in SEMESTER_PREP_CALENDAR_DATE_RANGE_LIST_FIELDS:
        ranges = vals.get(list_key)
        if not isinstance(ranges, list):
            continue
        for i, row in enumerate(ranges):
            if not isinstance(row, dict):
                continue
            for part_key in ("start", "end"):
                raw = row.get(part_key)
                if raw in (None, ""):
                    continue
                jy = _shamsi_year_of_iso(raw)
                if jy is None:
                    continue
                if jy < min_jy or jy > max_jy:
                    label = _CALENDAR_FIELD_LABELS_FA.get(list_key, list_key)
                    errors.append(
                        f"«{label}» — بازه {i + 1}: سال {jy} خارج از بازهٔ مجاز "
                        f"{min_jy} تا {max_jy} است."
                    )
            start_d = parse_iso_date(row.get("start"))
            end_d = parse_iso_date(row.get("end"))
            if start_d and end_d and end_d <= start_d:
                label = _CALENDAR_FIELD_LABELS_FA.get(list_key, list_key)
                errors.append(f"«{label}» — بازه {i + 1}: تاریخ پایان باید بعد از شروع باشد.")

    def check_order(start_key: str, end_key: str, message: str) -> None:
        start_d = parse_iso_date(vals.get(start_key))
        end_d = parse_iso_date(vals.get(end_key))
        if start_d and end_d and end_d < start_d:
            errors.append(message)

    check_order(
        "fall_start_date",
        "fall_end_date",
        "تاریخ پایان ترم پاییز نمی‌تواند قبل از شروع باشد.",
    )
    check_order(
        "winter_start_date",
        "winter_end_date",
        "تاریخ پایان ترم زمستان نمی‌تواند قبل از شروع باشد.",
    )
    check_order(
        "registration_payment_window_start",
        "registration_payment_window_end",
        "پایان پنجره ثبت‌نام نمی‌تواند قبل از شروع باشد.",
    )
    check_order(
        "intern_interview_deadline_start",
        "intern_interview_deadline_end",
        "پایان بازه مصاحبه انترن‌ها نمی‌تواند قبل از شروع باشد.",
    )
    check_order(
        "teaching_assistant_interview_deadline_start",
        "teaching_assistant_interview_deadline_end",
        "پایان بازه مصاحبه کمک مدرسی نمی‌تواند قبل از شروع باشد.",
    )
    check_order(
        "nowruz_holiday_start",
        "nowruz_holiday_end",
        "پایان تعطیلات نوروز نمی‌تواند قبل از شروع باشد.",
    )

    fall_end = parse_iso_date(vals.get("fall_end_date"))
    winter_start = parse_iso_date(vals.get("winter_start_date"))
    if fall_end and winter_start and winter_start < fall_end:
        errors.append("شروع ترم زمستان نمی‌تواند قبل از پایان ترم پاییز باشد.")

    return errors


def context_has_outlier_calendar_dates(
    context: dict[str, Any] | None,
    *,
    today: date | None = None,
) -> bool:
    """آیا در context تاریخ تقویم با سال پرت ثبت شده است؟"""
    return bool(semester_prep_calendar_date_errors(context or {}, today=today))


SEMESTER_PREP_CALENDAR_SYNC_FIELD_NAMES: frozenset[str] = frozenset(
    SEMESTER_PREP_CALENDAR_DATE_FIELDS
) | frozenset(SEMESTER_PREP_CALENDAR_DATE_RANGE_LIST_FIELDS)


async def sync_active_institute_calendar_after_prep_correction(
    db: AsyncSession,
    instance: ProcessInstance,
    *,
    updated_field_names: set[str] | frozenset[str] | None = None,
    published_by: uuid.UUID | None = None,
):
    """پس از ویرایش تقویم در آماده‌سازی پاییزِ منتشرشده، رکورد تقویم فعال انستیتو را به‌روز کند."""
    if instance.process_code != FALL_PREP:
        return None
    if instance.current_state_code != "published":
        return None
    if updated_field_names is not None:
        if not SEMESTER_PREP_CALENDAR_SYNC_FIELD_NAMES.intersection(updated_field_names):
            return None

    from app.services.institute_calendar_service import publish_calendar_from_instance_context

    ctx = dict(instance.context_data or {})
    return await publish_calendar_from_instance_context(
        db,
        instance,
        ctx,
        published_by=published_by,
        notify=False,
    )


def semester_prep_interview_date_range_errors(form_values: dict[str, Any] | None) -> list[str]:
    """خطاهای بازهٔ تاریخ مصاحبه (پایان قبل از شروع)."""
    errors: list[str] = []
    vals = form_values or {}
    for start_key, end_key, label in SEMESTER_PREP_INTERVIEW_DATE_RANGE_PAIRS:
        start_d = parse_iso_date(vals.get(start_key))
        end_d = parse_iso_date(vals.get(end_key))
        if start_d is None or end_d is None:
            continue
        if end_d < start_d:
            errors.append(f"پایان بازه مصاحبه {label} نمی‌تواند قبل از شروع باشد.")
    return errors


def _context_key_present(ctx: dict[str, Any], key: str) -> bool:
    val = ctx.get(key)
    if val in (None, ""):
        return False
    if isinstance(val, list):
        return len(val) > 0 and any(
            isinstance(row, dict) and any(v not in (None, "", False) for v in row.values())
            for row in val
        )
    return True


def _table_row_count(value: Any) -> int:
    if not isinstance(value, list):
        return 0
    return sum(
        1
        for row in value
        if isinstance(row, dict) and any(v not in (None, "", False) for v in row.values())
    )


def build_instance_marketing_diagnostic(
    inst: ProcessInstance,
    process_code: str,
) -> dict[str, Any]:
    """خلاصهٔ تشخیصی context برای مرحلهٔ کمپین بازاریابی (read-only)."""
    from app.meta.student_step_forms import CTX_SUBMITTED

    ctx = _ctx(inst)
    submitted = StateMachineEngine._as_mapping(ctx.get(CTX_SUBMITTED))
    step_states = FALL_PREP_STEP_STATES if process_code == FALL_PREP else WINTER_PREP_STEP_STATES
    marketing_keys = (
        FALL_MARKETING_CONTEXT_KEYS if process_code == FALL_PREP else WINTER_MARKETING_CONTEXT_KEYS
    )

    submitted_states = {
        state: bool(submitted.get(state))
        for state in step_states
    }
    key_presence = {key: _context_key_present(ctx, key) for key in marketing_keys}
    table_counts = {
        key: _table_row_count(ctx.get(key))
        for key in marketing_keys
        if key.startswith("courses")
    }

    return {
        "process_code": process_code,
        "instance_id": str(inst.id),
        "current_state": inst.current_state_code,
        "submitted_states": submitted_states,
        "marketing_keys_present": key_presence,
        "course_table_row_counts": table_counts,
        "has_marketing_data": any(key_presence.values()),
    }


async def build_marketing_handoff_diagnostic(
    db: AsyncSession,
    *,
    process_code: str | None = None,
) -> dict[str, Any]:
    """تشخیص خروجی کمپین برای instance فعال آماده‌سازی ترم روی anchor انستیتو."""
    anchor = await ensure_institute_operational_student(db)
    codes = (process_code,) if process_code in PREP_PROCESS_CODES else (FALL_PREP, WINTER_PREP)
    processes: dict[str, Any] = {}
    for code in codes:
        inst = await get_active_prep_instance(db, code, student_id=anchor.id)
        if inst is None:
            completed = await get_completed_prep_instance(db, code, student_id=anchor.id)
            if completed is not None:
                processes[code] = build_instance_marketing_diagnostic(completed, code)
                processes[code]["active"] = False
            else:
                processes[code] = {"process_code": code, "active": False, "instance_id": None}
            continue
        entry = build_instance_marketing_diagnostic(inst, code)
        entry["active"] = True
        processes[code] = entry

    return {
        "anchor_student_code": anchor.student_code,
        "processes": processes,
    }
