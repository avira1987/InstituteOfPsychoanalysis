"""Hub extra_data flags for slice-1 (violation / fee / referral)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HUB_VIOLATION = "violation_registration"

VIOLATION_PRESENT_BLOCK_REASON_FA = (
    "ثبت حضور برای این دانشجو به دلیل تعلیق انضباطی مسدود است."
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def set_is_suspended(extra: dict[str, Any], value: bool) -> dict[str, Any]:
    extra["is_suspended"] = bool(value)
    extra["is_suspended_at"] = _utcnow_iso()
    return extra


def apply_violation_present_block(extra: dict[str, Any], instance: Any) -> dict[str, Any]:
    extra["class_present_blocked"] = {
        "active": True,
        "instance_id": str(getattr(instance, "id", "") or ""),
        "process_code": HUB_VIOLATION,
        "locked_at": _utcnow_iso(),
        "reason_fa": VIOLATION_PRESENT_BLOCK_REASON_FA,
        "source": HUB_VIOLATION,
    }
    return extra


def clear_violation_present_block(extra: dict[str, Any]) -> dict[str, Any]:
    flag = extra.get("class_present_blocked")
    if isinstance(flag, dict) and flag.get("source") == HUB_VIOLATION:
        extra.pop("class_present_blocked", None)
    elif isinstance(flag, dict) and flag.get("process_code") == HUB_VIOLATION:
        extra.pop("class_present_blocked", None)
    return extra


def apply_violation_suspension(extra: dict[str, Any], *, immediate: bool) -> dict[str, Any]:
    set_is_suspended(extra, True)
    if immediate:
        extra["class_access_blocked"] = True
    return extra


def clear_violation_suspension(extra: dict[str, Any]) -> dict[str, Any]:
    set_is_suspended(extra, False)
    extra["class_access_blocked"] = False
    gates = dict(extra.get("gates") or {})
    gates["next_term_registration_blocked"] = False
    gates["next_term_registration_blocked_at"] = _utcnow_iso()
    extra["gates"] = gates
    clear_violation_present_block(extra)
    extra["violation_suspension_lifted_at"] = _utcnow_iso()
    return extra
