"""Shared helpers for flow-through scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
PROCESSES_DIR = ROOT / "metadata" / "processes"
PORTAL_MAP_PATH = ROOT / "metadata" / "portal_role_assigned_role_map.json"
ALT_PATHS_PATH = ROOT / "metadata" / "customer_acceptance_alternate_paths.json"
MATRIX_PATH = ROOT / "reports" / "flow_through" / "matrix.json"
ENRICHED_MATRIX_PATH = ROOT / "reports" / "flow_through" / "matrix_enriched.json"
GAPS_PATH = ROOT / "reports" / "flow_through" / "gaps.json"
PROMPTS_DIR = ROOT / "reports" / "flow_through" / "cursor_prompts"

ONBOARDING_DIR = ROOT / "reports" / "flow_through" / "onboarding"
ONBOARDING_MATRIX_PATH = ONBOARDING_DIR / "matrix.json"
ONBOARDING_ENRICHED_MATRIX_PATH = ONBOARDING_DIR / "matrix_enriched.json"
ONBOARDING_GAPS_PATH = ONBOARDING_DIR / "gaps.json"
ONBOARDING_PROMPTS_DIR = ONBOARDING_DIR / "cursor_prompts"

INTERVIEW_BOOK_TRIGGERS = frozenset({"timeslot_selected", "interview_time_selected"})


def load_portal_map() -> dict[str, Any]:
    if not PORTAL_MAP_PATH.is_file():
        return {}
    return json.loads(PORTAL_MAP_PATH.read_text(encoding="utf-8"))


def normalize_assigned_role(role: str | None, portal_data: dict[str, Any]) -> str:
    if not role:
        return ""
    typo = portal_data.get("normalize_assigned_role_typo") or {}
    return str(typo.get(role, role))


def role_to_portal_role(assigned_role: str, portal_data: dict[str, Any]) -> Optional[str]:
    ar = normalize_assigned_role(assigned_role, portal_data)
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


def load_wave_process_codes(wave: int) -> tuple[str, ...]:
    from app.meta.process_nav_order import _WAVE1_ORDER, _WAVE2_ORDER

    if wave == 1:
        return _WAVE1_ORDER
    if wave == 2:
        return _WAVE2_ORDER
    raise ValueError(f"Unsupported wave: {wave}")


def load_track_process_codes(track: str) -> tuple[str, ...]:
    from app.meta.process_nav_order import _WAVE1_ORDER, _WAVE2_ORDER, onboarding_process_codes

    t = (track or "wave1").strip().lower()
    if t in ("wave1", "1"):
        return _WAVE1_ORDER
    if t in ("wave2", "2"):
        return _WAVE2_ORDER
    if t == "onboarding":
        return onboarding_process_codes()
    raise ValueError(f"Unsupported track: {track}")


def matrix_paths_for_track(track: str) -> tuple[Path, Path, Path, Path]:
    """(matrix, enriched, gaps, prompts) for track."""
    t = (track or "wave1").strip().lower()
    if t == "onboarding":
        return (
            ONBOARDING_MATRIX_PATH,
            ONBOARDING_ENRICHED_MATRIX_PATH,
            ONBOARDING_GAPS_PATH,
            ONBOARDING_PROMPTS_DIR,
        )
    return MATRIX_PATH, ENRICHED_MATRIX_PATH, GAPS_PATH, PROMPTS_DIR


def load_process_json(process_code: str) -> dict[str, Any]:
    path = PROCESSES_DIR / f"{process_code}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def state_by_code(process_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s.get("code"): s for s in process_json.get("states") or [] if s.get("code")}


def terminal_states(process_json: dict[str, Any]) -> set[str]:
    return {
        s.get("code")
        for s in process_json.get("states") or []
        if s.get("type") == "terminal" and s.get("code")
    }


def forms_for_state(process_json: dict[str, Any], state_code: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for form in process_json.get("forms") or []:
        if not isinstance(form, dict):
            continue
        uis = form.get("used_in_state")
        if isinstance(uis, list):
            if state_code in uis:
                out.append(form)
        elif uis == state_code:
            out.append(form)
    return out


def field_spec(field: dict[str, Any]) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "name": field.get("name"),
        "type": (field.get("type") or "text").lower(),
        "label_fa": field.get("label_fa") or field.get("name"),
        "required": bool(field.get("required")),
    }
    if field.get("visible_if") is not None:
        spec["visible_if"] = field.get("visible_if")
    if field.get("required_if") is not None:
        spec["required_if"] = field.get("required_if")
    if field.get("options_source") is not None:
        spec["options_source"] = field.get("options_source")
    if field.get("options") is not None:
        spec["options"] = field.get("options")
    if field.get("columns") is not None:
        spec["columns"] = field.get("columns")
    if field.get("visible_to") is not None:
        spec["visible_to"] = field.get("visible_to")
    return spec


def step_id(row: dict[str, Any]) -> str:
    return (
        f"{row.get('process_code')}/{row.get('state_code')}"
        f"@{row.get('portal_role') or row.get('required_role')}"
    )
