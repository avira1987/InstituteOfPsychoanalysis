"""دسترسی مبتنی بر نقش به دادهٔ ثبت‌شدهٔ فرایند (مشاهده / ویرایش) — متادیتا-محور.

این ماژول لایهٔ عمومی «مشاهده + ویرایش/به‌روزرسانی دادهٔ ثبت‌شدهٔ هر فرایند» را
از روی متادیتای فرم‌ها (`metadata/processes/*.json`) تغذیه می‌کند و برای همهٔ
فرایندها بدون کد اختصاصی کار می‌کند.

قراردادهای اختیاری روی هر **فرم** یا **فیلد**:
- ``visible_to``: فهرست نقش‌هایی که می‌توانند ببینند (اگر خالی → همه؛ به‌جز
  فرم/فیلد ``confidential`` که برای دانشجو پنهان است).
- ``confidential``: اگر ``true`` باشد، برای نقش دانشجو پنهان می‌شود.
- ``editable_by``: فهرست نقش‌هایی که اجازه دارند پس از ثبت، مقدار را
  ویرایش/به‌روزرسانی کنند.

سطح فیلد بر سطح فرم اولویت دارد (override). یعنی اگر فیلد ``editable_by`` یا
``visible_to`` خودش را داشته باشد، همان ملاک است؛ در غیر این صورت مقدار فرم
به‌ارث می‌رسد.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from app.core.engine import StateMachineEngine

# کلید لاگ ممیزی ویرایش‌ها در context_data
CTX_DATA_EDIT_LOG = "__data_edit_log"


def _norm(role: Optional[str]) -> str:
    return (role or "").strip().lower()


def _norm_list(values: Optional[Iterable[Any]]) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return [_norm(str(v)) for v in values if str(v).strip()]


# نقش پورتال ↔ assigned_role متادیتا (آماده‌سازی ترم و نقش‌های مرتبط)
_EDITABLE_ROLE_ALIASES: dict[str, frozenset[str]] = {
    "deputy_education": frozenset({"deputy_education", "deputy_education_director"}),
    "deputy_education_director": frozenset({"deputy_education_director", "deputy_education"}),
    "course_committee": frozenset(
        {"course_committee", "course_committee_executive", "course_committee_scientific", "scientific_officer_course_committee"}
    ),
    "course_committee_executive": frozenset({"course_committee_executive", "course_committee"}),
    "scientific_officer_course_committee": frozenset(
        {"scientific_officer_course_committee", "course_committee_scientific", "course_committee"}
    ),
    "course_committee_scientific": frozenset(
        {"course_committee_scientific", "scientific_officer_course_committee", "course_committee"}
    ),
    "admissions_officer": frozenset({"admissions_officer", "admission_officer", "staff"}),
    "admission_officer": frozenset({"admission_officer", "admissions_officer", "staff"}),
}


def _role_matches_editable_list(role: str, allowed: list[str]) -> bool:
    r = _norm(role)
    allowed_norm = set(allowed)
    if r in allowed_norm:
        return True
    for code in allowed_norm:
        if r in _EDITABLE_ROLE_ALIASES.get(code, frozenset()):
            return True
    for alias in _EDITABLE_ROLE_ALIASES.get(r, frozenset()):
        if alias in allowed_norm:
            return True
    return False


def _inherit(field: dict, form: dict, key: str):
    """مقدار سطح فیلد را برگردان؛ اگر نبود، مقدار سطح فرم."""
    if key in field and field.get(key) is not None:
        return field.get(key)
    return form.get(key)


def field_visible_to_role(form: dict, field: dict, role: str) -> bool:
    r = _norm(role)
    confidential = bool(_inherit(field, form, "confidential"))
    if r == "student" and confidential:
        return False
    visible_to = _inherit(field, form, "visible_to")
    allowed = _norm_list(visible_to)
    if allowed and r and r not in allowed:
        return False
    return True


def field_editable_by_role(form: dict, field: dict, role: str) -> bool:
    """فیلد فقط وقتی قابل ویرایش است که برای نقش مرئی باشد و نقش در editable_by باشد."""
    if not field_visible_to_role(form, field, role):
        return False
    editable_by = _inherit(field, form, "editable_by")
    allowed = _norm_list(editable_by)
    if not allowed:
        return False
    return _role_matches_editable_list(role, allowed)


def _iter_fields(forms: list):
    for form in forms or []:
        if not isinstance(form, dict):
            continue
        for field in form.get("fields") or []:
            if isinstance(field, dict) and field.get("name"):
                yield form, field


def visible_field_names(forms: list, role: str) -> set[str]:
    return {
        field["name"]
        for form, field in _iter_fields(forms)
        if field_visible_to_role(form, field, role)
    }


def editable_field_names(forms: list, role: str) -> set[str]:
    return {
        field["name"]
        for form, field in _iter_fields(forms)
        if field_editable_by_role(form, field, role)
    }


def visible_forms_for_role(forms: list, role: str) -> list[dict]:
    """ساختار فرم‌ها را با فقط فیلدهای مرئی برای نقش برمی‌گرداند و روی هر فیلد
    پرچم ``__editable`` می‌گذارد تا UI بداند کدام فیلد قابل ویرایش است."""
    out: list[dict] = []
    for form in forms or []:
        if not isinstance(form, dict):
            continue
        vis_fields = []
        for field in form.get("fields") or []:
            if not isinstance(field, dict) or not field.get("name"):
                continue
            if not field_visible_to_role(form, field, role):
                continue
            enriched = dict(field)
            enriched["__editable"] = field_editable_by_role(form, field, role)
            vis_fields.append(enriched)
        if not vis_fields:
            continue
        form_copy = {k: v for k, v in form.items() if k != "fields"}
        form_copy["fields"] = vis_fields
        out.append(form_copy)
    return out


def extract_values(context_data: Any, names: Iterable[str]) -> dict:
    ctx = StateMachineEngine._as_mapping(context_data)
    out: dict = {}
    for n in names:
        if n in ctx:
            out[n] = ctx[n]
    return out


def sanitize_editable_payload(forms: list, role: str, field_values: dict) -> dict:
    """فقط فیلدهایی را نگه می‌دارد که نقش اجازهٔ ویرایش آن‌ها را دارد."""
    allowed = editable_field_names(forms, role)
    out: dict = {}
    for k, v in (field_values or {}).items():
        if isinstance(k, str) and not k.startswith("__") and k in allowed:
            out[k] = v
    return out


def apply_data_update_to_context(
    context_data: Any,
    sanitized_values: dict,
    *,
    actor_id: Optional[str],
    actor_role: str,
    reason: Optional[str] = None,
) -> dict:
    """مقادیر را در context_data ادغام و یک رکورد ممیزی اضافه می‌کند."""
    from datetime import datetime, timezone

    new_ctx = dict(StateMachineEngine._as_mapping(context_data))
    changed: list[str] = []
    for k, v in sanitized_values.items():
        if new_ctx.get(k) != v:
            changed.append(k)
        new_ctx[k] = v

    if changed:
        log = list(StateMachineEngine._as_mapping(new_ctx).get(CTX_DATA_EDIT_LOG) or [])
        if not isinstance(log, list):
            log = []
        log.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "actor_id": str(actor_id) if actor_id else None,
                "actor_role": _norm(actor_role),
                "fields": changed,
                "reason": (reason or "").strip() or None,
            }
        )
        new_ctx[CTX_DATA_EDIT_LOG] = log
    return new_ctx
