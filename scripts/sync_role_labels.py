#!/usr/bin/env python3
"""اسکن نقش‌های استفاده‌شده در متادیتا و گزارش موارد بدون ترجمه در role_labels_fa.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSES_DIR = ROOT / "metadata" / "processes"
LABELS_PATH = ROOT / "metadata" / "role_labels_fa.json"
ROLES_JSON_PATH = ROOT / "metadata" / "roles.json"


def _collect_process_roles() -> set[str]:
    roles: set[str] = set()
    for path in PROCESSES_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for state in data.get("states") or []:
            if state.get("assigned_role"):
                roles.add(str(state["assigned_role"]).strip())
        for tr in data.get("transitions") or []:
            if tr.get("required_role"):
                roles.add(str(tr["required_role"]).strip())
            for ed in tr.get("editable_by") or []:
                roles.add(str(ed).strip())
    return {r for r in roles if r}


def _portal_roles() -> set[str]:
    if not ROLES_JSON_PATH.is_file():
        return set()
    data = json.loads(ROLES_JSON_PATH.read_text(encoding="utf-8"))
    return {str(e["code"]).strip() for e in data if e.get("code")}


def main() -> int:
    doc = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    labels = doc.get("labels") or {}
    aliases = doc.get("typo_aliases") or {}

    used = _collect_process_roles() | _portal_roles()
    missing = sorted(
        code
        for code in used
        if code not in labels and code not in aliases
    )

    print(f"Labels defined: {len(labels)}")
    print(f"Roles in metadata: {len(used)}")
    if missing:
        print("\nMissing translations:")
        for code in missing:
            print(f"  - {code}")
        return 1
    print("\nAll referenced roles have translations (direct or via typo_aliases).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
