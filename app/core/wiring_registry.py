"""Declarative inter-process wiring registry.

Loads `metadata/wiring/process_links.json` and answers "which chaining links
apply to this process/state/trigger?". Holds no business logic and imports no
services, so it stays safe to import from `app.core.engine`.

A *link* is one directed edge in the inter-process graph. Matching is purely
declarative; the behaviour lives in a named handler registered in
`app.core.chaining`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

WIRING_DIR = Path(__file__).parent.parent.parent / "metadata" / "wiring"
PROCESS_LINKS_FILE = WIRING_DIR / "process_links.json"

PHASE_ON_START = "on_start"
PHASE_AFTER_TRANSITION = "after_transition"
VALID_PHASES = frozenset({PHASE_ON_START, PHASE_AFTER_TRANSITION})

VALID_MODES = frozenset({"start", "advance", "complete", "propagate", "sync"})


class WiringConfigError(Exception):
    """Raised when process_links.json is malformed."""


def _as_frozenset(value: Any, field_name: str, link_id: str) -> Optional[frozenset[str]]:
    """Normalise a string / list-of-strings matcher into a frozenset."""
    if value is None:
        return None
    if isinstance(value, str):
        return frozenset({value})
    if isinstance(value, (list, tuple, set)):
        items = [str(v) for v in value]
        if not items:
            raise WiringConfigError(f"link '{link_id}': '{field_name}' must not be an empty list")
        return frozenset(items)
    raise WiringConfigError(
        f"link '{link_id}': '{field_name}' must be a string or list of strings, got {type(value).__name__}"
    )


@dataclass(frozen=True)
class ProcessLink:
    """One declarative edge of the inter-process graph."""

    id: str
    phase: str
    handler: str
    order: int

    from_process: frozenset[str]
    from_state: Optional[frozenset[str]] = None
    to_state: Optional[frozenset[str]] = None
    trigger: Optional[frozenset[str]] = None
    requires_completed: bool = False

    # Documentation / graph-analysis only; does not affect matching.
    to_process: tuple[str, ...] = field(default_factory=tuple)
    mode: Optional[str] = None
    description: str = ""

    # Execution semantics.
    flush_before: bool = False
    refetch_instance: bool = False
    enabled: bool = True

    def matches(
        self,
        *,
        process_code: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        trigger_event: Optional[str] = None,
        is_completed: bool = False,
    ) -> bool:
        if not self.enabled:
            return False
        if process_code not in self.from_process:
            return False
        if self.from_state is not None and from_state not in self.from_state:
            return False
        if self.to_state is not None and to_state not in self.to_state:
            return False
        if self.trigger is not None and trigger_event not in self.trigger:
            return False
        if self.requires_completed and not is_completed:
            return False
        return True


def _parse_link(raw: Any, order: int) -> ProcessLink:
    if not isinstance(raw, dict):
        raise WiringConfigError(f"link #{order} must be an object, got {type(raw).__name__}")

    link_id = str(raw.get("id") or "").strip()
    if not link_id:
        raise WiringConfigError(f"link #{order} is missing 'id'")

    phase = str(raw.get("phase") or "").strip()
    if phase not in VALID_PHASES:
        raise WiringConfigError(
            f"link '{link_id}': 'phase' must be one of {sorted(VALID_PHASES)}, got '{phase}'"
        )

    handler = str(raw.get("handler") or "").strip()
    if not handler:
        raise WiringConfigError(f"link '{link_id}' is missing 'handler'")

    from_process = _as_frozenset(raw.get("from_process"), "from_process", link_id)
    if not from_process:
        raise WiringConfigError(f"link '{link_id}' is missing 'from_process'")

    mode = raw.get("mode")
    if mode is not None and str(mode) not in VALID_MODES:
        raise WiringConfigError(
            f"link '{link_id}': 'mode' must be one of {sorted(VALID_MODES)}, got '{mode}'"
        )

    to_process_raw = raw.get("to_process")
    if to_process_raw is None:
        to_process: tuple[str, ...] = ()
    elif isinstance(to_process_raw, str):
        to_process = (to_process_raw,)
    else:
        to_process = tuple(str(v) for v in to_process_raw)

    if phase == PHASE_ON_START and any(
        raw.get(k) is not None for k in ("from_state", "to_state", "trigger")
    ):
        raise WiringConfigError(
            f"link '{link_id}': 'from_state'/'to_state'/'trigger' are meaningless for phase 'on_start'"
        )

    return ProcessLink(
        id=link_id,
        phase=phase,
        handler=handler,
        order=order,
        from_process=from_process,
        from_state=_as_frozenset(raw.get("from_state"), "from_state", link_id),
        to_state=_as_frozenset(raw.get("to_state"), "to_state", link_id),
        trigger=_as_frozenset(raw.get("trigger"), "trigger", link_id),
        requires_completed=bool(raw.get("requires_completed", False)),
        to_process=to_process,
        mode=str(mode) if mode is not None else None,
        description=str(raw.get("description") or ""),
        flush_before=bool(raw.get("flush_before", False)),
        refetch_instance=bool(raw.get("refetch_instance", False)),
        enabled=bool(raw.get("enabled", True)),
    )


class WiringRegistry:
    """Indexed, immutable view over the declarative process links."""

    def __init__(self, links: Iterable[ProcessLink]):
        self._links: tuple[ProcessLink, ...] = tuple(links)
        by_phase_process: dict[tuple[str, str], list[ProcessLink]] = {}
        for link in self._links:
            for code in link.from_process:
                by_phase_process.setdefault((link.phase, code), []).append(link)
        for bucket in by_phase_process.values():
            bucket.sort(key=lambda item: item.order)
        self._by_phase_process = by_phase_process

    @property
    def links(self) -> tuple[ProcessLink, ...]:
        return self._links

    def link_ids(self) -> set[str]:
        return {link.id for link in self._links}

    def handler_names(self) -> set[str]:
        return {link.handler for link in self._links}

    def links_for(
        self,
        *,
        phase: str,
        process_code: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        trigger_event: Optional[str] = None,
        is_completed: bool = False,
    ) -> list[ProcessLink]:
        """Ordered list of links that apply, cheap enough to call per transition."""
        candidates = self._by_phase_process.get((phase, process_code))
        if not candidates:
            return []
        return [
            link
            for link in candidates
            if link.matches(
                process_code=process_code,
                from_state=from_state,
                to_state=to_state,
                trigger_event=trigger_event,
                is_completed=is_completed,
            )
        ]

    def edges(self) -> list[tuple[str, str, ProcessLink]]:
        """(from_process, to_process, link) tuples for graph analysis and docs."""
        out: list[tuple[str, str, ProcessLink]] = []
        for link in self._links:
            for src in sorted(link.from_process):
                for dst in link.to_process:
                    out.append((src, dst, link))
        return out


def parse_links(payload: Any) -> list[ProcessLink]:
    """Validate a raw process_links payload and return parsed links."""
    if not isinstance(payload, dict):
        raise WiringConfigError("process_links.json must contain a JSON object")
    raw_links = payload.get("links")
    if not isinstance(raw_links, list):
        raise WiringConfigError("process_links.json must contain a 'links' array")

    links = [_parse_link(raw, order=index) for index, raw in enumerate(raw_links)]

    seen: set[str] = set()
    for link in links:
        if link.id in seen:
            raise WiringConfigError(f"duplicate link id '{link.id}'")
        seen.add(link.id)
    return links


def load_registry(path: Optional[Path] = None) -> WiringRegistry:
    """Read and validate the wiring file. Missing file yields an empty registry."""
    target = path or PROCESS_LINKS_FILE
    if not target.exists():
        logger.warning("process wiring file not found: %s (inter-process chaining disabled)", target)
        return WiringRegistry([])
    with target.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return WiringRegistry(parse_links(payload))


_registry: Optional[WiringRegistry] = None


def get_registry() -> WiringRegistry:
    """Process-wide singleton, loaded lazily on first use."""
    global _registry
    if _registry is None:
        _registry = load_registry()
    return _registry


def reset_registry() -> None:
    """Drop the cached registry so the next access reloads from disk (tests)."""
    global _registry
    _registry = None
