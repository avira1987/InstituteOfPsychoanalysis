"""اعتبارسنجی انتخاب دروس — از دادهٔ منتشرشدهٔ آماده‌سازی ترم."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.services.course_prerequisite_service import (
    classify_student_course_progress,
    partition_options_by_prerequisites,
)
from app.services.term_course_offering_service import (
    NO_OFFERINGS_REASON_FA,
    _filter_by_admission_kind,
    canonicalize_course_option,
    extract_course_codes,
    get_offering_options,
    normalize_legacy_course_code,
)

INTRO_REG_COURSE_FIELD = "selected_courses"
INTRO_REG_COURSE_STATE = "course_selection"
INTRO_REG_EDITABLE_STATES: frozenset[str] = frozenset({"course_selection", "payment"})

INTRO_TERM2_COURSE_FIELD = "available_courses"
INTRO_TERM2_COURSE_STATE = "course_selection"
INTRO_TERM2_EDITABLE_STATES: frozenset[str] = frozenset(
    {"course_selection", "payment_method", "payment_processing"}
)

_PROCESS_SPECS: dict[str, dict[str, Any]] = {
    "introductory_course_registration": {
        "field_name": INTRO_REG_COURSE_FIELD,
        "form_state": INTRO_REG_COURSE_STATE,
        "editable_states": INTRO_REG_EDITABLE_STATES,
        "program_kind": "introductory",
        "term_number": 1,
        "use_prerequisites": True,
    },
    "intro_second_semester_registration": {
        "field_name": INTRO_TERM2_COURSE_FIELD,
        "form_state": INTRO_TERM2_COURSE_STATE,
        "editable_states": INTRO_TERM2_EDITABLE_STATES,
        "program_kind": "introductory",
        "term_number": 2,
        "use_prerequisites": True,
    },
}


def normalize_course_codes(raw: Any) -> list[str]:
    return extract_course_codes(raw)


def resolve_admission_kind(ctx: dict) -> Optional[str]:
    """نوع پذیرش از نتیجهٔ مصاحبه / نوع پذیرش ذخیره‌شده (و فیلد قدیمی result)."""
    from app.services.admission_type_service import (
        ADMISSION_CONDITIONAL_THERAPY,
        ADMISSION_FULL,
        ADMISSION_SINGLE_COURSE,
        overlay_admission_on_context,
        resolve_admission_type_from_context,
    )

    data = overlay_admission_on_context(ctx if isinstance(ctx, dict) else {})
    canon = resolve_admission_type_from_context(data)
    if canon == ADMISSION_SINGLE_COURSE:
        return "single_course"
    if canon == ADMISSION_CONDITIONAL_THERAPY:
        return "conditional_therapy"
    if canon == ADMISSION_FULL:
        return "full_admission"
    return None


def _labels_from_ctx(data: dict) -> dict[str, str]:
    labels = data.get("course_labels")
    if isinstance(labels, dict):
        return {str(k): str(v) for k, v in labels.items()}
    options = data.get("available_course_options") or []
    if isinstance(options, list):
        return {
            str(o.get("value")): str(o.get("label_fa") or o.get("value"))
            for o in options
            if isinstance(o, dict) and o.get("value")
        }
    return {}


async def _state_codes_for_instance(db: AsyncSession, instance: Any) -> Optional[list[str]]:
    if instance is None:
        return None
    from app.models.operational_models import StateHistory

    rows = (
        await db.execute(
            select(StateHistory.to_state_code).where(StateHistory.instance_id == instance.id)
        )
    ).scalars().all()
    codes = [str(c) for c in rows if c]
    current = getattr(instance, "current_state_code", None)
    if current:
        codes.append(str(current))
    return codes


async def _resolve_allowed_options(
    db: AsyncSession,
    process_code: str,
    ctx: dict,
    *,
    student: Optional[Any] = None,
    state_codes: Optional[list] = None,
) -> tuple[list[dict[str, Any]], Optional[int], Optional[str]]:
    spec = _PROCESS_SPECS.get(process_code)
    if not spec:
        return [], None, "این فرایند از انتخاب درس پشتیبانی نمی‌کند."

    from app.services.admission_type_service import overlay_admission_on_context

    ctx = overlay_admission_on_context(ctx, student, state_codes=state_codes)
    db_options = await get_offering_options(
        db,
        program_kind=spec["program_kind"],
        term_number=spec["term_number"],
        term_code=ctx.get("term_code"),
    )
    ctx_options = ctx.get("available_course_options")
    if not isinstance(ctx_options, list):
        ctx_options = []
    raw_options = db_options if db_options else ctx_options
    options = [
        canonicalize_course_option(o) for o in raw_options if isinstance(o, dict)
    ]

    if spec.get("use_prerequisites"):
        passed, failed = classify_student_course_progress(ctx, student)
        options, _blocked = partition_options_by_prerequisites(options, passed, failed)

    return _filter_by_admission_kind(
        options, ctx, term_number=spec["term_number"]
    )


async def validate_selected_courses_for_process(
    db: AsyncSession,
    process_code: str,
    ctx: object,
    selected: list[str],
    student: Optional[Any] = None,
    instance: Optional[Any] = None,
) -> tuple[bool, Optional[str]]:
    from app.services.admission_type_service import overlay_admission_on_context

    state_codes = await _state_codes_for_instance(db, instance)
    data = overlay_admission_on_context(
        StateMachineEngine._as_mapping(ctx), student, state_codes=state_codes
    )
    codes = normalize_course_codes(selected)
    if not codes:
        return False, "حداقل یک درس باید انتخاب شود."

    allowed_options, max_select, hint = await _resolve_allowed_options(
        db, process_code, data, student=student, state_codes=state_codes
    )
    if hint:
        return False, hint
    allowed_set = {
        normalize_legacy_course_code(str(o.get("value") or ""))
        for o in allowed_options
        if o.get("value")
    }
    if not allowed_set:
        return False, NO_OFFERINGS_REASON_FA

    unknown = [c for c in codes if c not in allowed_set]
    if unknown:
        labels = _labels_from_ctx(data)
        names = [labels.get(c, c) for c in unknown]
        return False, f"درس(های) غیرمجاز برای این نوع پذیرش: {', '.join(names)}"
    if len(set(codes)) != len(codes):
        return False, "هر درس فقط یک‌بار قابل انتخاب است."
    if max_select is not None and len(codes) > max_select:
        return False, f"حداکثر {max_select} درس برای این پذیرش مجاز است."
    return True, None


def course_selection_config(process_code: str) -> Optional[dict[str, Any]]:
    spec = _PROCESS_SPECS.get(process_code)
    if not spec:
        return None
    return {
        "field_name": spec["field_name"],
        "form_state": spec["form_state"],
        "editable_states": spec["editable_states"],
        "catalog": "term_offerings",
    }


# Backward-compatible sync wrapper for tests that mock DB
def validate_intro_term1_selected_courses(ctx: object, selected: list[str]) -> tuple[bool, Optional[str]]:
    from app.services.admission_type_service import overlay_admission_on_context

    data = overlay_admission_on_context(StateMachineEngine._as_mapping(ctx))
    kind = resolve_admission_kind(data)
    if kind is None:
        return False, "نتیجهٔ مصاحبه در پرونده ثبت نشده است؛ انتخاب درس مجاز نیست."
    codes = normalize_course_codes(selected)
    if not codes:
        return False, "حداقل یک درس باید انتخاب شود."
    options = data.get("available_course_options") or []
    if not options:
        offered = data.get("available_courses") or []
        if not offered:
            return False, NO_OFFERINGS_REASON_FA
        options = [
            {"value": normalize_legacy_course_code(str(c)), "label_fa": str(c)}
            for c in offered
        ]
    filtered, max_select, hint = _filter_by_admission_kind(options, data, term_number=1)
    if hint:
        return False, hint
    allowed_set = {
        normalize_legacy_course_code(str(o.get("value") or ""))
        for o in filtered
        if o.get("value")
    }
    if not allowed_set:
        return False, NO_OFFERINGS_REASON_FA
    if max_select is not None and len(codes) > max_select:
        return False, f"حداکثر {max_select} درس برای این پذیرش مجاز است."
    unknown = [c for c in codes if c not in allowed_set]
    if unknown:
        labels = _labels_from_ctx(data)
        names = [labels.get(c, c) for c in unknown]
        return False, f"درس(های) غیرمجاز برای این نوع پذیرش: {', '.join(names)}"
    if len(set(codes)) != len(codes):
        return False, "هر درس فقط یک‌بار قابل انتخاب است."
    return True, None
