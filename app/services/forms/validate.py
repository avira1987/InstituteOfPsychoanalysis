"""اعتبارسنجی پاسخ‌های فرم یکپارچه از روی schema_json + فیلتر نقش."""

from __future__ import annotations

import re
from typing import Any, Optional

from app.services.forms.condition import field_visible, field_required


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, dict):
        # فیلد فایل (multipart یا base64)
        if "file_name" in v or "url" in v or "content_base64" in v:
            return not (v.get("file_name") or v.get("url") or v.get("content_base64"))
        return len(v) == 0
    if isinstance(v, (list, tuple)):
        return len(v) == 0
    return False


def _norm_role(r: Optional[str]) -> str:
    return (r or "").strip().lower()


def filter_schema_for_role(schema: dict, role: Optional[str]) -> dict:
    """فیلدهای محرمانه/محدود به نقش را برای نقش جاری حذف می‌کند."""
    if not isinstance(schema, dict):
        return {"fields": []}
    role_n = _norm_role(role)
    out_fields = []
    for f in schema.get("fields") or []:
        if not isinstance(f, dict):
            continue
        if role_n == "student" and f.get("confidential"):
            continue
        visible_to = f.get("visible_to")
        if isinstance(visible_to, list) and visible_to:
            allowed = {_norm_role(x) for x in visible_to}
            if role_n and role_n not in allowed:
                continue
        out_fields.append(f)
    merged = dict(schema)
    merged["fields"] = out_fields
    return merged


def collect_allowed_keys(schema: dict) -> set[str]:
    """کلیدهای مجاز برای ذخیره (شامل کلیدهای کمکی _ack)."""
    keys: set[str] = set()
    for f in (schema or {}).get("fields") or []:
        if not isinstance(f, dict):
            continue
        name = f.get("name")
        if not name:
            continue
        keys.add(name)
        if (f.get("type") or "").lower() in ("radio_list", "checkbox_list"):
            keys.add(f"{name}_ack")
    return keys


def _check_validation_rules(field: dict, val: Any) -> Optional[str]:
    """قواعد min/max/min_len/max_len/pattern/max_selection. خطا یا None."""
    rules = field.get("validation")
    if not isinstance(rules, dict):
        # سازگاری: min/max مستقیماً روی فیلد
        rules = {}
        if "min" in field:
            rules["min"] = field["min"]
        if "max" in field:
            rules["max"] = field["max"]
        if not rules:
            return None
    label = field.get("label_fa") or field.get("name")

    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if rules.get("min") is not None and val < rules["min"]:
            return f"{label}: حداقل {rules['min']}"
        if rules.get("max") is not None and val > rules["max"]:
            return f"{label}: حداکثر {rules['max']}"
    if isinstance(val, str):
        if rules.get("min_len") is not None and len(val.strip()) < rules["min_len"]:
            return f"{label}: حداقل {rules['min_len']} نویسه"
        if rules.get("max_len") is not None and len(val) > rules["max_len"]:
            return f"{label}: حداکثر {rules['max_len']} نویسه"
        pattern = rules.get("pattern")
        if pattern and not re.fullmatch(pattern, val):
            return f"{label}: قالب نامعتبر"
    if isinstance(val, list) and rules.get("max_selection") is not None:
        if len(val) > rules["max_selection"]:
            return f"{label}: حداکثر {rules['max_selection']} انتخاب"
    return None


def validate_answers(
    schema: dict,
    answers: dict | None,
    role: Optional[str] = None,
    allowed_field_names: Optional[set[str]] = None,
) -> tuple[bool, list[str]]:
    """
    schema: { "fields": [ { name, type, required, show_if, required_if, validation, ... } ] }
    role: برای فیلتر فیلدهای محرمانه/نقش‌محور پیش از اعتبارسنجی.
    allowed_field_names: در حالت اصلاح جزئی (مثلاً نقص مدارک) فقط همین فیلدها بررسی شوند.
    """
    answers = answers or {}
    src = filter_schema_for_role(schema, role) if role else schema
    fields = src.get("fields") if isinstance(src, dict) else None
    if not isinstance(fields, list):
        return False, ["schema_json.fields نامعتبر است"]

    missing: list[str] = []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = field.get("name")
        if not name:
            continue
        if allowed_field_names is not None and name not in allowed_field_names:
            continue
        if not field_visible(field, answers):
            continue
        ftype = (field.get("type") or "text").lower()
        val = answers.get(name)

        if field_required(field, answers):
            if ftype == "checkbox":
                if not val:
                    missing.append(field.get("label_fa") or name)
                    continue
            elif ftype in ("radio_list", "checkbox_list"):
                ack = answers.get(f"{name}_ack")
                if isinstance(val, list):
                    if len(val) == 0 and not ack:
                        missing.append(field.get("label_fa") or name)
                        continue
                elif _is_empty(val) and not ack:
                    missing.append(field.get("label_fa") or name)
                    continue
            elif _is_empty(val):
                missing.append(field.get("label_fa") or name)
                continue

        if not _is_empty(val):
            err = _check_validation_rules(field, val)
            if err:
                missing.append(err)

    return (len(missing) == 0, missing)
