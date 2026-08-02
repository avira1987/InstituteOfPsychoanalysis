"""
کاتالوگ فرایندهای قابل نمایش در سایدبار — یک آیتم به ازای هر process_code
که نقش پورتال روی حداقل یک مرحلهٔ آن مجاز به اقدام است.
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.meta.operator_state_catalog import (
    get_state_catalog_for_portal_role,
    invalidate_caches as invalidate_operator_caches,
    normalize_assigned_role,
)
from app.meta.process_nav_order import process_nav_sort_key, sort_process_nav_rows

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROCESSES_DIR = _REPO_ROOT / "metadata" / "processes"

_STUDENT_ROLES = frozenset({"student", "applicant"})


def process_nav_path(process_code: str) -> str:
    code = (process_code or "").strip()
    return f"/panel/process-nav/{code}"


def _enrich_nav_row(row: dict[str, Any]) -> dict[str, Any]:
    """برچسب سطح کاربرد (۰=اصلی … ۳=سایر) برای دسته‌بندی سایدبار."""
    code = (row.get("process_code") or "").strip()
    label = (row.get("label_fa") or row.get("process_name_fa") or "").strip()
    nav_tier = process_nav_sort_key(code, label)[0]
    return {**row, "nav_tier": nav_tier}


@lru_cache(maxsize=1)
def _student_process_catalog() -> list[dict[str, Any]]:
    """فرایندهایی که دانشجو/متقاضی روی حداقل یک state مسئول است."""
    if not _PROCESSES_DIR.is_dir():
        return []

    by_code: dict[str, dict[str, Any]] = {}
    role_counts: dict[str, Counter[str]] = {}

    for path in sorted(_PROCESSES_DIR.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        proc = data.get("process") or {}
        process_code = (proc.get("code") or path.stem) or ""
        if not process_code:
            continue
        process_name_fa = (proc.get("name_fa") or process_code).strip()
        for st in data.get("states") or []:
            ar = normalize_assigned_role(st.get("assigned_role"))
            if ar not in _STUDENT_ROLES:
                continue
            if process_code not in by_code:
                by_code[process_code] = {
                    "process_code": process_code,
                    "label_fa": process_name_fa,
                    "process_name_fa": process_name_fa,
                }
                role_counts[process_code] = Counter()
            role_counts[process_code][ar] += 1

    out: list[dict[str, Any]] = []
    for code, row in by_code.items():
        primary = (role_counts[code].most_common(1) or [("student", 0)])[0][0]
        out.append(
            _enrich_nav_row(
                {
                    **row,
                    "primary_assigned_role": primary,
                    "path": process_nav_path(code),
                }
            )
        )
    return sort_process_nav_rows(out)


def _operator_process_catalog(portal_role: str) -> list[dict[str, Any]]:
    """گروه‌بندی state catalog به یک ردیف به ازای process_code."""
    if portal_role == "finance":
        return []

    rows = get_state_catalog_for_portal_role(portal_role)
    by_code: dict[str, dict[str, Any]] = {}
    role_counts: dict[str, Counter[str]] = {}

    for row in rows:
        code = (row.get("process_code") or "").strip()
        if not code:
            continue
        ar = normalize_assigned_role(row.get("assigned_role"))
        if code not in by_code:
            name = (row.get("process_name_fa") or code).strip()
            by_code[code] = {
                "process_code": code,
                "label_fa": name,
                "process_name_fa": name,
            }
            role_counts[code] = Counter()
        if ar:
            role_counts[code][ar] += 1

    out: list[dict[str, Any]] = []
    for code, row in by_code.items():
        primary = (role_counts[code].most_common(1) or [("", 0)])[0][0]
        out.append(
            _enrich_nav_row(
                {
                    **row,
                    "primary_assigned_role": primary,
                    "path": process_nav_path(code),
                }
            )
        )
    return sort_process_nav_rows(out)


def get_process_nav_catalog_for_portal_role(portal_role: str) -> list[dict[str, Any]]:
    """فهرست یکتای فرایندها برای سایدبار نقش داده‌شده."""
    role = (portal_role or "").strip().lower()
    if not role:
        return []
    if role == "student":
        return [dict(x) for x in _student_process_catalog()]
    return _operator_process_catalog(role)


def attach_pending_counts(
    catalog: list[dict[str, Any]],
    pending_by_process: dict[str, int],
) -> list[dict[str, Any]]:
    """شمارش کار منتظر را به هر آیتم کاتالوگ می‌چسباند."""
    out: list[dict[str, Any]] = []
    for row in catalog:
        code = (row.get("process_code") or "").strip().lower()
        out.append({**row, "pending_count": int(pending_by_process.get(code, 0))})
    return out


def invalidate_caches() -> None:
    invalidate_operator_caches()
    _student_process_catalog.cache_clear()
