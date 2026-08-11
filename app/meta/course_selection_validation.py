"""اعتبارسنجی انتخاب دروس — از دادهٔ منتشرشدهٔ آماده‌سازی ترم."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.services.term_course_offering_service import (
    NO_OFFERINGS_REASON_FA,
    _filter_by_admission_kind,
    _filter_by_prerequisites,
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
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [normalize_legacy_course_code(str(x).strip()) for x in raw if x is not None and str(x).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                import json

                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [normalize_legacy_course_code(str(x).strip()) for x in parsed if str(x).strip()]
            except (json.JSONDecodeError, TypeError):
                return []
        return [normalize_legacy_course_code(p.strip()) for p in s.replace("،", ",").split(",") if p.strip()]
    return [normalize_legacy_course_code(str(raw).strip())] if str(raw).strip() else []


def resolve_admission_kind(ctx: dict) -> Optional[str]:
    """نوع پذیرش از نتیجهٔ مصاحبه / نوع پذیرش ذخیره‌شده (و فیلد قدیمی result)."""
    ir = ctx.get("interview_result")
    at = ctx.get("admission_type")
    # برخی مسیرها فقط «result» را در context نگه می‌دارند
    res = ctx.get("result")
    if ir == "single_course" or at == "single_course" or res == "single_course":
        return "single_course"
    if ir == "conditional_therapy" or at == "conditional_therapy" or res == "conditional_therapy":
        return "conditional_therapy"
    if ir in ("full_admission",) or at in ("full_admission", "full") or res in ("full_admission", "full"):
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


async def _resolve_allowed_options(
    db: AsyncSession,
    process_code: str,
    ctx: dict,
) -> tuple[list[dict[str, Any]], Optional[int], Optional[str]]:
    spec = _PROCESS_SPECS.get(process_code)
    if not spec:
        return [], None, "این فرایند از انتخاب درس پشتیبانی نمی‌کند."

    options = ctx.get("available_course_options")
    if not isinstance(options, list) or not options:
        options = await get_offering_options(
            db,
            program_kind=spec["program_kind"],
            term_number=spec["term_number"],
            term_code=ctx.get("term_code"),
        )

    if spec.get("use_prerequisites"):
        completed: set[str] = set()
        for c in ctx.get("completed_courses") or ctx.get("enrolled_courses") or []:
            if isinstance(c, dict):
                code = c.get("code") or c.get("course_code") or ""
            else:
                code = str(c)
            if code:
                completed.add(normalize_legacy_course_code(code))
        lms = ctx.get("lms") or {}
        for c in lms.get("enrolled_courses") or []:
            if isinstance(c, dict):
                code = c.get("code") or c.get("course_code") or ""
            else:
                code = str(c)
            if code:
                completed.add(normalize_legacy_course_code(code))
        options = _filter_by_prerequisites(options, completed)

    return _filter_by_admission_kind(
        options, ctx, term_number=spec["term_number"]
    )


async def validate_selected_courses_for_process(
    db: AsyncSession,
    process_code: str,
    ctx: object,
    selected: list[str],
) -> tuple[bool, Optional[str]]:
    data = StateMachineEngine._as_mapping(ctx)
    codes = normalize_course_codes(selected)
    if not codes:
        return False, "حداقل یک درس باید انتخاب شود."

    allowed_options, max_select, hint = await _resolve_allowed_options(db, process_code, data)
    if hint:
        return False, hint
    allowed_set = {str(o["value"]) for o in allowed_options}
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
    data = StateMachineEngine._as_mapping(ctx)
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
        allowed_set = {normalize_legacy_course_code(str(c)) for c in offered}
    else:
        filtered, max_select, hint = _filter_by_admission_kind(options, data, term_number=1)
        if hint:
            return False, hint
        allowed_set = {str(o["value"]) for o in filtered}
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
