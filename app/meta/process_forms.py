"""Load form metadata from process JSON files (BUILD_TODO § ز — بخش ۷). Forms are not in DB."""

import json
from pathlib import Path
from typing import Optional

METADATA_PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


def _load_process_metadata(process_code: str) -> dict:
    path = METADATA_PROCESSES_DIR / f"{process_code}.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _normalize_field(field: dict) -> dict:
    normalized = dict(field)
    if "label_fa" not in normalized:
        normalized["label_fa"] = normalized.get("name") or normalized.get("code") or ""
    return normalized


def _normalize_form(form: dict) -> dict:
    normalized = dict(form)
    fields = normalized.get("fields")
    if isinstance(fields, list):
        normalized["fields"] = [
            _normalize_field(field) if isinstance(field, dict) else field
            for field in fields
        ]
        normalized["kind"] = "form"
    elif "kind" not in normalized:
        normalized["kind"] = "dashboard" if normalized.get("description_fa") else "form"
    return normalized


def get_process_forms(process_code: str, state_code: Optional[str] = None) -> list[dict]:
    """
    Load form definitions for a process from its JSON file.
    If state_code is given, return only forms whose used_in_state matches.
    """
    data = _load_process_metadata(process_code)
    forms = data.get("forms") or []
    if state_code is None:
        return [_normalize_form(f) for f in forms]
    return [_normalize_form(f) for f in forms if f.get("used_in_state") == state_code]


def get_process_ui_requirements(process_code: str) -> dict:
    """Load UI requirements for a process from its JSON file."""
    data = _load_process_metadata(process_code)
    ui_requirements = data.get("ui_requirements")
    return ui_requirements if isinstance(ui_requirements, dict) else {}
