"""Assert every action type referenced in process metadata has a real handler.

Without this guard an unknown ``action.type`` degrades silently: `_dispatch`
logs a warning and returns ``no_handler_for_<type>``, so the transition looks
successful while its side effect never happened. That is exactly how
``start_sub_process`` left four course-completion processes unable to complete.

Usage:
    python -m scripts.validate_action_coverage          # exit 1 on any gap
    python -m scripts.validate_action_coverage --json   # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSES_DIR = REPO_ROOT / "metadata" / "processes"

# `_dispatch` routes any unregistered `record_*` type to the generic artifact
# handler, so those are legitimately handled without a registry entry.
GENERIC_PREFIXES = ("record_",)


def known_action_types() -> set[str]:
    from app.services.action_handler import ActionHandler

    return set(ActionHandler._registry)


def _iter_actions(process: dict) -> Iterable[tuple[str, dict]]:
    """Yield (location, action) for every action in a process definition."""
    for transition in process.get("transitions") or []:
        if not isinstance(transition, dict):
            continue
        location = (
            f"{transition.get('from', '?')} --{transition.get('trigger', '?')}--> "
            f"{transition.get('to', '?')}"
        )
        for action in transition.get("actions") or []:
            if isinstance(action, dict):
                yield location, action

    for state in process.get("states") or []:
        if not isinstance(state, dict):
            continue
        for key in ("on_entry_actions", "on_exit_actions"):
            for action in state.get(key) or []:
                if isinstance(action, dict):
                    yield f"state {state.get('code', '?')}.{key}", action


def collect_usages(processes_dir: Path = PROCESSES_DIR) -> dict[str, list[str]]:
    """action type -> list of "process_code: location" strings."""
    usages: dict[str, list[str]] = defaultdict(list)
    for path in sorted(processes_dir.glob("*.json")):
        try:
            process = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path.name} is not valid JSON: {exc}") from exc
        for location, action in _iter_actions(process):
            action_type = action.get("type")
            if not action_type:
                usages["<missing type>"].append(f"{path.stem}: {location}")
                continue
            usages[str(action_type)].append(f"{path.stem}: {location}")
    return dict(usages)


def is_handled(action_type: str, registry: set[str]) -> bool:
    if action_type in registry:
        return True
    return any(action_type.startswith(prefix) for prefix in GENERIC_PREFIXES)


def find_unhandled(processes_dir: Path = PROCESSES_DIR) -> dict[str, list[str]]:
    """action type -> usage locations, for types with no handler at all."""
    registry = known_action_types()
    return {
        action_type: locations
        for action_type, locations in collect_usages(processes_dir).items()
        if not is_handled(action_type, registry)
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    usages = collect_usages()
    registry = known_action_types()
    unhandled = {t: locs for t, locs in usages.items() if not is_handled(t, registry)}

    if args.json:
        print(
            json.dumps(
                {
                    "registry_size": len(registry),
                    "distinct_action_types": len(usages),
                    "unhandled": {t: sorted(set(locs)) for t, locs in sorted(unhandled.items())},
                    "ok": not unhandled,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if unhandled else 0

    print(f"registered handlers      : {len(registry)}")
    print(f"action types in metadata : {len(usages)}")

    if not unhandled:
        print("OK - every action type in metadata has a handler.")
        return 0

    print(f"\nFAIL - {len(unhandled)} action type(s) have no handler:\n")
    for action_type in sorted(unhandled):
        locations = sorted(set(unhandled[action_type]))
        print(f"  {action_type}  ({len(locations)} usage(s))")
        for location in locations[:10]:
            print(f"      {location}")
        if len(locations) > 10:
            print(f"      ... and {len(locations) - 10} more")
    print(
        "\nFix by registering the type in ActionHandler._registry, or correct the "
        "spelling in metadata/processes/*.json."
    )
    return 1


if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))
    raise SystemExit(main())
