# -*- coding: utf-8 -*-
"""Rebuild _process_map_summary.md and _process_map_extract.json from SOP/metadata."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "metadata" / "process_registry" / "INDEX.json"
META_DIR = ROOT / "metadata" / "processes"
REG_DIR = ROOT / "metadata" / "process_registry" / "processes"
SUMMARY_PATH = ROOT / "_process_map_summary.md"
EXTRACT_PATH = ROOT / "_process_map_extract.json"

ARTIFACT_NAMES = (
    "01_input.md",
    "02_flowchart.md",
    "03_output.json",
    "04_status.md",
    "SOP_document.txt",
    "SOP_flowchart.png",
)
MAX_WORKFLOW_LINES = 10

SECTIONS: list[tuple[str, callable]] = [
    ("Therapy lifecycle (SOP 2-17)", lambda n: n is not None and 2 <= n <= 17),
    ("Supervision lifecycle (SOP 18-28)", lambda n: n is not None and 18 <= n <= 28),
    ("Academic calendar and enrollment (SOP 29-42)", lambda n: n is not None and 29 <= n <= 42),
    ("TA and instructor track (SOP 43-57)", lambda n: n is not None and 43 <= n <= 57),
    ("Leave and return (SOP 1, 58-60)", lambda n: n == 1 or (n is not None and 58 <= n <= 60)),
    ("Course completion and graduation (SOP 61-75)", lambda n: n is not None and 61 <= n <= 75),
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry_artifacts(code: str) -> list[str]:
    folder = REG_DIR / code
    if not folder.is_dir():
        return []
    return [name for name in ARTIFACT_NAMES if (folder / name).exists()]


def _state_role(states: list[dict], code: str) -> str | None:
    for st in states:
        if st.get("code") == code:
            return st.get("assigned_role")
    return None


def _workflow_line(tr: dict, states: list[dict]) -> str:
    src = tr.get("from") or "?"
    dst = tr.get("to") or "?"
    trigger = tr.get("trigger") or ""
    role = tr.get("required_role") or _state_role(states, src) or ""
    conds = [c for c in (tr.get("conditions") or []) if c]
    line = f"{src} --({trigger})--> {dst}"
    if role:
        line += f" [{role}]"
    if conds:
        line += f" [{', '.join(conds)}]"
    return line


def _build_record(index_row: dict | None, code: str, *, extra_status: str | None = None) -> dict:
    meta_path = META_DIR / f"{code}.json"
    meta = _load_json(meta_path) if meta_path.exists() else {}
    proc = meta.get("process") or {}
    states = meta.get("states") or []
    transitions = meta.get("transitions") or []
    index_row = index_row or {}
    sop_order = index_row.get("sop_order")
    artifacts = _registry_artifacts(code)
    has_registry = (REG_DIR / code).is_dir()
    workflow_lines = [_workflow_line(tr, states) for tr in transitions]
    return {
        "code": code,
        "name_fa": index_row.get("name_fa") or proc.get("name_fa") or code,
        "name_en": proc.get("name_en"),
        "description": proc.get("description"),
        "sop_order": sop_order,
        "status_index": extra_status or index_row.get("status") or ("sub_process_only" if not has_registry else None),
        "roles": index_row.get("roles_needed")
        or sorted({s.get("assigned_role") for s in states if s.get("assigned_role")}),
        "sub_process_refs_index": list(index_row.get("sub_process_refs") or []),
        "rules_used": list(index_row.get("rules_used") or []),
        "metadata_path": f"metadata/processes/{code}.json" if meta_path.exists() else None,
        "registry_path": f"processes/{code}" if has_registry else None,
        "registry_artifacts": artifacts,
        "notes": index_row.get("notes"),
        "initial_state": proc.get("initial_state"),
        "initial_role": proc.get("initial_role"),
        "states": [
            {
                "code": s.get("code"),
                "role": s.get("assigned_role"),
                "type": s.get("type"),
                "name_fa": s.get("name_fa"),
                "sla": s.get("sla"),
            }
            for s in states
        ],
        "workflow_steps": [
            {
                "from": tr.get("from"),
                "to": tr.get("to"),
                "trigger": tr.get("trigger"),
                "role": tr.get("required_role") or _state_role(states, tr.get("from")),
                "desc": tr.get("description_fa") or "",
                "conditions": list(tr.get("conditions") or []),
            }
            for tr in transitions
        ],
        "workflow_lines": workflow_lines,
    }


def _render_block(rec: dict) -> list[str]:
    sop = rec.get("sop_order")
    sop_label = str(sop) if sop is not None else "None"
    lines = [
        f"### {rec['code']} (SOP {sop_label})",
        f"- Name (fa): {rec['name_fa']}",
        f"- Status: {rec.get('status_index') or 'n/a'}",
        f"- metadata: {rec.get('metadata_path') or 'None'}",
        f"- registry: {rec.get('registry_path') or 'None'}",
    ]
    artifacts = rec.get("registry_artifacts") or []
    if artifacts:
        lines.append("- Registry artifacts: " + ", ".join(artifacts))
    else:
        lines.append("- Registry artifacts: SOP_document.txt (+ png where present)")
    roles = rec.get("roles") or []
    if roles:
        lines.append("- Roles: " + ", ".join(roles))
    refs = rec.get("sub_process_refs_index") or []
    if refs:
        lines.append("- INDEX sub_process_refs: " + ", ".join(refs))
    wf = rec.get("workflow_lines") or []
    lines.append("- Workflow:")
    if not wf:
        lines.append("  (no transitions)")
    else:
        shown = wf[:MAX_WORKFLOW_LINES]
        for i, step in enumerate(shown, start=1):
            lines.append(f"  {i}. {step}")
        extra = len(wf) - len(shown)
        if extra > 0:
            lines.append(f"  ... +{extra} transitions")
    lines.append("")
    return lines


def build() -> tuple[list[dict], str]:
    index = _load_json(INDEX_PATH)
    records = [_build_record(row, row["code"]) for row in index.get("processes") or []]
    used = {r["code"] for r in records}
    if "patient_referral" not in used and (META_DIR / "patient_referral.json").exists():
        records.append(_build_record(None, "patient_referral", extra_status="sub_process_only"))

    md: list[str] = []
    placed: set[str] = set()
    for title, pred in SECTIONS:
        group = [r for r in records if pred(r.get("sop_order"))]
        group.sort(key=lambda r: (r.get("sop_order") is None, r.get("sop_order") or 0, r["code"]))
        if not group:
            continue
        md.append(f"## {title}")
        md.append("")
        for rec in group:
            md.extend(_render_block(rec))
            placed.add(rec["code"])

    leftover = [r for r in records if r["code"] not in placed]
    shared, other = [], []
    for rec in leftover:
        if rec.get("status_index") == "sub_process_only" or rec["code"] == "patient_referral":
            shared.append(rec)
        else:
            other.append(rec)
    if shared:
        md.append("## Shared sub-processes")
        md.append("")
        for rec in shared:
            md.extend(_render_block(rec))
    if other:
        md.append("## Other")
        md.append("")
        for rec in other:
            md.extend(_render_block(rec))

    extract_rows = []
    for rec in records:
        row = dict(rec)
        row.pop("workflow_lines", None)
        extract_rows.append(row)
    return extract_rows, "\n".join(md).rstrip() + "\n"


def main() -> None:
    extract_rows, markdown = build()
    SUMMARY_PATH.write_text(markdown, encoding="utf-8")
    EXTRACT_PATH.write_text(
        json.dumps({"processes": extract_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {SUMMARY_PATH.name} and {EXTRACT_PATH.name} ({len(extract_rows)} processes)")


if __name__ == "__main__":
    main()
