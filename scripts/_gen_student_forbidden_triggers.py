"""One-off generator for app/core/student_forbidden_triggers.py — run from repo root."""
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "metadata", "processes")

roles_by_trigger: defaultdict[str, set] = defaultdict(set)
for dp, _, fs in os.walk(PROC):
    for f in fs:
        if not f.endswith(".json"):
            continue
        with open(os.path.join(dp, f), encoding="utf-8") as fp:
            data = json.load(fp)
        for t in data.get("transitions") or []:
            tr = t.get("trigger")
            if not tr:
                continue
            roles_by_trigger[tr].add(t.get("required_role") or "")

only_system = sorted(tr for tr, roles in roles_by_trigger.items() if roles == {"system"})
out = os.path.join(ROOT, "app", "core", "student_forbidden_triggers.py")
lines = [
    '"""Triggers that appear only with required_role==system in all process JSON.',
    "Deny student HTTP triggers even when DB metadata is stale.",
    'Regenerate: python scripts/_gen_student_forbidden_triggers.py',
    '"""',
    "",
    "STUDENT_FORBIDDEN_TRIGGER_EVENTS = frozenset({",
]
lines.extend(f"    {x!r}," for x in only_system)
lines.append("})")
lines.append("")
with open(out, "w", encoding="utf-8") as fp:
    fp.write("\n".join(lines))
print("wrote", len(only_system), "triggers ->", out)
