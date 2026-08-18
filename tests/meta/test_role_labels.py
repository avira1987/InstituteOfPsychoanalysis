"""تست برچسب فارسی نقش‌ها — metadata/role_labels_fa.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.meta.role_labels import (
    format_role_forbidden_message,
    label_role_fa,
    normalize_role_code,
    role_label_fa_only,
    role_labels_map,
)

ROOT = Path(__file__).resolve().parents[2]
PROCESSES_DIR = ROOT / "metadata" / "processes"


def _collect_process_roles() -> set[str]:
    roles: set[str] = set()
    for path in PROCESSES_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for state in data.get("states") or []:
            if state.get("assigned_role"):
                roles.add(str(state["assigned_role"]).strip())
    return {r for r in roles if r}


def test_course_committee_executive_label():
    assert label_role_fa("course_committee_executive") == (
        "مسئول اجرایی کمیته دروس (course_committee_executive)"
    )


def test_unknown_role_fallback():
    assert label_role_fa("unknown_role_xyz") == "نقش نامشخص (unknown_role_xyz)"


def test_typo_alias_admission_officer():
    assert normalize_role_code("admission_officer") == "admissions_officer"
    assert role_label_fa_only("admission_officer") == "مسئول پذیرش"


def test_all_process_assigned_roles_have_labels():
    labels = role_labels_map()
    aliases_path = ROOT / "metadata" / "role_labels_fa.json"
    aliases = json.loads(aliases_path.read_text(encoding="utf-8")).get("typo_aliases") or {}
    missing = []
    for code in _collect_process_roles():
        normalized = code
        if code in aliases:
            normalized = aliases[code]
        if normalized not in labels and code not in labels:
            missing.append(code)
    assert not missing, f"Missing role labels: {missing}"


def test_label_without_code():
    assert label_role_fa("staff", include_code=False) == "کارمند دفتر"
    assert label_role_fa("internal_manager", include_code=False) == "مدیر داخلی"


def test_format_role_forbidden_message():
    msg = format_role_forbidden_message(
        "staff", "admin", "deputy_education", "course_committee"
    )
    assert msg == (
        "نقش «کارمند دفتر» مجاز نیست. "
        "نقش‌های مجاز: مدیر سیستم، معاون مدیر آموزش، کمیته دروس"
    )
    assert label_role_fa("student", include_code=False) == "دانشجو"
