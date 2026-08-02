#!/usr/bin/env python3
"""Aggregate flow-through API/UI test failures into gaps.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.flow_through.common import ENRICHED_MATRIX_PATH, GAPS_PATH, matrix_paths_for_track


def load_enriched_matrix(track: str | None = None) -> dict[str, Any]:
    _, path, _, _ = matrix_paths_for_track(track or "wave1")
    if not path.is_file():
        raise FileNotFoundError(f"Missing enriched matrix: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def gap_from_row(row: dict[str, Any], *, failed_at: str, layer: str, detail: str) -> dict[str, Any]:
    return {
        "step_id": row.get("step_id"),
        "process_code": row.get("process_code"),
        "state_code": row.get("state_code"),
        "required_role": row.get("required_role"),
        "portal_role": row.get("portal_role"),
        "trigger": row.get("trigger"),
        "to_state": row.get("to_state"),
        "failed_at": failed_at,
        "layer": layer,
        "detail": detail,
        "ui_layer": row.get("ui_layer"),
        "ui_component": row.get("ui_component"),
        "form_codes": row.get("form_codes"),
        "field_specs": row.get("field_specs"),
        "severity": "high",
    }


def build_gaps_from_pytest_json(pytest_path: Path, matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    data = json.loads(pytest_path.read_text(encoding="utf-8"))
    by_id = {r.get("step_id"): r for r in matrix_rows}
    gaps: list[dict[str, Any]] = []
    for test in data.get("tests") or []:
        nodeid = test.get("nodeid") or ""
        outcome = test.get("outcome")
        if outcome == "passed":
            continue
        # extract step id from parametrize bracket
        step_id = None
        if "[" in nodeid and "]" in nodeid:
            step_id = nodeid.split("[", 1)[1].rsplit("]", 1)[0]
        row = by_id.get(step_id) or {}
        detail = ""
        for call in test.get("call", {}).get("longrepr", "") if isinstance(test.get("call"), dict) else []:
            detail = str(call)
        if not detail and test.get("call"):
            detail = str(test["call"].get("crash", {}).get("message", ""))
        gaps.append(
            gap_from_row(
                row,
                failed_at="api_flow",
                layer="api",
                detail=detail or outcome or "failed",
            )
        )
    return gaps


def build_ui_surface_gaps(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps = []
    for row in matrix_rows:
        if row.get("ui_surface_ok") is False or row.get("ui_layer") == "MISSING":
            gaps.append(
                gap_from_row(
                    row,
                    failed_at="ui_surface",
                    layer="ui",
                    detail="No UI surface mapped for this step",
                )
            )
    return gaps


def main() -> int:
    ap = argparse.ArgumentParser(description="Build flow-through gaps report")
    ap.add_argument("--track", type=str, default=None)
    ap.add_argument("--pytest-json", type=Path, help="pytest --json-report output")
    ap.add_argument("--playwright-json", type=Path, help="Playwright JSON results")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    track = args.track or "wave1"
    _, _, gaps_path, _ = matrix_paths_for_track(track)
    out_path = args.out or gaps_path

    matrix = load_enriched_matrix(track)
    rows = matrix.get("rows") or []
    gaps: list[dict[str, Any]] = list(build_ui_surface_gaps(rows))

    if args.pytest_json and args.pytest_json.is_file():
        gaps.extend(build_gaps_from_pytest_json(args.pytest_json, rows))

    # Deduplicate by step_id + failed_at
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for g in gaps:
        key = (g.get("step_id") or "", g.get("failed_at") or "")
        if key in seen:
            continue
        seen.add(key)
        unique.append(g)

    report = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "gap_count": len(unique),
            "matrix_rows": len(rows),
        },
        "gaps": unique,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(unique)} gaps -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
