"""مرجع ثابت وظایف نقش‌ها و فرایندهای registry — برای صندوق پیگیری مدیر اصلی."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.meta.student_lifecycle_matrix import ROLE_ACTION_PATTERNS

from app.meta.role_labels import role_label_fa_only

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INDEX_PATH = _REPO_ROOT / "metadata" / "process_registry" / "INDEX.json"


def _label_role(role: str) -> str:
    return role_label_fa_only(role)


def build_reference_role_tasks() -> list[dict[str, Any]]:
    """نقش‌های اپراتوری (غیر دانشجو) + جملات الگو از ماتریس چرخه عمر."""
    out: list[dict[str, Any]] = []
    for role, tasks in sorted(ROLE_ACTION_PATTERNS.items()):
        if role == "student":
            continue
        titles = [t for t in (tasks or []) if isinstance(t, str) and t.strip()]
        if not titles:
            continue
        out.append(
            {
                "role_code": role,
                "role_label_fa": _label_role(role),
                "tasks": titles,
            }
        )
    return out


@lru_cache(maxsize=1)
def _load_index_json() -> dict[str, Any]:
    if not _INDEX_PATH.is_file():
        return {"processes": []}
    with _INDEX_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def build_reference_process_hints(max_rows: int = 50) -> list[dict[str, Any]]:
    """
    فرایندهایی که در INDEX نقش غیر دانشجو/سیستم دارند — حداکثر max_rows ردیف، مرتب‌شده بر نام فارسی.
    """
    data = _load_index_json()
    rows: list[dict[str, Any]] = []
    skip_roles = frozenset({"student", "system", "applicant"})
    for proc in data.get("processes") or []:
        code = proc.get("code")
        if not code:
            continue
        raw = proc.get("roles_needed") or []
        op_roles = [r for r in raw if r not in skip_roles]
        if not op_roles:
            continue
        rows.append(
            {
                "process_code": code,
                "name_fa": (proc.get("name_fa") or "").strip() or code,
                "roles_needed": op_roles,
            }
        )
    rows.sort(key=lambda x: x["name_fa"])
    return rows[:max_rows]


def build_reference_block() -> dict[str, Any]:
    return {
        "reference_role_tasks": build_reference_role_tasks(),
        "reference_process_hints": build_reference_process_hints(50),
    }
