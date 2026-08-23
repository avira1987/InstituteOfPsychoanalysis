#!/usr/bin/env python3
"""ممیزی درصد پیاده‌سازی واقعی هر فرایند (کد قابل‌استفاده، نه مستندات).

معیار جامع با تعریف «سخت‌گیرانه»:
  - اکشن‌ها (۴۰٪): فقط اکشن‌هایی که هندلر واقعی DB دارند پیاده‌سازی محسوب می‌شوند؛
    استاب‌های external_integration و اکشن‌های بدون هندلر = ناقص.
  - conditions/rules (۲۰٪): هر condition باید تعریف rule (expression) داشته باشد.
  - فرم/UI کاربرمحور (۲۵٪): stateهای دارای نقش انسانی که به ورودی نیاز دارند باید فرم داشته باشند.
  - پرتال نقش‌ها (۱۵٪): نقش‌های فرایند باید پرتال/پوشش UI داشته باشند.

خروجی: scripts/process_implementation_report.json + چاپ جدول.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSES_DIR = ROOT / "metadata" / "processes"
ACTION_HANDLER = ROOT / "app" / "services" / "action_handler.py"
ALL_RULES = ROOT / "metadata" / "rules" / "all_rules.json"
PORTAL_MAP = ROOT / "metadata" / "portal_role_assigned_role_map.json"
INDEX = ROOT / "metadata" / "process_registry" / "INDEX.json"

WEIGHTS = {"actions": 0.40, "rules": 0.20, "forms": 0.25, "portals": 0.15}

# اکشن‌هایی که بدون هیچ کاری «انجام‌شده» تلقی می‌شوند (بدون نیاز به هندلر اختصاصی)
ALWAYS_OK_ACTION_TYPES: set[str] = set()


STUB_HANDLER_NAME = "_handle_external_integration"


def action_registry() -> dict[str, str]:
    """action type -> handler function name, read from the live registry.

    Imported rather than regex-parsed so the audit keeps working no matter how
    ActionHandler is split across modules.
    """
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from app.services.action_handler import ActionHandler

    return {
        action_type: getattr(handler, "__name__", str(handler))
        for action_type, handler in ActionHandler._registry.items()
    }


def parse_action_registry(path: Path | None = None) -> tuple[set[str], set[str]]:
    """(actions with a real handler, actions still on the integration stub).

    `path` is accepted for backwards compatibility and ignored.
    """
    real, stub = set(), set()
    for action_type, handler_name in action_registry().items():
        if handler_name == STUB_HANDLER_NAME:
            stub.add(action_type)
        else:
            real.add(action_type)
    return real, stub


def load_defined_rules(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r.get("code") for r in data if r.get("code")}


def build_covered_roles(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    covered = {"system", "student", "applicant", "admin"}
    for _portal, cfg in data.get("portal_roles", {}).items():
        for r in cfg.get("assigned_roles", []) or []:
            covered.add(r)
    # admin شامل همهٔ نقش‌های اپراتوری است
    return covered


def normalize_role(role: str, norm_map: dict) -> str:
    return norm_map.get(role, role)


def audit_process(pj: dict, real: set[str], stub: set[str], defined_rules: set[str],
                  covered_roles: set[str], norm_map: dict) -> dict:
    states = pj.get("states", [])
    transitions = pj.get("transitions", [])
    forms = pj.get("forms", [])

    # ── محور ۱: اکشن‌ها ──
    action_types: list[str] = []
    for t in transitions:
        for a in t.get("actions", []) or []:
            at = a.get("type")
            if at:
                action_types.append(at)
    uniq_actions = set(action_types)
    real_actions = {a for a in uniq_actions if a in real or a in ALWAYS_OK_ACTION_TYPES}
    stub_actions = {a for a in uniq_actions if a in stub and a not in real_actions}
    missing_actions = {a for a in uniq_actions if a not in real and a not in stub}
    actions_score = (len(real_actions) / len(uniq_actions)) if uniq_actions else 1.0

    # ── محور ۲: rules/conditions ──
    cond_codes: set[str] = set()
    for t in transitions:
        for c in t.get("conditions", []) or []:
            cond_codes.add(c)
    defined = {c for c in cond_codes if c in defined_rules}
    undefined = cond_codes - defined
    rules_score = (len(defined) / len(cond_codes)) if cond_codes else 1.0

    # ── محور ۳: فرم/UI کاربرمحور ──
    form_states: set[str] = set()
    for f in forms:
        uis = f.get("used_in_state")
        if isinstance(uis, list):
            form_states.update(x for x in uis if x)
        elif uis:
            form_states.add(uis)
    # stateهای انسانی (نه system) که هدفِ یک transition با required_role غیرسیستمی هستند
    human_states = {}
    for s in states:
        role = s.get("assigned_role")
        if role and role != "system" and s.get("type") != "terminal":
            human_states[s.get("code")] = role
    # کدام stateهای انسانی واقعاً به ورودی کاربر نیاز دارند؟ آنهایی که transition خروجی
    # با required_role غیرسیستمی دارند (یعنی کاربر باید اکشن بزند/فرم پر کند)
    states_needing_input = set()
    for t in transitions:
        rr = t.get("required_role")
        frm = t.get("from")
        if rr and rr != "system" and frm in human_states:
            states_needing_input.add(frm)
    if not states_needing_input:
        forms_score = 1.0 if not human_states else 1.0
        covered_input_states = set()
    else:
        # یک state «پوشش‌داده‌شده» است اگر فرم دارد یا transition خروجی‌اش فرم لازم ندارد
        # (دکمهٔ عمومی triggerTransition کافی است). فرم فقط وقتی لازم است که آن state فرم تعریف‌شده دارد
        # یا state حاوی forms متادیتاست. اینجا سخت‌گیرانه: نیاز به وجود فرم یا متادیتای راهنمای دانشجو.
        covered_input_states = set()
        state_meta = {s.get("code"): s for s in states}
        for sc in states_needing_input:
            sm = state_meta.get(sc, {})
            meta = sm.get("metadata") or {}
            has_form = sc in form_states
            has_guidance = bool(meta.get("student_task_fa") or meta.get("student_short_fa"))
            if has_form or has_guidance:
                covered_input_states.add(sc)
        forms_score = len(covered_input_states) / len(states_needing_input)

    # ── محور ۴: پرتال نقش‌ها ──
    roles: set[str] = set()
    for s in states:
        r = s.get("assigned_role")
        if r:
            roles.add(normalize_role(r, norm_map))
    for t in transitions:
        r = t.get("required_role")
        if r:
            roles.add(normalize_role(r, norm_map))
    roles.discard("system")
    if not roles:
        portals_score = 1.0
        uncovered_roles = set()
    else:
        covered = {r for r in roles if r in covered_roles}
        uncovered_roles = roles - covered
        portals_score = len(covered) / len(roles)

    total = (
        WEIGHTS["actions"] * actions_score
        + WEIGHTS["rules"] * rules_score
        + WEIGHTS["forms"] * forms_score
        + WEIGHTS["portals"] * portals_score
    )

    return {
        "total_pct": round(total * 100, 1),
        "actions_pct": round(actions_score * 100, 1),
        "rules_pct": round(rules_score * 100, 1),
        "forms_pct": round(forms_score * 100, 1),
        "portals_pct": round(portals_score * 100, 1),
        "n_actions": len(uniq_actions),
        "real_actions": sorted(real_actions),
        "stub_actions": sorted(stub_actions),
        "missing_actions": sorted(missing_actions),
        "undefined_conditions": sorted(undefined),
        "uncovered_roles": sorted(uncovered_roles),
    }


def main() -> int:
    real, stub = parse_action_registry(ACTION_HANDLER)
    defined_rules = load_defined_rules(ALL_RULES)
    portal_data = json.loads(PORTAL_MAP.read_text(encoding="utf-8"))
    covered_roles = build_covered_roles(PORTAL_MAP)
    norm_map = portal_data.get("normalize_assigned_role_typo", {})

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    name_map = {p["code"]: p.get("name_fa", "") for p in index.get("processes", [])}

    results = {}
    for pf in sorted(PROCESSES_DIR.glob("*.json")):
        pj = json.loads(pf.read_text(encoding="utf-8"))
        code = pj.get("process", {}).get("code", pf.stem)
        res = audit_process(pj, real, stub, defined_rules, covered_roles, norm_map)
        res["name_fa"] = pj.get("process", {}).get("name_fa") or name_map.get(code, "")
        results[code] = res

    out = ROOT / "scripts" / "process_implementation_report.json"
    out.write_text(json.dumps({
        "meta": {
            "real_handler_action_types": sorted(real),
            "stub_action_types": sorted(stub),
            "weights": WEIGHTS,
            "n_processes": len(results),
        },
        "processes": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    ordered = sorted(results.items(), key=lambda kv: kv[1]["total_pct"], reverse=True)
    avg = sum(r["total_pct"] for _, r in ordered) / len(ordered)
    lines = [f"# گزارش پیاده‌سازی {len(ordered)} فرایند | میانگین کل: {avg:.1f}%", ""]
    lines.append(f"{'فرایند':<48} {'کل':>6} {'اکشن':>6} {'قانون':>6} {'فرم':>6} {'پرتال':>6}")
    lines.append("-" * 84)
    for code, r in ordered:
        lines.append(f"{code:<48} {r['total_pct']:>6} {r['actions_pct']:>6} {r['rules_pct']:>6} {r['forms_pct']:>6} {r['portals_pct']:>6}")
    report_txt = ROOT / "scripts" / "process_implementation_report.txt"
    report_txt.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nJSON: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
