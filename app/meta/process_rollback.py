"""Shared rollback target resolution for process instances."""

from __future__ import annotations

from typing import Any, Optional, Protocol, Sequence


class HistoryEntryLike(Protocol):
    from_state_code: Optional[str]
    to_state_code: Optional[str]
    trigger_event: Optional[str]


def resolve_rollback_target_from_history(
    history: Sequence[HistoryEntryLike | dict[str, Any]],
    current_state: str,
) -> Optional[str]:
    """
    Find the operational predecessor of ``current_state``.

    Skips ``manual_rollback`` entries so chained rollbacks walk back through
    real workflow steps instead of undoing the previous rollback hop.
    """
    if not current_state or not history:
        return None

    for entry in reversed(history):
        if isinstance(entry, dict):
            to_state = entry.get("to_state") or entry.get("to_state_code")
            from_state = entry.get("from_state") or entry.get("from_state_code")
            trigger_event = entry.get("trigger_event")
        else:
            to_state = entry.to_state_code
            from_state = entry.from_state_code
            trigger_event = entry.trigger_event

        if to_state != current_state:
            continue
        if trigger_event == "manual_rollback":
            continue
        if not from_state:
            return None
        return from_state

    return None
