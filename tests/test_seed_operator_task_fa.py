"""Tests for seed_operator_task_fa idempotency and operator state coverage."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.seed_operator_task_fa import EXCLUDE_ROLES, normalize_assigned_role, seed_file

ROOT = Path(__file__).resolve().parents[1]
PROCESSES_DIR = ROOT / "metadata" / "processes"
MAP_PATH = ROOT / "metadata" / "portal_role_assigned_role_map.json"


def _load_typo_map() -> dict[str, str]:
    with MAP_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return dict(raw.get("normalize_assigned_role_typo") or {})


def _operator_states_missing_task() -> list[tuple[str, str]]:
    typo = _load_typo_map()
    missing: list[tuple[str, str]] = []
    for path in sorted(PROCESSES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for state in data.get("states") or []:
            role = normalize_assigned_role(state.get("assigned_role"), typo)
            if not role or role in EXCLUDE_ROLES:
                continue
            task = (state.get("metadata") or {}).get("operator_task_fa") or ""
            if not str(task).strip():
                missing.append((path.name, state.get("code") or ""))
    return missing


def test_all_operator_states_have_operator_task_fa():
    missing = _operator_states_missing_task()
    assert missing == [], f"missing operator_task_fa: {missing[:10]}"


def test_seed_is_idempotent_on_real_metadata():
    typo = _load_typo_map()
    total_changed = 0
    for path in sorted(PROCESSES_DIR.glob("*.json")):
        n_changed, _ = seed_file(path, typo, dry_run=True)
        total_changed += n_changed
    assert total_changed == 0, f"seed would modify {total_changed} fields — not idempotent"


def test_seed_does_not_overwrite_existing_text(tmp_path):
    typo = _load_typo_map()
    sample = {
        "process": {"code": "sample_proc"},
        "states": [
            {
                "code": "staff_step",
                "name_fa": "گام کارمند",
                "assigned_role": "admissions_officer",
                "metadata": {
                    "operator_task_fa": "متن دستی",
                    "operator_short_fa": "گام کارمند",
                },
            }
        ],
    }
    path = tmp_path / "sample_proc.json"
    path.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    changed, _ = seed_file(path, typo, dry_run=False)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["states"][0]["metadata"]["operator_task_fa"] == "متن دستی"
    assert changed == 0
