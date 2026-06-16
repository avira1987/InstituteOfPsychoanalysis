"""
ممیزی heuristics: مراحل با assigned_role اپراتوری — آیا متن راهنمای دانشجو یا فرم student دارند؟
خروجی برای گزارش JSON و اولویت‌بندی شکاف.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[2]
_PROCESSES = _REPO / "metadata" / "processes"
_MAP = _REPO / "metadata" / "portal_role_assigned_role_map.json"

_EXCLUDE = frozenset({"student", "applicant", "system"})


def _normalize_role(code: str | None) -> str:
    if not code or not str(code).strip():
        return ""
    c = str(code).strip()
    typo = {}
    if _MAP.is_file():
        with _MAP.open(encoding="utf-8") as f:
            raw = json.load(f)
            typo = raw.get("normalize_assigned_role_typo") or {}
    return str(typo.get(c, c))


def _staff_center_roles() -> frozenset[str]:
    if not _MAP.is_file():
        return frozenset()
    with _MAP.open(encoding="utf-8") as f:
        raw = json.load(f)
    pr = (raw.get("portal_roles") or {}).get("staff") or {}
    arr = pr.get("assigned_roles") or []
    return frozenset(_normalize_role(x) for x in arr if x)


def _state_has_student_form(process_data: dict, state_code: str) -> bool:
    for form in process_data.get("forms") or []:
        if not isinstance(form, dict):
            continue
        if form.get("used_in_state") != state_code:
            continue
        vis = form.get("visible_to")
        if isinstance(vis, list) and "student" in vis:
            return True
    return False


def _has_student_task_text(state: dict) -> bool:
    meta = state.get("metadata") if isinstance(state.get("metadata"), dict) else {}
    t = (meta.get("student_task_fa") or meta.get("student_short_fa") or "").strip()
    return bool(t)


def _transitions_from(process_data: dict, state_code: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tr in process_data.get("transitions") or []:
        if not isinstance(tr, dict):
            continue
        if (tr.get("from") or "").strip() != state_code:
            continue
        out.append(
            {
                "trigger": tr.get("trigger"),
                "to": tr.get("to"),
                "required_role": tr.get("required_role"),
            }
        )
    return out


def build_operator_student_visibility_report() -> dict[str, Any]:
    staff_roles = _staff_center_roles()
    rows: list[dict[str, Any]] = []
    for path in sorted(_PROCESSES.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        proc = data.get("process") or {}
        process_code = (proc.get("code") or path.stem) or ""
        process_name_fa = proc.get("name_fa") or process_code
        for st in data.get("states") or []:
            if not isinstance(st, dict):
                continue
            ar = _normalize_role(st.get("assigned_role"))
            if not ar or ar in _EXCLUDE:
                continue
            state_code = (st.get("code") or "").strip()
            state_name_fa = (st.get("name_fa") or "").strip()
            st_type = (st.get("type") or "").strip()
            has_form = _state_has_student_form(data, state_code)
            has_text = _has_student_task_text(st)
            is_staff_center = ar in staff_roles
            transitions = _transitions_from(data, state_code)
            # شکاف احتمالی: اپراتور مسئول است؛ دانشجو نه فرم دارد نه متن راهنما؛ مرحله غیر پایانی
            weak_student_surface = (not has_form) and (not has_text)
            needs_review = weak_student_surface and st_type != "terminal"
            severity = 0
            if needs_review:
                severity = 3 if is_staff_center else 1
            rows.append(
                {
                    "process_code": process_code,
                    "process_name_fa": process_name_fa,
                    "state_code": state_code,
                    "state_name_fa": state_name_fa,
                    "state_type": st_type,
                    "assigned_role": ar,
                    "is_staff_center_role": is_staff_center,
                    "has_student_form": has_form,
                    "has_student_task_text": has_text,
                    "transitions_out_count": len(transitions),
                    "transitions_out_sample": transitions[:5],
                    "needs_review": needs_review,
                    "severity": severity,
                }
            )

    needs = [r for r in rows if r.get("needs_review")]
    needs.sort(key=lambda x: (-(x.get("severity") or 0), x.get("process_name_fa") or "", x.get("state_code") or ""))
    prioritized = needs[:15]

    summary = {
        "total_operator_states": len(rows),
        "needs_review_count": len(needs),
        "staff_center_needs_review": len([r for r in needs if r.get("is_staff_center_role")]),
        "prioritized_gap_count": len(prioritized),
    }

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "prioritized_gaps": prioritized,
        "rows": rows,
    }
