"""Minimal HTML sanitizer for blog content (no external deps)."""

from __future__ import annotations

import re

_SCRIPT_RE = re.compile(r"<\s*(script|iframe|object|embed|link|meta|base|form)[^>]*>.*?<\s*/\s*\1\s*>", re.I | re.S)
_SCRIPT_OPEN_RE = re.compile(r"<\s*(script|iframe|object|embed|link|meta|base|form)[^>]*/?\s*>", re.I)
_EVENT_ATTR_RE = re.compile(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_JS_URL_RE = re.compile(r"(href|src)\s*=\s*([\"'])\s*javascript:[^\2]*\2", re.I)
_DATA_URL_RE = re.compile(r"(href|src)\s*=\s*([\"'])\s*data:text/html[^\"']*\2", re.I)


def sanitize_blog_html(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw)
    text = _SCRIPT_RE.sub("", text)
    text = _SCRIPT_OPEN_RE.sub("", text)
    text = _EVENT_ATTR_RE.sub("", text)
    text = _JS_URL_RE.sub("", text)
    text = _DATA_URL_RE.sub("", text)
    return text
