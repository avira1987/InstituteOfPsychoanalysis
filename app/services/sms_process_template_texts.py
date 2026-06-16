"""متن‌های پیامک تعریف‌شده در metadata فرایندها (template_text_fa) برای پاپ‌آپ و ارسال log."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_META_PROCESSES = Path(__file__).resolve().parents[2] / "metadata" / "processes"


@lru_cache(maxsize=1)
def process_sms_template_texts() -> dict[str, str]:
    """کلید template → متن فارسی از actions نوع notification/sms در JSON فرایندها."""
    out: dict[str, str] = {}
    if not _META_PROCESSES.is_dir():
        return out
    for path in sorted(_META_PROCESSES.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for tr in data.get("transitions") or []:
            for act in tr.get("actions") or []:
                if act.get("type") != "notification":
                    continue
                if (act.get("notification_type") or "sms").lower() != "sms":
                    continue
                key = (act.get("template") or "").strip()
                if not key:
                    continue
                text = (act.get("template_text_fa") or act.get("template_text") or "").strip()
                if text and key not in out:
                    out[key] = text
    return out


def get_process_sms_fallback(template_key: str) -> str | None:
    key = (template_key or "").strip()
    if not key:
        return None
    return process_sms_template_texts().get(key)
