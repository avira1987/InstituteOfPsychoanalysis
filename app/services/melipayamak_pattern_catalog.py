"""بارگذاری کاتالوگ پترن‌های ملی‌پیامک از metadata/melipayamak_patterns.json.

خروجی اسکریپت‌های:
  - scripts/import_melipayamak_patterns_xlsx.py (اکسل پنل)
  - scripts/sync_melipayamak_patterns.py (SOAP؛ در صورت دسترس بودن API)

استفادهٔ ارسال واقعی همچنان با sms_gateway و پارامتر text با جداکنندهٔ ; مطابق مستند پترن است؛
این ماژول فقط مرجع بدنهٔ متن و عنوان برای نقشه‌برداری رویداد → bodyId را فراهم می‌کند.

فهرست سناریوهای فرایند در برابر همین پترن‌ها و «کمبود پترن»:
  metadata/sms_pattern_coverage_matrix.json
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

_DEFAULT_JSON = PROJECT_ROOT / "metadata" / "melipayamak_patterns.json"


def _catalog_path() -> Path:
    override = (os.environ.get("MELIPAYAMAK_PATTERNS_JSON") or "").strip()
    return Path(override).expanduser().resolve() if override else _DEFAULT_JSON


def _coerce_pattern_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = raw.get("patterns")
    if not isinstance(patterns, list):
        return []
    out: list[dict[str, Any]] = []
    for row in patterns:
        if not isinstance(row, dict):
            continue
        bid = row.get("bodyId")
        if bid is None:
            bid = row.get("body_id")
        try:
            ib = int(str(bid).strip())
        except (TypeError, ValueError):
            continue
        if ib <= 0:
            continue
        merged = dict(row)
        merged["bodyId"] = ib
        out.append(merged)
    out.sort(key=lambda x: x["bodyId"])
    return out


@lru_cache(maxsize=1)
def load_melipayamak_pattern_catalog() -> dict[str, Any]:
    """کل JSON را با کلیدهای استاندارد برمی‌گرداند؛ در صورت نبود فایل، ساختار خالی."""
    path = _catalog_path()
    if not path.is_file():
        return {"source": None, "patterns": [], "count": 0, "catalogPath": str(path)}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"source": None, "patterns": [], "count": 0, "catalogPath": str(path)}
    if not isinstance(raw, dict):
        return {"source": None, "patterns": [], "count": 0, "catalogPath": str(path)}
    patterns = _coerce_pattern_rows(raw)
    extra = {k: v for k, v in raw.items() if k not in ("patterns", "count", "source")}
    return {
        "source": raw.get("source"),
        "patterns": patterns,
        "count": len(patterns),
        "catalogPath": str(path),
        **extra,
    }


def get_pattern_by_body_id(body_id: int) -> dict[str, Any] | None:
    bid = int(body_id)
    for p in load_melipayamak_pattern_catalog()["patterns"]:
        if int(p["bodyId"]) == bid:
            return p
    return None


def clear_pattern_catalog_cache() -> None:
    load_melipayamak_pattern_catalog.cache_clear()
