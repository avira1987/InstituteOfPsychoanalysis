"""کاتالوگ ویژگی‌های مثبت/منفی فرم ارزیابی مدرس — سوالات ۷ و ۸."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "metadata" / "instructor_student_trait_catalog.json"
)


@lru_cache(maxsize=1)
def _load_catalog_raw() -> dict[str, Any]:
    if not _CATALOG_PATH.is_file():
        return {"positive_traits": [], "negative_traits": []}
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def list_trait_options(kind: str) -> list[dict[str, str]]:
    """kind: positive | negative"""
    data = _load_catalog_raw()
    key = "positive_traits" if kind == "positive" else "negative_traits"
    items = data.get(key) or []
    out: list[dict[str, str]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        val = str(row.get("value") or "").strip()
        if not val:
            continue
        out.append({
            "value": val,
            "label_fa": str(row.get("label_fa") or val),
        })
    return out


def trait_label(kind: str, code: str) -> str:
    for opt in list_trait_options(kind):
        if opt["value"] == code:
            return opt["label_fa"]
    return code
