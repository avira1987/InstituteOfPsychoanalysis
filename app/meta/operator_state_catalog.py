"""
کاتالوگ مراحل فرایند (state) به ازای هر assigned_role در metadata/processes —
برای راهنمای «همهٔ مراحلی که نقش شما در متادیتا مسئول آن است» در پنل.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROCESSES_DIR = _REPO_ROOT / "metadata" / "processes"
_MAP_PATH = _REPO_ROOT / "metadata" / "portal_role_assigned_role_map.json"


@lru_cache(maxsize=1)
def _load_portal_role_map_raw() -> dict[str, Any]:
    if not _MAP_PATH.is_file():
        return {"schema_version": 0, "portal_roles": {}, "normalize_assigned_role_typo": {}, "exclude_from_operator_catalog": []}
    with _MAP_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def normalize_assigned_role(code: str | None) -> str:
    if not code or not str(code).strip():
        return ""
    c = str(code).strip()
    typo = _load_portal_role_map_raw().get("normalize_assigned_role_typo") or {}
    return str(typo.get(c, c))


def _exclude_roles() -> frozenset[str]:
    raw = _load_portal_role_map_raw().get("exclude_from_operator_catalog") or []
    base = {"student", "applicant", "system"}
    return frozenset(base | {str(x).strip() for x in raw if x})


@lru_cache(maxsize=1)
def _catalog_by_assigned_role() -> dict[str, list[dict[str, Any]]]:
    """assigned_role نرمال‌شده → لیست ورودی‌های مرحله."""
    out: dict[str, list[dict[str, Any]]] = {}
    exclude = _exclude_roles()

    if not _PROCESSES_DIR.is_dir():
        return out

    for path in sorted(_PROCESSES_DIR.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        proc = data.get("process") or {}
        process_code = (proc.get("code") or path.stem) or ""
        process_name_fa = proc.get("name_fa") or process_code
        for st in data.get("states") or []:
            ar = normalize_assigned_role(st.get("assigned_role"))
            if not ar or ar in exclude:
                continue
            state_code = (st.get("code") or "").strip()
            state_name_fa = (st.get("name_fa") or state_code).strip()
            row = {
                "process_code": process_code,
                "process_name_fa": process_name_fa,
                "state_code": state_code,
                "state_name_fa": state_name_fa,
                "assigned_role": ar,
            }
            out.setdefault(ar, []).append(row)

    for key in list(out.keys()):
        out[key].sort(key=lambda r: (r.get("process_name_fa") or "", r.get("state_code") or ""))
    return out


def all_operator_assigned_role_codes() -> list[str]:
    """همهٔ کدهای assigned_role اپراتوری که در فرایندها ظاهر شده‌اند."""
    cat = _catalog_by_assigned_role()
    exclude = _exclude_roles()
    codes = sorted({k for k in cat if k and k not in exclude})
    return codes


def resolve_portal_role_to_assigned_roles(portal_role: str) -> list[str] | None:
    """
    None یعنی «همهٔ نقش‌های اپراتوری» (مدیر).
    لیست خالی یعنی هیچ نگاشت stateای نیست (مثلاً مالی).
    """
    raw = _load_portal_role_map_raw()
    from app.core.user_roles import canonical_portal_role

    lookup = canonical_portal_role(portal_role) or (portal_role or "").strip()
    pr = (raw.get("portal_roles") or {}).get(lookup)
    if not pr and lookup != portal_role:
        pr = (raw.get("portal_roles") or {}).get(portal_role)
    if not pr:
        return []
    if pr.get("include_all_operator_assigned_roles"):
        return None
    arr = pr.get("assigned_roles")
    if not isinstance(arr, list):
        return []
    return [normalize_assigned_role(x) for x in arr if x and str(x).strip()]


def get_state_catalog_for_portal_role(portal_role: str) -> list[dict[str, Any]]:
    """
    فهرست یکتا از مراحل مرتبط با نقش پورتال؛ هر آیتم برای ادغام در action-queue.
    """
    target_roles = resolve_portal_role_to_assigned_roles(portal_role)
    cat = _catalog_by_assigned_role()
    if target_roles is None:
        target_roles = all_operator_assigned_role_codes()

    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, Any]] = []
    for ar in target_roles:
        for row in cat.get(ar, []):
            pc = row.get("process_code") or ""
            sc = row.get("state_code") or ""
            key = (pc, sc)
            if key in seen:
                continue
            seen.add(key)
            merged.append(dict(row))

    merged.sort(key=lambda r: (r.get("process_name_fa") or "", r.get("state_code") or ""))
    return merged


def portal_role_can_act_on_assigned_role(portal_role: str, state_assigned_role: str | None) -> bool:
    """آیا نقش پورتال می‌تواند روی مرحله‌ای با assigned_role داده‌شده اقدام کند؟"""
    if not portal_role or not state_assigned_role:
        return False
    allowed = resolve_portal_role_to_assigned_roles(portal_role)
    if allowed is None:
        return True
    normalized = normalize_assigned_role(state_assigned_role)
    return normalized in allowed


def invalidate_caches() -> None:
    """برای تست یا بارگذاری مجدد فرایندها."""
    _load_portal_role_map_raw.cache_clear()
    _catalog_by_assigned_role.cache_clear()
