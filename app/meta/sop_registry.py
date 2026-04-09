"""شمارهٔ مرحلهٔ SOP هر فرایند از روی metadata/process_registry/INDEX.json."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

def _resolve_index_path() -> Optional[Path]:
    """مسیر INDEX.json؛ چند ریشهٔ رایج (uvicorn از ریشهٔ مخزن یا یک پوشه بالاتر)."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "metadata" / "process_registry" / "INDEX.json",
        here.parents[3] / "metadata" / "process_registry" / "INDEX.json",
        Path.cwd() / "metadata" / "process_registry" / "INDEX.json",
        Path.cwd().parent / "metadata" / "process_registry" / "INDEX.json",
    ]
    seen: set[Path] = set()
    for c in candidates:
        try:
            r = c.resolve()
        except OSError:
            continue
        if r in seen:
            continue
        seen.add(r)
        if r.is_file():
            return r
    return None

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# فرایندهایی که در notes هنوز «مرحله N» ندارند؛ ترتیب با سند SOP و جایگاه در INDEX هم‌راستا است.
_FALLBACK_SOP_ORDER: dict[str, int] = {
    "educational_leave": 1,
    "start_therapy": 2,
    "extra_session": 3,
    "session_payment": 4,
    "attendance_tracking": 5,
    "fee_determination": 6,
    "therapy_completion": 7,
    "therapy_session_increase": 8,
    "therapy_session_reduction": 9,
    "therapy_early_termination": 10,
    "specialized_commission_review": 11,
    "committees_review": 12,
    "therapist_session_cancellation": 13,
    "unannounced_absence_reaction": 14,
}


def _parse_marhale_from_notes(notes: Optional[str]) -> Optional[int]:
    if not notes or not isinstance(notes, str):
        return None
    m = re.search(r"مرحله\s*([۰-۹\d]+)", notes)
    if not m:
        return None
    raw = m.group(1).translate(_PERSIAN_DIGITS)
    try:
        return int(raw)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _load_index_process_entries() -> tuple[dict[str, int], dict[str, Optional[int]]]:
    """برمی‌گرداند (نگاشت صریح sop_order از INDEX، نگاشت نهایی code -> sop_order)."""
    explicit: dict[str, int] = {}
    index_path = _resolve_index_path()
    if not index_path:
        return explicit, {}
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("processes") or []
    merged: dict[str, Optional[int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = row.get("code")
        if not code:
            continue
        if isinstance(row.get("sop_order"), int):
            explicit[code] = row["sop_order"]
            merged[code] = row["sop_order"]
            continue
        parsed = _parse_marhale_from_notes(row.get("notes"))
        if parsed is not None:
            merged[code] = parsed
        elif code in _FALLBACK_SOP_ORDER:
            merged[code] = _FALLBACK_SOP_ORDER[code]
        else:
            merged[code] = None
    return explicit, merged


def get_sop_order_for_process_code(code: str) -> Optional[int]:
    """شمارهٔ مرحلهٔ SOP برای کد فرایند، در صورت نبود None."""
    _, merged = _load_index_process_entries()
    if code in merged and merged[code] is not None:
        return merged[code]
    if code in _FALLBACK_SOP_ORDER:
        return _FALLBACK_SOP_ORDER[code]
    return None


def get_all_sop_orders() -> dict[str, Optional[int]]:
    """همهٔ کدهای ثبت‌شده در INDEX به‌همراه شماره (یا None)."""
    _, merged = _load_index_process_entries()
    return dict(merged)


def clear_sop_order_cache() -> None:
    _load_index_process_entries.cache_clear()
