"""نگاشت کلید تمپلیت اعلان → bodyId + متغیرهای پترن (خط خدماتی / BaseServiceNumber).

منبع: metadata/sms_template_pattern_map.json — قابل بازتعریف با SMS_TEMPLATE_PATTERN_MAP_JSON.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

_DEFAULT_PATH = PROJECT_ROOT / "metadata" / "sms_template_pattern_map.json"

_SLOT_ALIASES: dict[str, tuple[str, ...]] = {
    "student_name": ("applicant_name", "full_name", "name"),
    "interview_date": ("date", "meeting_date"),
    "interview_time": ("time", "meeting_time"),
    "interview_link": ("meeting_link", "interview_location_or_link"),
    "interview_location": ("location_fa", "interview_location_or_link"),
    "interview_location_or_link": ("meeting_link", "location_fa"),
    "amount_rial": ("amount", "payment_amount_rial", "total_rial", "invoice_amount_rial"),
    "payer_name": ("student_name", "applicant_name", "full_name"),
    "portal_hint": ("course_name", "class_label"),
    "date": ("interview_date",),
    "time": ("interview_time",),
    "location_info": ("interview_location_or_link", "interview_location", "interview_link"),
}


def _map_path() -> Path:
    override = (os.environ.get("SMS_TEMPLATE_PATTERN_MAP_JSON") or "").strip()
    return Path(override).expanduser().resolve() if override else _DEFAULT_PATH


def _strip_problematic_separators(s: str) -> str:
    """جداکنندهٔ پترن در API نقطه‌ویرگول است؛ از شکستن پارامتر text جلوگیری می‌کنیم."""
    return (s or "").replace(";", "،").replace("\n", " ").strip()


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    path = _map_path()
    if not path.is_file():
        return {"mappings": {}, "slot_defaults": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"mappings": {}, "slot_defaults": {}}
    return raw if isinstance(raw, dict) else {"mappings": {}, "slot_defaults": {}}


def clear_sms_template_pattern_map_cache() -> None:
    _load_raw.cache_clear()


def _slot_value(ctx: dict[str, Any], key: str, defaults: dict[str, str]) -> str:
    v = ctx.get(key)
    if v is not None and str(v).strip():
        return _strip_problematic_separators(str(v))
    for alt in _SLOT_ALIASES.get(key, ()):
        v = ctx.get(alt)
        if v is not None and str(v).strip():
            return _strip_problematic_separators(str(v))
    d = defaults.get(key)
    if d is not None and str(d).strip():
        return _strip_problematic_separators(str(d))
    return ""


def resolve_sms_pattern_for_template(
    template_key: str | None,
    context: dict[str, Any] | None,
) -> tuple[int, str] | None:
    """اگر برای کلید تمپلیت نگاشت باشد، (bodyId, text) برای BaseServiceNumber برمی‌گرداند؛ وگرنه None."""
    if not template_key or not str(template_key).strip():
        return None
    key = str(template_key).strip()
    raw = _load_raw()
    mappings = raw.get("mappings")
    if not isinstance(mappings, dict):
        return None
    row = mappings.get(key)
    if not isinstance(row, dict):
        return None
    try:
        body_id = int(row.get("bodyId") or row.get("body_id") or 0)
    except (TypeError, ValueError):
        return None
    if body_id <= 0:
        return None
    slots = row.get("slots") or row.get("slot_keys")
    if not isinstance(slots, list) or not slots:
        return None
    defaults = raw.get("slot_defaults")
    defaults_map: dict[str, str] = {}
    if isinstance(defaults, dict):
        defaults_map = {str(k): str(v) for k, v in defaults.items()}
    row_def = row.get("slot_defaults")
    if isinstance(row_def, dict):
        defaults_map = {**defaults_map, **{str(k): str(v) for k, v in row_def.items()}}
    ctx = dict(context or {})
    parts: list[str] = []
    for sk in slots:
        sks = str(sk).strip()
        if not sks:
            parts.append("")
            continue
        parts.append(_slot_value(ctx, sks, defaults_map))
    text = ";".join(parts)
    if not any(str(p).strip() for p in parts):
        return None
    return body_id, text


def list_mapped_template_keys() -> list[str]:
    raw = _load_raw()
    m = raw.get("mappings")
    if not isinstance(m, dict):
        return []
    return sorted(m.keys())
