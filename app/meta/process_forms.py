"""Load form metadata from process JSON files (BUILD_TODO § ز — بخش ۷). Forms are not in DB."""

import json
from pathlib import Path
from typing import Optional

METADATA_PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


def get_process_forms(process_code: str, state_code: Optional[str] = None) -> list[dict]:
    """
    Load form definitions for a process from its JSON file.
    If state_code is given, return only forms whose used_in_state matches.
    """
    path = METADATA_PROCESSES_DIR / f"{process_code}.json"
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    forms = data.get("forms") or []
    if state_code is None:
        return forms
    return [f for f in forms if f.get("used_in_state") == state_code]
