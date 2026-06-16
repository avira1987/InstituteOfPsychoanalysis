#!/usr/bin/env python3
"""
Scan admin-ui source for process-related UI anchors (data-testid) and transition handlers.
Writes NDJSON lines to stdout; use --json for a single summary object.

Usage (from repo root):
  python scripts/audit_process_ui_clicks.py
  python scripts/audit_process_ui_clicks.py --root admin-ui/src --format json > report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Patterns aligned with Playwright / manual QA for فرایند دانشجو و پرسنل
TRIGGER_TRANSITION_RE = re.compile(r"triggerTransition\s*\(\s*t\s*\)")
ON_TRIGGER_RE = re.compile(r"onTrigger\s*=")
QUEST_TRANSITION_RE = re.compile(r"quest-transition-")

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "admin-ui" / "src"


def extract_data_testids(text: str) -> tuple[list[str], list[str]]:
    """Collect data-testid values: quoted strings and template literals (single-line)."""
    static = sorted(
        set(re.findall(r'data-testid\s*=\s*"([^"]+)"', text))
        | set(re.findall(r"data-testid\s*=\s*'([^']+)'", text))
    )
    expr = sorted(set(re.findall(r"data-testid\s*=\s*\{`([^`]+)`\}", text)))
    # Multiline JSX: data-testid={ cond ? `a-${x}` : 'b' }
    if re.search(r"data-testid\s*=\s*\{[^}]*student-dashboard-start-process", text, re.DOTALL):
        expr.append("student-dashboard-start-process-${regCodeForProfile} | student-dashboard-start-registration")
    return static, sorted(set(expr))


def scan_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    static_ids, expr_ids = extract_data_testids(text)
    return {
        "path": str(path).replace("\\", "/"),
        "data_testid_static": static_ids,
        "data_testid_expressions": expr_ids,
        "has_trigger_transition_t": bool(TRIGGER_TRANSITION_RE.search(text)),
        "has_on_trigger_prop": bool(ON_TRIGGER_RE.search(text)),
        "has_quest_transition_pattern": bool(QUEST_TRANSITION_RE.search(text)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit process UI clicks / test ids in admin-ui")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Source root (default: admin-ui/src)")
    ap.add_argument("--format", choices=("ndjson", "json"), default="ndjson")
    args = ap.parse_args()
    root: Path = args.root
    if not root.is_dir():
        print(json.dumps({"error": f"root not found: {root}"}, ensure_ascii=False), file=sys.stderr)
        return 1

    files = sorted(
        [p for p in root.rglob("*") if p.suffix in (".jsx", ".tsx", ".js", ".ts") and "node_modules" not in p.parts]
    )
    rows = [scan_file(p) for p in files]

    # Aggregate: recommended E2E selectors for student process flow
    student_portal = [r for r in rows if r["path"].endswith("StudentPortal.jsx")]
    quest = [r for r in rows if r["path"].endswith("StudentQuestCard.jsx")]
    summary = {
        "files_scanned": len(rows),
        "student_portal_testids": (student_portal[0]["data_testid_static"] + student_portal[0]["data_testid_expressions"])
        if student_portal
        else [],
        "student_quest_card_testids": (quest[0]["data_testid_static"] + quest[0]["data_testid_expressions"]) if quest else [],
        "files_with_trigger_transition_button": [r["path"] for r in rows if r["has_trigger_transition_t"]],
    }

    if args.format == "json":
        print(json.dumps({"summary": summary, "files": rows}, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps({"kind": "summary", **summary}, ensure_ascii=False))
    for r in rows:
        if (
            r["data_testid_static"]
            or r["data_testid_expressions"]
            or r["has_trigger_transition_t"]
            or r["has_on_trigger_prop"]
        ):
            print(json.dumps({"kind": "file", **r}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
