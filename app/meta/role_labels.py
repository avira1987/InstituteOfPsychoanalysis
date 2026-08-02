"""برچسب فارسی یکپارچه نقش‌ها — منبع: metadata/role_labels_fa.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LABELS_PATH = _REPO_ROOT / "metadata" / "role_labels_fa.json"


@lru_cache(maxsize=1)
def _load_role_labels_doc() -> dict:
    if not _LABELS_PATH.is_file():
        return {"labels": {}, "typo_aliases": {}}
    with _LABELS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def role_labels_map() -> dict[str, str]:
    doc = _load_role_labels_doc()
    return dict(doc.get("labels") or {})


@lru_cache(maxsize=1)
def role_typo_aliases() -> dict[str, str]:
    doc = _load_role_labels_doc()
    return dict(doc.get("typo_aliases") or {})


def normalize_role_code(code: str | None) -> str:
    if not code:
        return ""
    raw = str(code).strip().lower()
    if not raw:
        return ""
    aliases = role_typo_aliases()
    return aliases.get(raw, raw)


def role_label_fa_only(code: str | None) -> str:
    normalized = normalize_role_code(code)
    if not normalized:
        return "—"
    return role_labels_map().get(normalized, "نقش نامشخص")


def label_role_fa(code: str | None, *, include_code: bool = True) -> str:
    """
    برچسب نمایشی: «نام فارسی (کد)».
    اگر ترجمه نبود: «نقش نامشخص (کد)».
    """
    normalized = normalize_role_code(code)
    if not normalized:
        return "—"
    fa = role_labels_map().get(normalized, "نقش نامشخص")
    if not include_code:
        return fa
    return f"{fa} ({normalized})"


def format_role_forbidden_message(actor_role: str | None, *required_roles: str) -> str:
    """پیام فارسی برای خطای ۴۰۳ — نقش فعلی مجاز نیست."""
    current = role_label_fa_only(actor_role)
    required_labels = [role_label_fa_only(r) for r in required_roles if r]
    if not required_labels:
        return f"نقش «{current}» مجاز نیست."
    return f"نقش «{current}» مجاز نیست. نقش‌های مجاز: {'، '.join(required_labels)}"
