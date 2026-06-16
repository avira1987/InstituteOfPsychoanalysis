"""اعتبارسنجی پاسخ‌های فرم داینامیک — اکنون به سامانهٔ یکپارچهٔ forms واگذار می‌شود.

نگهداری برای سازگاری عقب‌رو؛ منطق اصلی در app/services/forms/validate.py است.
"""

from __future__ import annotations

from typing import Optional

from app.services.forms.validate import validate_answers


def validate_dynamic_answers(
    schema: dict, answers: dict | None, role: Optional[str] = None
) -> tuple[bool, list[str]]:
    """واسط سازگار قدیمی — به validate_answers یکپارچه واگذار می‌کند."""
    return validate_answers(schema if isinstance(schema, dict) else {}, answers, role=role)


def merge_dynamic_into_context(existing: Optional[dict], key: str, payload: dict) -> dict:
    """کلید namespaced در context_data فرایند."""
    out = dict(existing or {})
    slot = f"__dynamic_form__{key}"
    cur = out.get(slot)
    if isinstance(cur, dict):
        merged = {**cur, **payload}
    else:
        merged = dict(payload)
    out[slot] = merged
    return out
