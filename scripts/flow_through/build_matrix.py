#!/usr/bin/env python3
"""Build flow-through matrix: human-action steps per process state."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.flow_through.common import (
    INTERVIEW_BOOK_TRIGGERS,
    MATRIX_PATH,
    field_spec,
    forms_for_state,
    load_portal_map,
    load_process_json,
    load_track_process_codes,
    load_wave_process_codes,
    matrix_paths_for_track,
    role_to_portal_role,
    state_by_code,
    terminal_states,
)


def build_rows_for_process(process_code: str, portal_data: dict[str, Any]) -> list[dict[str, Any]]:
    pj = load_process_json(process_code)
    states = state_by_code(pj)
    terminals = terminal_states(pj)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for tr in pj.get("transitions") or []:
        if not isinstance(tr, dict):
            continue
        required_role = (tr.get("required_role") or "system").strip()
        if required_role == "system":
            continue
        state_code = (tr.get("from") or "").strip()
        if not state_code or state_code in terminals:
            continue
        trigger = (tr.get("trigger") or "").strip()
        to_state = (tr.get("to") or "").strip()
        if not trigger:
            continue

        portal_role = role_to_portal_role(required_role, portal_data) or required_role
        key = (state_code, required_role, trigger)
        if key in seen:
            continue
        seen.add(key)

        st = states.get(state_code) or {}
        forms = forms_for_state(pj, state_code)
        field_specs: list[dict[str, Any]] = []
        form_codes: list[str] = []
        for form in forms:
            code = (form.get("code") or form.get("name") or "").strip()
            if code:
                form_codes.append(code)
            for field in form.get("fields") or []:
                if isinstance(field, dict) and field.get("name"):
                    field_specs.append(field_spec(field))

        rows.append(
            {
                "step_id": f"{process_code}/{state_code}@{portal_role}",
                "process_code": process_code,
                "process_name_fa": (pj.get("process") or {}).get("name_fa") or process_code,
                "state_code": state_code,
                "state_name_fa": st.get("name_fa") or state_code,
                "state_assigned_role": st.get("assigned_role") or "",
                "required_role": required_role,
                "portal_role": portal_role,
                "trigger": trigger,
                "to_state": to_state,
                "is_terminal_target": to_state in terminals,
                "form_codes": form_codes,
                "field_specs": field_specs,
                "has_forms": bool(forms),
                "action_type": "interview_book" if trigger in INTERVIEW_BOOK_TRIGGERS else "standard",
            }
        )

    rows.sort(key=lambda r: (r["process_code"], r["state_code"], r["required_role"], r["trigger"]))
    return rows


def build_matrix(
    *,
    wave: int | None = 1,
    track: str | None = None,
    process_codes: list[str] | None = None,
) -> dict[str, Any]:
    portal_data = load_portal_map()
    if process_codes:
        codes = list(process_codes)
        track_label = track or f"wave{wave}"
    elif track:
        codes = list(load_track_process_codes(track))
        track_label = track
    else:
        codes = list(load_wave_process_codes(wave or 1))
        track_label = f"wave{wave or 1}"
    all_rows: list[dict[str, Any]] = []
    per_process: dict[str, int] = {}

    for code in codes:
        try:
            rows = build_rows_for_process(code, portal_data)
        except FileNotFoundError:
            continue
        per_process[code] = len(rows)
        all_rows.extend(rows)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "wave": wave,
            "track": track_label,
            "process_count": len(per_process),
            "row_count": len(all_rows),
            "per_process": per_process,
        },
        "rows": all_rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build flow-through matrix from process metadata")
    ap.add_argument("--wave", type=int, default=None, help="Wave number (1=critical, 2=important)")
    ap.add_argument(
        "--track",
        type=str,
        default=None,
        help="Track name: wave1, wave2, or onboarding (ورود مرکز)",
    )
    ap.add_argument("--process", action="append", dest="processes", help="Limit to process code(s)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    track = args.track
    wave = args.wave if args.wave is not None else (1 if not track else None)
    if args.out is not None:
        out_path = args.out
    else:
        _, _, _, _ = matrix_paths_for_track(track or f"wave{wave or 1}")
        out_path = matrix_paths_for_track(track or f"wave{wave or 1}")[0]

    report = build_matrix(wave=wave, track=track, process_codes=args.processes)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {report['meta']['row_count']} rows for {report['meta']['process_count']} processes -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
