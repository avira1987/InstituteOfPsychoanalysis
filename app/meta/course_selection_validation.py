"""اعتبارسنجی انتخاب دروس ترم اول دوره آشنایی — هم‌تراز admin-ui/resolveCourseFieldOptions.js."""

from __future__ import annotations

from typing import Any, Optional

from app.core.engine import StateMachineEngine

INTRO_TERM1_COURSE_CODES: tuple[str, ...] = (
    "theory_1",
    "theory_2",
    "theory_3",
    "theory_4",
    "theory_5",
)

INTRO_TERM1_COURSE_LABELS_FA: dict[str, str] = {
    "theory_1": "تئوری روانکاوی ۱",
    "theory_2": "تئوری روانکاوی ۲",
    "theory_3": "تئوری روانکاوی ۳",
    "theory_4": "تئوری روانکاوی ۴",
    "theory_5": "تئوری روانکاوی ۵",
}

# فرایند ثبت‌نام ترم اول: فیلد selected_courses
INTRO_REG_COURSE_FIELD = "selected_courses"
INTRO_REG_COURSE_STATE = "course_selection"
INTRO_REG_EDITABLE_STATES: frozenset[str] = frozenset({"course_selection", "payment"})

# فرایند ترم دوم: فیلد available_courses در فرم دانشجو
INTRO_TERM2_COURSE_FIELD = "available_courses"
INTRO_TERM2_COURSE_STATE = "course_selection"
INTRO_TERM2_EDITABLE_STATES: frozenset[str] = frozenset(
    {"course_selection", "payment_method", "payment_processing"}
)


def normalize_course_codes(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                import json

                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except (json.JSONDecodeError, TypeError):
                return []
        return [p.strip() for p in s.replace("،", ",").split(",") if p.strip()]
    return [str(raw).strip()] if str(raw).strip() else []


def resolve_admission_kind(ctx: dict) -> Optional[str]:
    ir = ctx.get("interview_result")
    at = ctx.get("admission_type")
    if ir == "single_course" or at == "single_course":
        return "single_course"
    if ir == "conditional_therapy" or at == "conditional_therapy":
        return "conditional_therapy"
    if ir in ("full_admission",) or at in ("full_admission", "full"):
        return "full_admission"
    return None


def _parse_allowed_count(ctx: dict) -> Optional[int]:
    n = ctx.get("allowed_course_count")
    if n is None or n == "":
        return None
    try:
        x = int(n)
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def allowed_intro_term1_options(ctx: dict) -> tuple[list[str], Optional[int]]:
    """برمی‌گرداند: (کدهای مجاز، حداکثر تعداد انتخاب)."""
    kind = resolve_admission_kind(ctx)
    if kind == "single_course":
        return (["theory_1"], 1)
    if kind in ("conditional_therapy", "full_admission"):
        cap = _parse_allowed_count(ctx)
        return (list(INTRO_TERM1_COURSE_CODES), cap if cap is not None else 5)
    return (list(INTRO_TERM1_COURSE_CODES), 5)


def validate_intro_term1_selected_courses(ctx: object, selected: list[str]) -> tuple[bool, Optional[str]]:
    data = StateMachineEngine._as_mapping(ctx)
    codes = [c for c in selected if c]
    if not codes:
        return False, "حداقل یک درس باید انتخاب شود."
    allowed, max_select = allowed_intro_term1_options(data)
    allowed_set = set(allowed)
    unknown = [c for c in codes if c not in allowed_set]
    if unknown:
        labels = [INTRO_TERM1_COURSE_LABELS_FA.get(c, c) for c in unknown]
        return False, f"درس(های) غیرمجاز برای این نوع پذیرش: {', '.join(labels)}"
    if len(set(codes)) != len(codes):
        return False, "هر درس فقط یک‌بار قابل انتخاب است."
    if max_select is not None and len(codes) > max_select:
        return False, f"حداکثر {max_select} درس برای این پذیرش مجاز است."
    return True, None


def course_selection_config(process_code: str) -> Optional[dict[str, Any]]:
    if process_code == "introductory_course_registration":
        return {
            "field_name": INTRO_REG_COURSE_FIELD,
            "form_state": INTRO_REG_COURSE_STATE,
            "editable_states": INTRO_REG_EDITABLE_STATES,
            "catalog": "intro_term1",
        }
    if process_code == "intro_second_semester_registration":
        return {
            "field_name": INTRO_TERM2_COURSE_FIELD,
            "form_state": INTRO_TERM2_COURSE_STATE,
            "editable_states": INTRO_TERM2_EDITABLE_STATES,
            "catalog": "intro_term2_freeform",
        }
    return None


def validate_selected_courses_for_process(
    process_code: str,
    ctx: object,
    selected: list[str],
) -> tuple[bool, Optional[str]]:
    cfg = course_selection_config(process_code)
    if not cfg:
        return False, "این فرایند از ویرایش دروس توسط اپراتور پشتیبانی نمی‌شود."
    if cfg["catalog"] == "intro_term1":
        return validate_intro_term1_selected_courses(ctx, selected)
    codes = [c for c in selected if c]
    if not codes:
        return False, "حداقل یک درس باید انتخاب شود."
    data = StateMachineEngine._as_mapping(ctx)
    kind = resolve_admission_kind(data)
    if kind == "single_course":
        if len(codes) != 1:
            return False, "دانشجوی تک‌درس فقط یک درس مجاز دارد."
        if codes[0] != "theory_2":
            return False, "دانشجوی تک‌درس ترم دوم فقط مجاز به «تئوری روانکاوی ۲» است."
    return True, None
