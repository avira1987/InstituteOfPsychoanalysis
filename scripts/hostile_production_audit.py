#!/usr/bin/env python3
"""Hostile production audit — code-path structural analysis only."""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.audit_process_implementation import (  # noqa: E402
    audit_process,
    build_covered_roles,
    load_defined_rules,
    parse_action_registry,
)

PROCESSES_DIR = ROOT / "metadata" / "processes"
PORTAL_MAP = ROOT / "metadata" / "portal_role_assigned_role_map.json"
ACTION_HANDLER = ROOT / "app" / "services" / "action_handler.py"

# Daily-critical for an educational institute (hostile prioritization)
CRITICAL = frozenset({
    "introductory_course_registration",
    "introductory_course_completion",
    "intro_second_semester_registration",
    "comprehensive_course_registration",
    "comprehensive_term_start",
    "comprehensive_term_end",
    "start_therapy",
    "session_payment",
    "attendance_tracking",
    "supervision_50h_completion",
    "supervision_block_transition",
    "internship_readiness_consultation",
    "internship_12month_conditional_review",
    "educational_leave",
    "full_education_leave",
    "return_to_full_education",
    "violation_registration",
    "fee_determination",
    "student_non_registration",
    "thesis_defense_request",
    "introductory_term_end",
    "lesson_start_per_term",
    "class_attendance",
    "theory_course_completion",
    "payment",
})

NOOP_ACTION_PATTERNS = re.compile(
    r"return \"(?:attendance_blocked|sessions_marked|lms_noop|document_noop|portal_noop|.*_noop)",
    re.I,
)


def load_noop_actions() -> set[str]:
    text = ACTION_HANDLER.read_text(encoding="utf-8")
    noops: set[str] = set()
    for m in re.finditer(r"async def (_handle_\w+).*?(?=async def _handle_|\n    _registry)", text, re.S):
        body = m.group(0)
        if NOOP_ACTION_PATTERNS.search(body) or 'return f"lms_noop' in body or 'return "skip"' in body:
            hm = re.match(r"async def (_handle_\w+)", body)
            if hm:
                noops.add(hm.group(1))
    return noops


def handler_for_action(action_type: str, registry: dict[str, str]) -> str:
    return registry.get(action_type, "")


def build_registry() -> dict[str, str]:
    text = ACTION_HANDLER.read_text(encoding="utf-8")
    m = re.search(r"_registry\s*=\s*\{(.*?)\n    \}", text, re.S)
    reg: dict[str, str] = {}
    if m:
        for line in m.group(1).splitlines():
            lm = re.match(r'\s*"([^"]+)"\s*:\s*(_handle_\w+)\s*,?', line)
            if lm:
                reg[lm.group(1)] = lm.group(2)
    return reg


def stuck_states(pj: dict) -> list[str]:
    states = {s["code"]: s for s in pj.get("states", []) if s.get("code")}
    out = []
    for sc, st in states.items():
        if st.get("type") == "terminal":
            continue
        if not any(t.get("from") == sc for t in pj.get("transitions", [])):
            out.append(sc)
    return out


def can_student_start(pj: dict) -> bool:
    proc = pj.get("process") or {}
    initial = proc.get("initial_state")
    if not initial:
        return False
    for t in pj.get("transitions", []):
        if t.get("from") != initial:
            continue
        rr = t.get("required_role") or "student"
        if rr in ("student", "applicant", "admin"):
            return True
    init_st = next((s for s in pj.get("states", []) if s.get("code") == initial), {})
    if init_st.get("assigned_role") in ("student", "applicant"):
        return True
    return False


def has_system_auto_path(pj: dict) -> bool:
    for t in pj.get("transitions", []):
        if (t.get("required_role") or "system") == "system":
            return True
    return False


def terminal_reachable(pj: dict) -> bool:
    states = pj.get("states") or []
    terminals = {s["code"] for s in states if s.get("type") == "terminal"}
    if not terminals:
        return bool(not pj.get("transitions"))
    graph = defaultdict(list)
    for t in pj.get("transitions", []):
        graph[t.get("from")].append(t.get("to"))
    initial = (pj.get("process") or {}).get("initial_state")
    if not initial:
        return False
    seen = {initial}
    stack = [initial]
    while stack:
        cur = stack.pop()
        if cur in terminals:
            return True
        for nxt in graph.get(cur, []):
            if nxt and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def classify(pj: dict, impl: dict, stuck: list[str], reg: dict[str, str], noop_handlers: set[str]) -> str:
    code = (pj.get("process") or {}).get("code", "")
    if stuck:
        return "BLOCKING"
    if not terminal_reachable(pj):
        return "BLOCKING"
    if not can_student_start(pj) and not has_system_auto_path(pj):
        # subprocess-only — not blocking if parent starts it
        if code in ("fee_determination", "patient_referral", "violation_registration"):
            return "DEGRADED"
        return "BLOCKING"
    missing = impl.get("missing_actions") or []
    stub = impl.get("stub_actions") or []
    if missing or stub:
        if code in CRITICAL:
            return "BLOCKING" if impl.get("total_pct", 0) < 0.5 else "DEGRADED"
        return "DEGRADED"
    uncovered = impl.get("uncovered_roles") or []
    if uncovered:
        if code in CRITICAL:
            return "BLOCKING"
        return "DEGRADED"
    # check noop handlers on used actions
    for t in pj.get("transitions", []):
        for a in t.get("actions") or []:
            at = a.get("type")
            h = reg.get(at or "")
            if h in noop_handlers and code in CRITICAL:
                return "DEGRADED"
    if impl.get("total_pct", 0) >= 0.85:
        return "OPERATIONAL"
    if impl.get("total_pct", 0) >= 0.55:
        return "DEGRADED"
    if code in CRITICAL:
        return "BLOCKING"
    return "DEGRADED"


def main() -> int:
    real, stub = parse_action_registry(ACTION_HANDLER)
    defined = load_defined_rules(ROOT / "metadata" / "rules" / "all_rules.json")
    covered = build_covered_roles(PORTAL_MAP)
    norm = json.loads(PORTAL_MAP.read_text(encoding="utf-8")).get("normalize_assigned_role_typo") or {}
    reg = build_registry()
    noop_handlers = load_noop_actions()

    counts = {"OPERATIONAL": 0, "DEGRADED": 0, "BLOCKING": 0}
    rows = []
    blocking_detail = []

    for pf in sorted(PROCESSES_DIR.glob("*.json")):
        pj = json.loads(pf.read_text(encoding="utf-8"))
        code = (pj.get("process") or {}).get("code") or pf.stem
        impl = audit_process(pj, real, stub, defined, covered, norm)
        stuck = stuck_states(pj)
        cat = classify(pj, impl, stuck, reg, noop_handlers)
        counts[cat] += 1
        rows.append((code, cat, impl.get("total_pct", 0), stuck, impl))

        if cat == "BLOCKING":
            # find first human state without form/guidance
            form_states = set()
            for f in pj.get("forms") or []:
                uis = f.get("used_in_state")
                if isinstance(uis, list):
                    form_states.update(uis)
                elif uis:
                    form_states.add(uis)
            missing_form_state = None
            for s in pj.get("states", []):
                sc = s.get("code")
                if sc in form_states:
                    continue
                meta = (s.get("metadata") or {})
                if s.get("assigned_role") in ("student", "applicant") and s.get("type") != "terminal":
                    if not meta.get("student_task_fa"):
                        missing_form_state = sc
                        break
            blocking_detail.append({
                "code": code,
                "stuck": stuck,
                "uncovered_roles": impl.get("uncovered_roles"),
                "missing_actions": impl.get("missing_actions"),
                "stub_actions": impl.get("stub_actions"),
                "missing_form_state": missing_form_state,
                "total_pct": impl.get("total_pct"),
            })

    print(json.dumps({"counts": counts, "blocking": blocking_detail}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
