"""ثبت فرم‌های مرحله توسط دانشجو در context_data نمونهٔ فرایند + قفل/باز کردن ویرایش."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.engine import StateMachineEngine
from app.services.forms.condition import field_visible as _unified_visible
from app.services.forms.validate import validate_table_field

# کلیدهای رزرو در ProcessInstance.context_data (با __ تا با payload معمول تداخل نکند)
CTX_SUBMITTED = "__student_forms_submitted_states"
CTX_EDIT_UNLOCK = "__student_forms_edit_unlock"
# پس از رد جزئی مدارک: نام فیلدهایی که دانشجو باید دوباره بارگذاری کند
CTX_DOCUMENTS_RESUBMIT_FIELDS = "__documents_resubmit_fields"
CTX_DOCUMENT_FIELD_REJECTION_NOTES = "__document_field_rejection_notes"
CTX_DOCUMENT_FIELD_LABELS_FA = "__document_field_labels_fa"
# پس از تأیید موفق OTP مرحله (قبل از register) — جلوگیری از مصرف دوبارهٔ کد
CTX_STEP_OTP_VERIFIED_STATE = "__step_otp_verified_state"
CTX_STEP_OTP_VERIFIED_AT = "__step_otp_verified_at"


def context_has_step_otp_verified(
    context_data: Optional[dict],
    state_code: Optional[str] = None,
) -> bool:
    """آیا OTP مرحله قبلاً روی سرور تأیید شده است؟

    پس از ثبت موفق فرم، فلگ ماندگار ``step_otp_verified`` در context می‌ماند
    (حتی اگر وضعیت از documents_upload به documents_incomplete عوض شود).
    فلگ موقت ``__step_otp_verified_state`` فقط فاصلهٔ verify تا register را پوشش می‌دهد.
    """
    ctx = context_data or {}
    if ctx.get("step_otp_verified") is True:
        return True
    stamped = ctx.get(CTX_STEP_OTP_VERIFIED_STATE)
    if not stamped or not isinstance(stamped, str):
        return False
    if not state_code:
        return True
    return stamped == state_code


def stamp_step_otp_verified(context_data: Optional[dict], state_code: str) -> dict:
    """ثبت فلگ سروری تأیید OTP برای وضعیت فعلی."""
    ctx = dict(context_data or {})
    ctx[CTX_STEP_OTP_VERIFIED_STATE] = state_code
    ctx[CTX_STEP_OTP_VERIFIED_AT] = datetime.now(timezone.utc).isoformat()
    return ctx


def clear_step_otp_verified_flags(context_data: Optional[dict]) -> dict:
    """پاک کردن فلگ‌های موقت OTP پس از ثبت موفق فرم."""
    ctx = dict(context_data or {})
    ctx.pop(CTX_STEP_OTP_VERIFIED_STATE, None)
    ctx.pop(CTX_STEP_OTP_VERIFIED_AT, None)
    return ctx


def process_state_requires_step_otp(process_code: str, state_code: str) -> bool:
    """وضعیت‌هایی که قبل از register باید OTP مرحله تأیید شده باشد."""
    if process_code == "upgrade_to_ta" and state_code == "commitment_signature":
        return True
    if process_code == "introductory_course_registration" and state_code in (
        "documents_upload",
        "documents_incomplete",
    ):
        return True
    return False

# فرم روش پرداخت تا قبل از پرداخت موفق باید قابل تغییر بماند
PAYMENT_METHOD_EDITABLE_STATES = frozenset(
    {
        "payment",
        "payment_method",
        "payment_choice",
        "payment_processing",
    }
)


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


def _field_required(field: dict, values: dict) -> bool:
    from app.services.forms.condition import field_required as _unified_required

    return _unified_required(field, values or {})


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
                t_early = field.get("type") or "text"
                is_rules_gate = t_early == "checkbox" and bool(field.get("rules_link_href"))
                # OTP فقط اگر هنوز در این پرونده تأیید نشده باشد در ثبت مجدد الزامی است
                if t_early == "step_otp" and context_has_step_otp_verified(context_data):
                    continue
                if t_early != "step_otp" and not is_rules_gate:
                    continue
            # فیلد نامرئی (show_if شیئی) را اعتبارسنجی نکن.
            if not _unified_visible(field, vals):
                continue
            if not _field_required(field, vals):
                continue
            if t == "checkbox":
                if field.get("required") and not vals.get(name):
                    missing.append(field.get("label_fa") or name)
                continue
            if t == "step_otp":
                if context_has_step_otp_verified(context_data):
                    continue
                if _is_empty(vals.get(name)):
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
            if t == "step_otp":
                # فقط پس از gate سروری در register نوشته می‌شود؛ از کلاینت به‌تنهایی اعتماد نمی‌شود
                keys.add("step_otp_verified")
    return keys


def operator_visible_forms(forms: list) -> list[dict]:
    """فرم‌های مرحله برای اپراتور؛ برخلاف دانشجو فرم محرمانه/غیردانشجو هم دیده می‌شود."""
    return [f for f in (forms or []) if isinstance(f, dict)]


def validate_operator_step_forms(
    forms: list,
    values: dict,
    context_data: Optional[dict] = None,
) -> tuple[bool, list[str]]:
    """اعتبارسنجی فرم‌های مرحله توسط اپراتور (بدون فیلتر دانشجو)."""
    missing: list[str] = []
    vals = values or {}
    for form in operator_visible_forms(forms):
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            t = field.get("type") or "text"
            name = field.get("name")
            if not name:
                continue
            if not _unified_visible(field, vals):
                continue
            if not _field_required(field, vals):
                continue
            if t == "checkbox":
                if field.get("required") and not vals.get(name):
                    missing.append(field.get("label_fa") or name)
                continue
            if t == "table":
                err = validate_table_field(field, vals.get(name))
                if err:
                    missing.append(err)
                continue
            if t in ("radio_list", "checkbox_list", "multi_select", "date_range_list"):
                raw = vals.get(name)
                if isinstance(raw, list):
                    if field.get("required") and len(raw) == 0:
                        missing.append(field.get("label_fa") or name)
                    continue
                if field.get("required") and (raw is None or (isinstance(raw, str) and str(raw).strip() == "")):
                    missing.append(field.get("label_fa") or name)
                continue
            if _is_empty(vals.get(name)):
                missing.append(field.get("label_fa") or name)
    return (len(missing) == 0, missing)


def collect_operator_allowed_keys(forms: list) -> set[str]:
    keys: set[str] = set()
    for form in operator_visible_forms(forms):
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


def sanitize_operator_form_values(forms: list, values: dict) -> dict:
    allowed = collect_operator_allowed_keys(forms)
    out: dict = {}
    for k, v in (values or {}).items():
        if k.startswith("__"):
            continue
        if k in allowed:
            out[k] = v
    return out


def documents_resubmit_field_names(context_data: Optional[object]) -> list[str]:
    """اگر خالی باشد، حالت عادی (همهٔ فیلدهای الزام)."""
    ctx = StateMachineEngine._as_mapping(context_data)
    raw = ctx.get(CTX_DOCUMENTS_RESUBMIT_FIELDS)
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if x]


def format_documents_deficiency_list(context_data: Optional[object]) -> str:
    """فهرست مدارک ردشده به‌همراه توضیح پذیرش — برای SMS و نمایش دانشجو."""
    ctx = StateMachineEngine._as_mapping(context_data)
    names = documents_resubmit_field_names(ctx)
    labels_raw = ctx.get(CTX_DOCUMENT_FIELD_LABELS_FA)
    labels = labels_raw if isinstance(labels_raw, dict) else {}
    notes_raw = ctx.get(CTX_DOCUMENT_FIELD_REJECTION_NOTES)
    notes = notes_raw if isinstance(notes_raw, dict) else {}
    lines: list[str] = []
    for i, fname in enumerate(names, 1):
        label = str(labels.get(fname) or labels.get(str(fname)) or fname)
        note = str(notes.get(fname) or notes.get(str(fname)) or "").strip()
        if note:
            lines.append(f"{i}- {label}: {note}")
        else:
            lines.append(f"{i}- {label}")
    return "\n".join(lines) if lines else "—"


def collect_partial_allowed_keys(forms: list, partial_names: set[str]) -> set[str]:
    keys: set[str] = set()
    for form in filter_forms_for_student(forms):
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            if not name:
                continue
            t = field.get("type") or "text"
            is_rules_gate = t == "checkbox" and bool(field.get("rules_link_href"))
            if name not in partial_names and t != "step_otp" and not is_rules_gate:
                continue
            keys.add(name)
            if t in ("radio_list", "checkbox_list"):
                keys.add(f"{name}_ack")
            if t == "step_otp":
                keys.add("step_otp_verified")
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
    # روش پرداخت: تا قبل از پرداخت درگاه، دانشجو بتواند نقدی/اقساط و تعداد را عوض کند
    if current_state in PAYMENT_METHOD_EDITABLE_STATES:
        unlock[current_state] = True
    else:
        unlock.pop(current_state, None)
    new_ctx[CTX_EDIT_UNLOCK] = unlock
    return new_ctx


def apply_unlock_to_context(ctx: object, state_code: str) -> dict:
    new_ctx = dict(StateMachineEngine._as_mapping(ctx))
    unlock = dict(StateMachineEngine._as_mapping(new_ctx.get(CTX_EDIT_UNLOCK)))
    unlock[state_code] = True
    new_ctx[CTX_EDIT_UNLOCK] = unlock
    return new_ctx


def apply_rollback_student_forms_to_context(
    ctx: object,
    target_state: str,
    from_state: Optional[str] = None,
) -> dict:
    """
    پس از بازگشت دستی به مرحلهٔ قبل: UI فرم همان مرحله برای دانشجو دوباره نمایش داده شود.

    - مرحلهٔ هدف: قفل ثبت قبلی برداشته می‌شود (ویرایش باز).
    - مرحلهٔ ترک‌شده با rollback: پرچم ثبت حذف می‌شود تا در ورود مجدد قفل نماند.
    """
    if not target_state:
        return dict(StateMachineEngine._as_mapping(ctx))
    new_ctx = apply_unlock_to_context(ctx, target_state)
    # اگر قبلاً ثبت شده بود، با unlock فرم قابل مشاهده/ویرایش می‌شود؛
    # submitted را نگه می‌داریم تا مقادیر قبلی در context بماند.
    if from_state and from_state != target_state:
        submitted = dict(StateMachineEngine._as_mapping(new_ctx.get(CTX_SUBMITTED)))
        if from_state in submitted:
            submitted.pop(from_state, None)
            new_ctx[CTX_SUBMITTED] = submitted
        unlock = dict(StateMachineEngine._as_mapping(new_ctx.get(CTX_EDIT_UNLOCK)))
        if from_state in unlock:
            unlock.pop(from_state, None)
            new_ctx[CTX_EDIT_UNLOCK] = unlock
    return new_ctx


def apply_reopen_student_step_forms_to_context(
    ctx: object,
    state_code: str,
    *,
    clear_keys: Optional[list[str]] = None,
    clear_submitted: bool = True,
) -> dict:
    """
    پس از رد/بازگشت فرایندی (مثلاً therapist_declined): فرم همان مرحله دوباره برای دانشجو باز شود.

    - قفل UI برداشته می‌شود (edit unlock).
    - به‌طور پیش‌فرض پرچم ثبت همان مرحله پاک می‌شود تا مثل اولین ورود باشد.
    - clear_keys: کلیدهای context که باید پاک شوند (مثلاً therapist_id / slot_ids).
    """
    if not state_code:
        return dict(StateMachineEngine._as_mapping(ctx))
    new_ctx = apply_unlock_to_context(ctx, state_code)
    if clear_submitted:
        submitted = dict(StateMachineEngine._as_mapping(new_ctx.get(CTX_SUBMITTED)))
        if state_code in submitted:
            submitted.pop(state_code, None)
            new_ctx[CTX_SUBMITTED] = submitted
    for key in clear_keys or []:
        name = str(key).strip()
        if name and not name.startswith("__"):
            new_ctx.pop(name, None)
    return new_ctx


def is_state_locked_for_student(
    context_data: Optional[dict],
    state_code: Optional[str],
) -> bool:
    """اگر برای این مرحله ثبت شده و باز بودن ویرایش فعال نباشد → فرم مخفی."""
    if not state_code:
        return False
    if state_code in PAYMENT_METHOD_EDITABLE_STATES:
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
