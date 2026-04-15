"""ثبت فرم‌های مرحله توسط دانشجو در context_data نمونهٔ فرایند + قفل/باز کردن ویرایش."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.engine import StateMachineEngine

# کلیدهای رزرو در ProcessInstance.context_data (با __ تا با payload معمول تداخل نکند)
CTX_SUBMITTED = "__student_forms_submitted_states"
CTX_EDIT_UNLOCK = "__student_forms_edit_unlock"
# پس از رد جزئی مدارک: نام فیلدهایی که دانشجو باید دوباره بارگذاری کند
CTX_DOCUMENTS_RESUBMIT_FIELDS = "__documents_resubmit_fields"


def filter_forms_for_student(forms: list) -> list[dict]:
    """هم‌تراز filterFormsForStudent در فرانت."""
    out: list[dict] = []
    for f in forms or []:
        if not isinstance(f, dict):
            continue
        if f.get("confidential"):
            continue
        vis = f.get("visible_to")
        if isinstance(vis, list) and vis and "student" not in vis:
            continue
        out.append(f)
    return out


def _field_required(field: dict, _values: dict) -> bool:
    if field.get("required_when"):
        return False
    return bool(field.get("required"))


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, dict):
        if v.get("file_name") is not None or v.get("url") is not None:
            return not (v.get("file_name") or v.get("url"))
    return False


def validate_student_step_forms(
    forms: list,
    values: dict,
    context_data: Optional[dict] = None,
) -> tuple[bool, list[str]]:
    """هم‌تراز validateStepForms در admin-ui."""
    missing: list[str] = []
    filtered = filter_forms_for_student(forms)
    vals = values or {}
    partial = documents_resubmit_field_names(context_data)
    partial_set = set(partial) if partial else None
    for form in filtered:
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            t = field.get("type") or "text"
            name = field.get("name")
            if not name:
                continue
            if partial_set is not None and name not in partial_set:
                continue
            if not _field_required(field, vals):
                continue
            if t == "checkbox":
                if field.get("required") and not vals.get(name):
                    missing.append(field.get("label_fa") or name)
                continue
            if t in ("radio_list", "checkbox_list"):
                raw = vals.get(name)
                ack = vals.get(f"{name}_ack")
                if isinstance(raw, list):
                    if field.get("required") and len(raw) == 0 and not ack:
                        missing.append(field.get("label_fa") or name)
                    continue
                if field.get("required") and not ack and (raw is None or (isinstance(raw, str) and str(raw).strip() == "")):
                    missing.append(field.get("label_fa") or name)
                continue
            if _is_empty(vals.get(name)):
                missing.append(field.get("label_fa") or name)
    return (len(missing) == 0, missing)


def collect_allowed_value_keys(forms: list) -> set[str]:
    """کلیدهایی که دانشجو مجاز است در payload ثبت کند."""
    keys: set[str] = set()
    for form in filter_forms_for_student(forms):
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            if not name:
                continue
            keys.add(name)
            t = field.get("type") or "text"
            if t in ("radio_list", "checkbox_list"):
                keys.add(f"{name}_ack")
    return keys


def documents_resubmit_field_names(context_data: Optional[object]) -> list[str]:
    """اگر خالی باشد، حالت عادی (همهٔ فیلدهای الزام)."""
    ctx = StateMachineEngine._as_mapping(context_data)
    raw = ctx.get(CTX_DOCUMENTS_RESUBMIT_FIELDS)
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if x]


def collect_partial_allowed_keys(forms: list, partial_names: set[str]) -> set[str]:
    keys: set[str] = set()
    for form in filter_forms_for_student(forms):
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            if not name or name not in partial_names:
                continue
            keys.add(name)
            t = field.get("type") or "text"
            if t in ("radio_list", "checkbox_list"):
                keys.add(f"{name}_ack")
    return keys


def sanitize_form_values(forms: list, values: dict, context_data: Optional[dict] = None) -> dict:
    partial = documents_resubmit_field_names(context_data)
    if partial:
        allowed = collect_partial_allowed_keys(forms, set(partial))
    else:
        allowed = collect_allowed_value_keys(forms)
    out: dict = {}
    for k, v in (values or {}).items():
        if k.startswith("__"):
            continue
        if k in allowed:
            out[k] = v
    return out


def apply_register_to_context(
    ctx: object,
    current_state: str,
    sanitized_values: dict,
) -> dict:
    """ادغام مقادیر فرم، ثبت زمان، و برداشتن باز بودن ویرایش برای همین مرحله."""
    # JSONB گاهی رشتهٔ JSON است؛ dict(r) مستقیم روی str خطا می‌دهد (۵۰۰ در ثبت فرم مرحله).
    new_ctx = dict(StateMachineEngine._as_mapping(ctx))
    for k, v in sanitized_values.items():
        new_ctx[k] = v
    submitted = dict(StateMachineEngine._as_mapping(new_ctx.get(CTX_SUBMITTED)))
    submitted[current_state] = datetime.now(timezone.utc).isoformat()
    new_ctx[CTX_SUBMITTED] = submitted
    unlock = dict(StateMachineEngine._as_mapping(new_ctx.get(CTX_EDIT_UNLOCK)))
    unlock.pop(current_state, None)
    new_ctx[CTX_EDIT_UNLOCK] = unlock
    return new_ctx


def apply_unlock_to_context(ctx: object, state_code: str) -> dict:
    new_ctx = dict(StateMachineEngine._as_mapping(ctx))
    unlock = dict(StateMachineEngine._as_mapping(new_ctx.get(CTX_EDIT_UNLOCK)))
    unlock[state_code] = True
    new_ctx[CTX_EDIT_UNLOCK] = unlock
    return new_ctx


def is_state_locked_for_student(
    context_data: Optional[dict],
    state_code: Optional[str],
) -> bool:
    """اگر برای این مرحله ثبت شده و باز بودن ویرایش فعال نباشد → فرم مخفی."""
    if not state_code:
        return False
    # JSONB / نمونهٔ قدیمی: context_data گاهی رشتهٔ JSON است.
    ctx = StateMachineEngine._as_mapping(context_data)
    if not ctx:
        return False
    submitted = ctx.get(CTX_SUBMITTED) or {}
    unlock = ctx.get(CTX_EDIT_UNLOCK) or {}
    if not submitted.get(state_code):
        return False
    return not bool(unlock.get(state_code))
