"""
یکپارچگی گراف متادیتا: stateهای یال‌ها و کدهای قانون روی ترنزیشن‌ها.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.processes.test_all_processes_level_a_smoke import _process_json_paths


def _all_rule_codes() -> set[str]:
    path = Path(__file__).resolve().parent.parent.parent / "metadata" / "rules" / "all_rules.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["code"] for r in data if isinstance(r, dict) and r.get("code")}


def test_transitions_reference_existing_states():
    for process_file in _process_json_paths():
        data = json.loads(process_file.read_text(encoding="utf-8"))
        states = {s["code"] for s in data.get("states") or [] if s.get("code")}
        for t in data.get("transitions") or []:
            f, to = t.get("from"), t.get("to")
            assert f in states, f"{process_file.name}: from={f!r} not in states"
            assert to in states, f"{process_file.name}: to={to!r} not in states"


def test_transition_conditions_reference_known_rules():
    codes = _all_rule_codes()
    for process_file in _process_json_paths():
        data = json.loads(process_file.read_text(encoding="utf-8"))
        for t in data.get("transitions") or []:
            for c in t.get("conditions") or []:
                assert c in codes, f"{process_file.name}: unknown rule {c!r}"
