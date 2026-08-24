# -*- coding: utf-8 -*-
"""Detect Persian text that lost connecting letters (U+0640–U+06FF stripping)."""
from __future__ import annotations

import re
from typing import Any, Iterator

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_CONNECTING_RE = re.compile(r"[\u0641-\u06FF]")
_REH_PREFIX = re.compile(r"^رح[\s\u200c]")
_MARHALE_PREFIX = re.compile(
    r"^مرحله\s*[0-9۰-۹]+\s*(?:\(SOP(?:\s+به‌روز)?\))?\.\s*"
)

_DEFINITE_MARKERS = (
    "گاساز",
    "اطاعرسا",
    "درت تغرات",
    "درا آزش",
    "SOP برز",
    "سخ برز",
    "دراگر",
    "سپرازر",
    "ارزاب",
    "تصحح",
    "غبت",
    "پشرفت",
    "فارت",
    "جس۱۸",
    "جس۱۷",
    "جس١٨",
    "جس١٧",
    "شارشگر",
    "ارکتگ",
    "پشس",
    "سپر ف تف",
)

# Substrings that also occur inside healthy words need lookaround.
_STRIPPED_RES = (
    re.compile(r"(?<!ن)ظارت"),  # نظارت
    re.compile(r"(?<!م)شارکت"),  # مشارکت
    re.compile(r"جبرا(?!ن)"),  # جبرانی
    re.compile(r"در داخ(?!ل)"),
)

FA_STRING_KEYS = frozenset({"name_fa", "description_fa", "description"})


def arabic_letters(text: str) -> list[str]:
    return _ARABIC_RE.findall(text or "")


def connecting_ratio(text: str, min_letters: int = 24) -> float | None:
    letters = arabic_letters(text)
    if len(letters) < min_letters:
        return None
    conn = sum(1 for ch in letters if _CONNECTING_RE.fullmatch(ch))
    return conn / len(letters)


def _ratio_target(text: str) -> str:
    """Ignore a restored «مرحله N (SOP).» prefix so a healthy header cannot mask a stripped body."""
    stripped = text.strip()
    body = _MARHALE_PREFIX.sub("", stripped, count=1)
    if len(arabic_letters(body)) >= 24:
        return body
    return stripped


def is_stripped_persian(text: str | None) -> bool:
    """True when Arabic/Persian letters are present but connecting letters were dropped."""
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if any(marker in text for marker in _DEFINITE_MARKERS):
        return True
    if any(rx.search(text) for rx in _STRIPPED_RES):
        return True
    if _REH_PREFIX.match(stripped):
        return True
    ratio = connecting_ratio(_ratio_target(stripped))
    return ratio is not None and ratio < 0.16


def try_prefix_repair(text: str) -> str:
    """Fix recoverable tokens; does not restore dropped letters in the body."""
    t = text or ""
    t = re.sub(r"^رح[\s\u200c]+", "مرحله ", t.strip())
    t = t.replace("SOP برز", "SOP به‌روز")
    return t


def iter_fa_strings(
    obj: Any,
    keys: frozenset[str] = FA_STRING_KEYS,
    path: str = "",
) -> Iterator[tuple[str, str]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{path}.{k}" if path else str(k)
            if k in keys and isinstance(v, str):
                yield child, v
            else:
                yield from iter_fa_strings(v, keys, child)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from iter_fa_strings(item, keys, f"{path}[{i}]")
