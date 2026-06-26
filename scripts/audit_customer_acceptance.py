#!/usr/bin/env python3
"""Customer acceptance audit — executable code paths only.

Compares SOP (registry), workflow metadata, backend handlers, portal/UI routes,
pytest level A/B/C, and calendar/SLA coverage for all metadata/processes/*.json.

Usage:
  python scripts/audit_customer_acceptance.py
  python scripts/audit_customer_acceptance.py --run-pytest
  python scripts/audit_customer_acceptance.py --pytest-json reports/pytest_processes.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
PROCESSES_DIR = ROOT / "metadata" / "processes"
REGISTRY_DIR = ROOT / "metadata" / "process_registry" / "processes"
ACTION_HANDLER = ROOT / "app" / "services" / "action_handler.py"
ALL_RULES = ROOT / "metadata" / "rules" / "all_rules.json"
PORTAL_MAP = ROOT / "metadata" / "portal_role_assigned_role_map.json"
ALT_PATHS = ROOT / "metadata" / "customer_acceptance_alternate_paths.json"
GAP_RULES = ROOT / "metadata" / "operator_gap_rules.json"
CALENDAR_TRIGGERS = ROOT / "app" / "services" / "calendar_triggers.py"
SLA_MONITOR = ROOT / "app" / "services" / "sla_monitor.py"
OUT_JSON = ROOT / "reports" / "customer_acceptance_audit.json"
OUT_MD = ROOT / "reports" / "customer_acceptance_audit.md"

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# Import shared helpers (scripts/ is not always a package)
import importlib.util

_impl_spec = importlib.util.spec_from_file_location(
    "audit_process_implementation",
    ROOT / "scripts" / "audit_process_implementation.py",
)
_impl_mod = importlib.util.module_from_spec(_impl_spec)
assert _impl_spec.loader is not None
_impl_spec.loader.exec_module(_impl_mod)
audit_process = _impl_mod.audit_process
build_covered_roles = _impl_mod.build_covered_roles
parse_action_registry = _impl_mod.parse_action_registry
load_defined_rules = _impl_mod.load_defined_rules

sys.path.insert(0, str(ROOT))
from app.meta.operator_student_visibility_audit import build_operator_student_visibility_report  # noqa: E402  # optional meta


def _normalize_role(role: str, norm_map: dict) -> str:
    return norm_map.get(role, role) if role else ""


def parse_sop_steps(sop_path: Path) -> list[dict[str, str]]:
    """Extract numbered SOP step headers from section «گام‌های اجرایی» only."""
    if not sop_path.is_file():
        return []
    text = sop_path.read_text(encoding="utf-8")
    # Restrict to executive steps section (skip philosophy/principles numbered lists)
    section_m = re.search(
        r"۳\.?\s*گام‌های اجرایی[^\n]*\n[-─]+\s*\n(.*?)(?:\n۴\.|\n={3,}|\Z)",
        text,
        re.DOTALL,
    )
    if section_m:
        text = section_m.group(1)
    steps: list[dict[str, str]] = []
    for m in re.finditer(
        r"^(\s{0,2})([۰-۹0-9]+)\)\s*(.+?)\s*$",
        text,
        re.MULTILINE,
    ):
        num = m.group(2).translate(_PERSIAN_DIGITS)
        title = m.group(3).strip()
        if len(title) < 3 or len(title) > 120:
            continue
        steps.append({"num": num, "title": title})
    return steps


def _metadata_tokens(pj: dict) -> set[str]:
    """Collect searchable tokens from workflow JSON for SOP step mapping."""
    tokens: set[str] = set()
    proc = pj.get("process") or {}
    if proc.get("code"):
        tokens.add(str(proc["code"]).lower())
    for s in pj.get("states") or []:
        for key in ("code", "name_fa", "name_en"):
            v = s.get(key)
            if v:
                tokens.add(str(v).lower())
    for t in pj.get("transitions") or []:
        for key in ("trigger", "from", "to"):
            v = t.get(key)
            if v:
                tokens.add(str(v).lower())
        for a in t.get("actions") or []:
            if isinstance(a, dict):
                for k, v in a.items():
                    if k in ("type", "process_code", "template") and v:
                        tokens.add(str(v).lower())
    for f in pj.get("forms") or []:
        for key in ("code", "name_fa"):
            v = f.get(key)
            if v:
                tokens.add(str(v).lower())
        for field in f.get("fields") or []:
            for key in ("name", "label_fa"):
                v = field.get(key)
                if v:
                    tokens.add(str(v).lower())
    return tokens


_SOP_KEYWORD_HINTS: dict[str, list[str]] = {
    "درمانگر": ["therapist", "therapist_recording", "therapist_review"],
    "پرداخت": ["payment", "awaiting_payment", "pay", "invoice"],
    "حضور": ["present", "attendance", "student_present", "record_attendance"],
    "غیاب": ["absent", "absence", "student_absent"],
    "مصاحبه": ["interview", "interviewer"],
    "مدرک": ["document", "documents_"],
    "ثبت": ["registration", "register"],
    "کمیته": ["committee", "commission"],
    "سوپرو": ["supervision", "supervisor"],
    "انترن": ["intern", "internship"],
    "مرخص": ["leave", "on_leave"],
    "تخلف": ["violation"],
    "لغو": ["cancel", "cancellation"],
    "کنسلی": ["cancel", "cancellation"],
    "اساتید": ["instructor", "ta_"],
    "مقاله": ["article", "thesis"],
    "پایان": ["interview_end_time", "end_time", "end_date", "پایان"],
    "آنلاین": ["interview_mode", "online", "آنلاین"],
    "حضوری": ["interview_mode", "حضوری"],
}


def map_sop_steps(code: str, steps: list[dict], pj: dict) -> tuple[list[dict], list[dict]]:
    """Map SOP steps to metadata; return (mapped, unmapped)."""
    if not steps:
        return [], []
    tokens = _metadata_tokens(pj)
    state_names_fa = [
        (s.get("code") or "", (s.get("name_fa") or "").lower())
        for s in pj.get("states") or []
    ]
    mapped, unmapped = [], []
    for step in steps:
        title_lower = step["title"].lower()
        keywords = re.findall(r"[\w\u0600-\u06FF]{3,}", title_lower)
        hit = False
        matched_via = ""
        for kw in keywords:
            if kw in tokens:
                hit = True
                matched_via = f"token:{kw}"
                break
        if not hit:
            for fa_hint, hints in _SOP_KEYWORD_HINTS.items():
                if fa_hint in title_lower and any(h in tokens for h in hints):
                    hit = True
                    matched_via = f"hint:{fa_hint}"
                    break
        if not hit:
            for sc, name_fa in state_names_fa:
                if not name_fa:
                    continue
                name_words = re.findall(r"[\w\u0600-\u06FF]{3,}", name_fa)
                if any(w in title_lower for w in name_words[:4]):
                    hit = True
                    matched_via = f"state:{sc}"
                    break
        if not hit:
            for t in pj.get("transitions") or []:
                for a in t.get("actions") or []:
                    if isinstance(a, dict) and a.get("process_code"):
                        pc = str(a["process_code"]).lower()
                        if pc in title_lower or any(w in pc for w in keywords[:3]):
                            hit = True
                            matched_via = f"subprocess:{a['process_code']}"
                            break
                if hit:
                    break
        if hit:
            mapped.append({**step, "matched_via": matched_via})
        else:
            unmapped.append(step)
    return mapped, unmapped


def _load_alt_config() -> dict:
    if ALT_PATHS.is_file():
        return json.loads(ALT_PATHS.read_text(encoding="utf-8"))
    return {}


def _role_to_portal_role(assigned_role: str, portal_data: dict) -> Optional[str]:
    norm = portal_data.get("normalize_assigned_role_typo") or {}
    ar = norm.get(assigned_role, assigned_role)
    for portal_role, cfg in (portal_data.get("portal_roles") or {}).items():
        if portal_role == "admin":
            continue
        roles = cfg.get("assigned_roles") or []
        if ar in roles:
            return portal_role
    if ar in ("student", "applicant"):
        return "student"
    if ar == "admin":
        return "admin"
    return None


def _subprocess_codes_from_all_metadata() -> set[str]:
    codes: set[str] = set()
    for pf in PROCESSES_DIR.glob("*.json"):
        try:
            pj = json.loads(pf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for t in pj.get("transitions") or []:
            for a in t.get("actions") or []:
                if isinstance(a, dict) and a.get("type") == "start_process" and a.get("process_code"):
                    codes.add(str(a["process_code"]))
    return codes


def check_auto_start(
    code: str,
    pj: dict,
    alt: dict,
    gap_rules: dict,
    subprocess_codes: set[str],
) -> tuple[list[dict], list[dict]]:
    """FAIL if process must auto-start but has no executable starter. Returns (hard_fails, warnings)."""
    hard: list[dict] = []
    warn: list[dict] = []
    auto_paths = alt.get("auto_start_paths") or {}
    if code in auto_paths or code in subprocess_codes:
        return hard, warn

    proc = pj.get("process") or {}
    initial = proc.get("initial_state")
    transitions = pj.get("transitions") or []
    student_can_start = any(
        t.get("from") == initial
        and (t.get("required_role") or "student") in ("student", "applicant", "admin")
        for t in transitions
    )

    for rule in gap_rules.get("rules") or []:
        if rule.get("process_code") == code and rule.get("expect") == "missing_instance":
            if not rule.get("enabled"):
                entry = {
                    "check": "auto_start",
                    "detail": f"operator_gap_rules rule '{rule.get('id')}' disabled — no auto-start for eligible students",
                    "backend": str(GAP_RULES),
                    "frontend": "admin-ui/src/pages/StudentPortal.jsx",
                    "fix": f"Enable gap rule {rule.get('id')} and wire calendar/student lifecycle trigger",
                }
                if student_can_start:
                    entry["severity"] = "minor"
                    warn.append(entry)
                else:
                    hard.append(entry)

    if not transitions:
        return hard, warn

    initial_state = next((s for s in pj.get("states") or [] if s.get("code") == initial), {})
    if initial_state.get("assigned_role") == "system":
        out_tr = [t for t in transitions if t.get("from") == initial]
        if not out_tr:
            hard.append({
                "check": "auto_start",
                "detail": f"Initial state '{initial}' is system-only with no outgoing transitions",
                "backend": f"metadata/processes/{code}.json",
                "frontend": "",
                "fix": "Add system/calendar transition from initial state or document manual start API",
            })
    return hard, warn


def _student_state_has_actionable_transition(pj: dict, state_code: str) -> bool:
    """Student can advance via StudentQuestCard triggerTransition without a dedicated form."""
    for t in pj.get("transitions") or []:
        if t.get("from") != state_code:
            continue
        rr = t.get("required_role") or "student"
        if rr in ("student", "applicant", "admin"):
            return True
    return False


def check_portal_roles(
    code: str,
    impl: dict,
    portal_data: dict,
    alt: dict,
) -> list[dict]:
    fails: list[dict] = []
    role_portals = alt.get("role_portal_frontend") or {}
    for role in impl.get("uncovered_roles") or []:
        portal_role = _role_to_portal_role(role, portal_data)
        fe = role_portals.get(portal_role or role, "")
        fails.append({
            "check": "portal_missing",
            "detail": f"Role '{role}' has no portal mapping",
            "backend": str(PORTAL_MAP),
            "frontend": fe or "admin-ui/src/components/Layout.jsx",
            "fix": f"Add '{role}' to portal_role_assigned_role_map.json and Layout.jsx navItems",
        })
    return fails


def check_forms(
    code: str,
    pj: dict,
    alt: dict,
) -> list[dict]:
    fails: list[dict] = []
    form_alt = (alt.get("form_alternate_paths") or {}).get(code)
    states = {s.get("code"): s for s in pj.get("states") or []}
    form_states: set[str] = set()
    for f in pj.get("forms") or []:
        uis = f.get("used_in_state")
        if isinstance(uis, list):
            form_states.update(x for x in uis if x)
        elif uis:
            form_states.add(uis)

    human_states = {
        s.get("code")
        for s in pj.get("states") or []
        if s.get("assigned_role") not in (None, "system") and s.get("type") != "terminal"
    }
    states_needing_input: set[str] = set()
    for t in pj.get("transitions") or []:
        rr = t.get("required_role")
        frm = t.get("from")
        if rr and rr != "system" and frm in human_states:
            states_needing_input.add(frm)

    alt_states = set((form_alt or {}).get("states") or [])
    has_alt = bool(form_alt)

    for sc in states_needing_input:
        sm = states.get(sc) or {}
        meta = sm.get("metadata") or {}
        role = sm.get("assigned_role") or ""
        has_form = sc in form_states
        has_guidance = bool(meta.get("student_task_fa") or meta.get("student_short_fa"))
        if has_form or has_guidance:
            continue
        if has_alt and (not alt_states or sc in alt_states):
            continue
        # Operator roles with portal + generic transitions are OK
        if role not in ("student", "applicant"):
            portal_data = json.loads(PORTAL_MAP.read_text(encoding="utf-8"))
            pr = _role_to_portal_role(role, portal_data)
            role_portals = alt.get("role_portal_frontend") or {}
            if pr and pr in role_portals:
                continue
        elif _student_state_has_actionable_transition(pj, sc):
            continue
        fails.append({
            "check": "form_missing",
            "detail": f"State '{sc}' (role={role}) needs input but has no form, guidance, or alternate path",
            "backend": f"metadata/processes/{code}.json",
            "frontend": "admin-ui/src/components/ProcessStepForms.jsx",
            "fix": f"Add form for state '{sc}' or register alternate path in customer_acceptance_alternate_paths.json",
        })
    return fails


def check_actions(code: str, impl: dict) -> list[dict]:
    fails: list[dict] = []
    for a in impl.get("missing_actions") or []:
        fails.append({
            "check": "action_missing",
            "detail": f"Action type '{a}' has no handler",
            "backend": "app/services/action_handler.py",
            "frontend": "",
            "fix": f"Register handler for action '{a}' in ActionHandler._registry",
        })
    for a in impl.get("stub_actions") or []:
        fails.append({
            "check": "action_stub",
            "detail": f"Action type '{a}' is stub only",
            "backend": "app/services/action_handler.py",
            "frontend": "",
            "fix": f"Implement real handler for '{a}' in workflow services",
        })
    return fails


def check_artifacts(code: str, pj: dict, alt: dict, pytest_pass: dict) -> list[dict]:
    prefixes = tuple(alt.get("artifact_action_prefixes") or [])
    has_artifact_action = False
    for t in pj.get("transitions") or []:
        for a in t.get("actions") or []:
            if not isinstance(a, dict):
                continue
            at = a.get("type") or ""
            if any(at.startswith(p) or at == p.rstrip("_") for p in prefixes):
                has_artifact_action = True
                break

    terminals = {s.get("code") for s in pj.get("states") or [] if s.get("type") == "terminal"}
    if not terminals and not pj.get("transitions"):
        return []  # stub process

    if has_artifact_action:
        return []

    if pytest_pass.get("level_c") is True or pytest_pass.get("level_b") is True:
        return []  # backend path reaches next state / terminal

    return [{
        "check": "artifact_missing",
        "detail": "No artifact-producing action and pytest B/C did not prove terminal reachability",
        "backend": "app/services/workflow/",
        "frontend": "admin-ui/src/pages/StudentPortal.jsx",
        "fix": "Add record_*/generate_* action on terminal path or ensure level C test passes",
    }]


def check_visibility(code: str, pj: dict, alt: dict) -> list[dict]:
    """FAIL only when student/applicant must act or see outcome but has no surface."""
    fails: list[dict] = []
    form_states: set[str] = set()
    for f in pj.get("forms") or []:
        uis = f.get("used_in_state")
        if isinstance(uis, list):
            form_states.update(x for x in uis if x)
        elif uis:
            form_states.add(uis)

    student_result_paths = (alt.get("student_result_visibility") or {}).get(code)
    if student_result_paths:
        return fails

    for st in pj.get("states") or []:
        ar = (st.get("assigned_role") or "").strip()
        if ar not in ("student", "applicant"):
            continue
        sc = st.get("code") or ""
        if st.get("type") == "terminal":
            continue
        meta = st.get("metadata") or {}
        has_form = sc in form_states
        has_guidance = bool(meta.get("student_task_fa") or meta.get("student_short_fa"))
        if not has_form and not has_guidance:
            if _student_state_has_actionable_transition(pj, sc):
                continue
            fails.append({
                "check": "visibility_missing",
                "detail": f"Student state '{sc}' has no form or student_task_fa guidance",
                "backend": f"metadata/processes/{code}.json",
                "frontend": "admin-ui/src/pages/StudentPortal.jsx",
                "fix": f"Add student-visible form or student_task_fa for state '{sc}'",
            })
    return fails


def check_stuck_states(code: str, pj: dict, alt: dict) -> list[dict]:
    fails: list[dict] = []
    cal_triggers_in_code: set[str] = set()
    if CALENDAR_TRIGGERS.is_file():
        cal_text = CALENDAR_TRIGGERS.read_text(encoding="utf-8")
        cal_triggers_in_code = set(re.findall(r'trigger_event="([^"]+)"', cal_text))
    cal_doc = set(alt.get("calendar_triggers_documented") or []) | cal_triggers_in_code
    sla_handles_generic = SLA_MONITOR.is_file() and "breach.breach_event" in SLA_MONITOR.read_text(encoding="utf-8")

    for st in pj.get("states") or []:
        sc = st.get("code")
        if st.get("type") == "terminal":
            continue
        out_tr = [t for t in pj.get("transitions") or [] if t.get("from") == sc]
        if not out_tr:
            fails.append({
                "check": "stuck_state",
                "detail": f"Non-terminal state '{sc}' has no outgoing transitions",
                "backend": f"metadata/processes/{code}.json",
                "frontend": "",
                "fix": f"Add transition from '{sc}' or mark as terminal",
            })
            continue

        sla_event = st.get("on_sla_breach_event")
        if sla_event and not sla_handles_generic:
            fails.append({
                "check": "stuck_state",
                "detail": f"SLA breach event '{sla_event}' on '{sc}' — sla_monitor lacks generic handler",
                "backend": "app/services/sla_monitor.py",
                "frontend": "",
                "fix": "Ensure sla_monitor executes on_sla_breach_event transitions",
            })

        sys_triggers = [
            t.get("trigger") for t in out_tr
            if (t.get("required_role") or "system") == "system"
        ]
        human_tr = [t for t in out_tr if (t.get("required_role") or "system") != "system"]
        # Stuck only when ALL exits are calendar/time triggers not implemented in calendar_triggers.py
        calendar_names = cal_doc | cal_triggers_in_code
        if sys_triggers and not human_tr:
            calendar_exits = [tr for tr in sys_triggers if tr and tr in calendar_names]
            if calendar_exits and len(calendar_exits) == len([t for t in sys_triggers if t]):
                not_impl = [tr for tr in calendar_exits if tr not in cal_triggers_in_code]
                if not_impl:
                    fails.append({
                        "check": "stuck_state",
                        "detail": f"State '{sc}' depends on calendar triggers not implemented: {not_impl}",
                        "backend": "app/services/calendar_triggers.py",
                        "frontend": "",
                        "fix": "Implement calendar trigger in calendar_triggers.py",
                    })

        if human_tr and not sys_triggers:
            portal_data = json.loads(PORTAL_MAP.read_text(encoding="utf-8"))
            norm = portal_data.get("normalize_assigned_role_typo") or {}
            covered = build_covered_roles(PORTAL_MAP)
            for t in human_tr:
                rr = _normalize_role(t.get("required_role") or "", norm)
                if rr and rr not in covered and rr not in ("student", "applicant"):
                    fails.append({
                        "check": "stuck_state",
                        "detail": f"State '{sc}' requires role '{rr}' with no portal — process can stall",
                        "backend": str(PORTAL_MAP),
                        "frontend": "admin-ui/src/components/Layout.jsx",
                        "fix": f"Add portal for role '{rr}'",
                    })
    return fails


def check_partial_ui(code: str, pj: dict, alt: dict) -> list[dict]:
    """Partial UI paths are minor — returned as warnings not hard fails."""
    partial = (alt.get("partial_ui_paths") or {}).get(code)
    resolved = (alt.get("interviewer_result_paths") or {}).get(code)
    if resolved and not partial:
        return []
    if not partial:
        return []
    roles_in_proc = set()
    for t in pj.get("transitions") or []:
        if t.get("required_role"):
            roles_in_proc.add(t["required_role"])
    if partial.get("role") in roles_in_proc:
        return [{
            "check": "partial_ui",
            "severity": "minor",
            "detail": partial.get("issue_fa", ""),
            "backend": "",
            "frontend": partial.get("workaround_frontend", ""),
            "fix": partial.get("workaround_note_fa", ""),
        }]
    return []


def run_pytest_suite() -> dict[str, dict[str, Optional[bool]]]:
    """Run process pytest files and parse per-process pass/fail."""
    test_files = [
        "tests/processes/test_all_processes_level_a_smoke.py",
        "tests/processes/test_all_processes_level_b.py",
        "tests/processes/test_all_processes_level_c.py",
    ]
    result: dict[str, dict[str, Optional[bool]]] = defaultdict(
        lambda: {"level_a": None, "level_b": None, "level_c": None}
    )
    for tf, level in zip(test_files, ("level_a", "level_b", "level_c")):
        cmd = [
            sys.executable, "-m", "pytest", tf,
            "--tb=no", "-q", "--no-header",
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = proc.stdout + proc.stderr
        # PASSED [  1%] test...::test_name[process_code]
        for line in output.splitlines():
            m = re.search(r"(PASSED|FAILED|ERROR)\s+.*\[([^\]]+)\]", line)
            if m:
                status, process_code = m.group(1), m.group(2)
                result[process_code][level] = status == "PASSED"
        if proc.returncode != 0 and not any(v[level] is not None for v in result.values()):
            # whole file failed — mark unknown
            pass
    return dict(result)


def parse_junit_xml(path: Path) -> dict[str, dict[str, Optional[bool]]]:
    """Parse pytest junitxml into per-process level_a/b/c pass map."""
    import xml.etree.ElementTree as ET

    tree = ET.parse(path)
    root = tree.getroot()
    result: dict[str, dict[str, Optional[bool]]] = defaultdict(
        lambda: {"level_a": None, "level_b": None, "level_c": None}
    )
    level_map = {
        "test_process_level_a_load_sync_start_matches_initial_state": "level_a",
        "test_process_level_b_one_transition_from_initial_succeeds": "level_b",
        "test_process_level_c_second_transition_or_terminal_after_first": "level_c",
    }
    for case in root.iter("testcase"):
        name = case.get("name") or ""
        classname = case.get("classname") or ""
        failed = case.find("failure") is not None or case.find("error") is not None
        # parametrized: test_name[process_code]
        m = re.search(r"\[([^\]]+)\]$", name)
        process_code = m.group(1) if m else None
        if not process_code:
            continue
        for test_prefix, level in level_map.items():
            if test_prefix in name or test_prefix in classname:
                result[process_code][level] = not failed
                break
    return dict(result)


def load_pytest_json(path: Path) -> dict[str, dict[str, Optional[bool]]]:
    if path.suffix == ".xml":
        return parse_junit_xml(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("processes") or data


def classify_process(
    fails: list[dict],
    partial: list[dict],
    sop_unmapped: list[dict],
    sop_steps: list[dict],
    user_complete: bool,
) -> str:
    hard_fails = [f for f in fails if f.get("check") != "partial_ui"]
    major_checks = {
        "portal_missing", "stuck_state", "action_missing", "action_stub",
        "pytest_b_fail", "pytest_c_fail", "auto_start",
    }
    if any(f.get("check") in major_checks for f in hard_fails):
        return "C"
    if user_complete and not sop_unmapped and not partial:
        return "A"
    if user_complete:
        return "B"
    if hard_fails:
        return "C"
    return "B"


def build_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Customer Acceptance Audit")
    lines.append("")
    lines.append(f"Generated: {report['meta']['generated_at']}")
    lines.append(f"**Customer Acceptance Readiness: {report['meta']['readiness_pct']}%** "
                 f"({report['meta']['pass_count']}/{report['meta']['scored_process_count']} processes)")
    lines.append("")

    lines.append("## Main Table")
    lines.append("")
    lines.append("| Process | SOP Requirement | Implemented | Missing | User Can Actually Complete? |")
    lines.append("|---------|-----------------|-------------|---------|----------------------------|")
    for row in report["processes"]:
        sop_req = "; ".join(f"{s['num']}) {s['title'][:40]}" for s in row.get("sop_steps", [])[:4])
        if len(row.get("sop_steps", [])) > 4:
            sop_req += f" (+{len(row['sop_steps']) - 4} more)"
        impl = f"{len(row.get('sop_mapped', []))}/{len(row.get('sop_steps', []))} SOP steps"
        if row.get("pytest_level_b"):
            impl += "; pytest B OK"
        missing = "; ".join(
            f"{f['check']}:{f['detail'][:50]}" for f in row.get("fails", [])[:2]
        )
        if row.get("sop_unmapped"):
            missing = (missing + "; " if missing else "") + f"{len(row['sop_unmapped'])} SOP unmapped"
        complete = "YES" if row.get("user_can_complete") else "**NO**"
        lines.append(f"| {row['code']} | {sop_req or '—'} | {impl} | {missing or '—'} | {complete} |")

    fail_rows = [r for r in report["processes"] if not r.get("user_can_complete")]
    if fail_rows:
        lines.append("")
        lines.append("## FAIL Details")
        lines.append("")
        for row in fail_rows:
            lines.append(f"### {row['code']}")
            for f in row.get("fails", []):
                if f.get("check") == "partial_ui":
                    continue
                lines.append(f"- **Check:** {f['check']}")
                lines.append(f"  - Step: {f['detail']}")
                lines.append(f"  - Backend: `{f.get('backend', '')}`")
                lines.append(f"  - Frontend: `{f.get('frontend', '')}`")
                lines.append(f"  - Fix: {f.get('fix', '')}")
            lines.append("")

    lines.append("## SECTION A — Processes ready for customer delivery")
    lines.append("")
    for code in report["sections"]["A"]:
        lines.append(f"- `{code}`")
    if not report["sections"]["A"]:
        lines.append("- _(none)_")

    lines.append("")
    lines.append("## SECTION B — Processes requiring minor fixes")
    lines.append("")
    for code in report["sections"]["B"]:
        lines.append(f"- `{code}`")
    if not report["sections"]["B"]:
        lines.append("- _(none)_")

    lines.append("")
    lines.append("## SECTION C — Processes requiring major redesign")
    lines.append("")
    for code in report["sections"]["C"]:
        lines.append(f"- `{code}`")
    if not report["sections"]["C"]:
        lines.append("- _(none)_")

    lines.append("")
    lines.append("## SECTION D — Top 20 blockers preventing customer acceptance")
    lines.append("")
    for i, b in enumerate(report["top_blockers"][:20], 1):
        lines.append(f"{i}. **{b['check']}** — affects {b['count']} process(es): {', '.join(b['processes'][:5])}"
                     f"{'…' if len(b['processes']) > 5 else ''}")
        lines.append(f"   - Fix pattern: {b.get('sample_fix', '')}")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Customer acceptance audit")
    ap.add_argument("--run-pytest", action="store_true", help="Run pytest level A/B/C before audit")
    ap.add_argument("--pytest-json", type=Path, help="Load pytest results from JSON or JUnit XML")
    args = ap.parse_args()

    alt = _load_alt_config()
    exclude = set(alt.get("exclude_from_score") or [])
    real, stub = parse_action_registry(ACTION_HANDLER)
    defined_rules = load_defined_rules(ALL_RULES)
    portal_data = json.loads(PORTAL_MAP.read_text(encoding="utf-8"))
    covered_roles = build_covered_roles(PORTAL_MAP)
    norm_map = portal_data.get("normalize_assigned_role_typo") or {}
    gap_rules = json.loads(GAP_RULES.read_text(encoding="utf-8")) if GAP_RULES.is_file() else {"rules": []}

    visibility_report = build_operator_student_visibility_report()

    pytest_results: dict[str, dict[str, Optional[bool]]] = {}
    if args.pytest_json and args.pytest_json.is_file():
        pytest_results = load_pytest_json(args.pytest_json)
    elif args.run_pytest:
        print("Running pytest level A/B/C...", file=sys.stderr)
        pytest_results = run_pytest_suite()

    subprocess_codes = _subprocess_codes_from_all_metadata()

    processes_out: list[dict] = []
    blocker_counter: Counter = Counter()
    blocker_samples: dict[str, str] = {}
    blocker_processes: dict[str, list[str]] = defaultdict(list)

    for pf in sorted(PROCESSES_DIR.glob("*.json")):
        pj = json.loads(pf.read_text(encoding="utf-8"))
        code = (pj.get("process") or {}).get("code") or pf.stem
        name_fa = (pj.get("process") or {}).get("name_fa") or code

        impl = audit_process(pj, real, stub, defined_rules, covered_roles, norm_map)
        sop_path = REGISTRY_DIR / code / "SOP_document.txt"
        sop_steps = parse_sop_steps(sop_path)
        sop_mapped, sop_unmapped = map_sop_steps(code, sop_steps, pj)

        pr = pytest_results.get(code) or {}
        pytest_a = pr.get("level_a")
        pytest_b = pr.get("level_b")
        pytest_c = pr.get("level_c")

        fails: list[dict] = []
        warnings: list[dict] = []
        auto_hard, auto_warn = check_auto_start(code, pj, alt, gap_rules, subprocess_codes)
        fails.extend(auto_hard)
        warnings.extend(auto_warn)
        fails.extend(check_portal_roles(code, impl, portal_data, alt))
        fails.extend(check_forms(code, pj, alt))
        fails.extend(check_actions(code, impl))
        fails.extend(check_artifacts(code, pj, alt, {"level_b": pytest_b, "level_c": pytest_c}))
        fails.extend(check_visibility(code, pj, alt))
        fails.extend(check_stuck_states(code, pj, alt))
        partial = check_partial_ui(code, pj, alt)
        partial.extend(warnings)

        hard_fails = [f for f in fails if f.get("check") != "partial_ui"]

        # Pytest B/C failure blocks user completion (except stub)
        if code not in exclude:
            if pytest_b is False:
                hard_fails.append({
                    "check": "pytest_b_fail",
                    "detail": "Level B test failed — no successful transition from initial state",
                    "backend": "tests/processes/test_all_processes_level_b.py",
                    "frontend": "",
                    "fix": "Fix transition rules/context so level B passes",
                })
            if pytest_c is False:
                hard_fails.append({
                    "check": "pytest_c_fail",
                    "detail": "Level C test failed — cannot reach terminal or second transition",
                    "backend": "tests/processes/test_all_processes_level_c.py",
                    "frontend": "",
                    "fix": "Fix multi-step path so level C passes",
                })

        user_can_complete = len(hard_fails) == 0 and code not in exclude

        section = classify_process(fails, partial, sop_unmapped, sop_steps, user_can_complete)

        for f in hard_fails:
            ck = f.get("check", "unknown")
            blocker_counter[ck] += 1
            blocker_processes[ck].append(code)
            if ck not in blocker_samples:
                blocker_samples[ck] = f.get("fix", "")

        processes_out.append({
            "code": code,
            "name_fa": name_fa,
            "excluded_from_score": code in exclude,
            "sop_steps": sop_steps,
            "sop_mapped": sop_mapped,
            "sop_unmapped": sop_unmapped,
            "sop_fully_mapped": len(sop_unmapped) == 0 and len(sop_steps) > 0,
            "fails": fails,
            "partial_ui": partial,
            "user_can_complete": user_can_complete,
            "section": section,
            "pytest": {"level_a": pytest_a, "level_b": pytest_b, "level_c": pytest_c},
            "implementation": {
                "total_pct": impl.get("total_pct"),
                "uncovered_roles": impl.get("uncovered_roles"),
                "forms_pct": impl.get("forms_pct"),
            },
        })

    scored = [p for p in processes_out if not p["excluded_from_score"]]
    pass_count = sum(1 for p in scored if p["user_can_complete"])
    scored_count = len(scored)
    readiness_pct = round(100 * pass_count / scored_count, 1) if scored_count else 0.0

    sections = {"A": [], "B": [], "C": []}
    for p in processes_out:
        if p["excluded_from_score"]:
            continue
        sections[p["section"]].append(p["code"])

    top_blockers = sorted(
        [
            {
                "check": ck,
                "count": cnt,
                "processes": blocker_processes[ck],
                "sample_fix": blocker_samples.get(ck, ""),
            }
            for ck, cnt in blocker_counter.most_common(20)
        ],
        key=lambda x: (-x["count"], x["check"]),
    )

    report = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "process_count": len(processes_out),
            "scored_process_count": scored_count,
            "pass_count": pass_count,
            "readiness_pct": readiness_pct,
            "excluded_from_score": sorted(exclude),
            "pytest_run": args.run_pytest or bool(args.pytest_json),
        },
        "sections": sections,
        "top_blockers": top_blockers,
        "operator_visibility_summary": visibility_report.get("summary"),
        "processes": processes_out,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(build_markdown(report), encoding="utf-8")

    print(f"Customer Acceptance Readiness: {readiness_pct}% ({pass_count}/{scored_count})")
    print(f"Section A: {len(sections['A'])} | B: {len(sections['B'])} | C: {len(sections['C'])}")
    print(f"JSON: {OUT_JSON}")
    print(f"MD:   {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
