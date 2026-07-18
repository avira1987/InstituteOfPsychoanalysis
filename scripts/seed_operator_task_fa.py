#!/usr/bin/env python3
"""Seed metadata.operator_task_fa for operator states in metadata/processes/*.json (idempotent)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
PROCESSES_DIR = ROOT / "metadata" / "processes"
MAP_PATH = ROOT / "metadata" / "portal_role_assigned_role_map.json"

EXCLUDE_ROLES = frozenset({"student", "applicant", "system"})

DEFAULT_OPERATOR_TASK_FA: dict[str, str] = {
    "therapist": "بررسی درخواست؛ فرم را تکمیل و دکمه تصمیم را بزنید.",
    "supervisor": "ثبت/بررسی جلسه سوپرویژن؛ سپس دکمه تأیید.",
    "admissions_officer": "بررسی مدارک/پرونده؛ تأیید، نقص، یا ادامه.",
    "interviewer": "ثبت نتیجه مصاحبه در فرم محرمانه.",
    "progress_committee": "بررسی پرونده و ثبت تصمیم جلسه.",
    "progress_committee_project": "بررسی پروژه و ثبت تصمیم کمیته پیشرفت.",
    "supervision_committee": "بررسی/صدور مجوز طبق دستور کار.",
    "instructor": "ثبت نمره/حضور/تأیید TA.",
    "teaching_assistant": "هماهنگی با مدرس؛ ثبت اطلاعات یا تأیید درخواست.",
    "teaching_assistant_or_instructor": "بررسی و ثبت تصمیم طبق نقش شما (مدرس یا TA).",
    "site_manager": "بررسی درخواست و ثبت تصمیم.",
    "deputy_education": "بررسی پرونده و تأیید یا ارجاع.",
    "deputy_education_director": "بررسی پرونده و ثبت تصمیم مدیریتی.",
    "education_committee": "بررسی پرونده در جلسه کمیته آموزش.",
    "course_committee": "بررسی موضوع در کمیته دروس.",
    "course_committee_scientific": "بررسی علمی و ثبت نظر.",
    "course_committee_executive": "هماهنگی اجرایی و ثبت تصمیم.",
    "scientific_officer_course_committee": "بررسی علمی و ثبت نظر.",
    "monitoring_committee_officer": "بررسی گزارش و ثبت اقدام.",
    "specialized_commission": "بررسی پرونده و ثبت رأی.",
    "therapy_committee_chair": "بررسی پرونده درمان و ثبت تصمیم.",
    "therapy_committee_executor": "اجرا و پیگیری تصمیم کمیته درمان.",
    "therapy_education_coordinator": "هماهنگی آموزش درمان و ثبت اطلاعات.",
}


def _load_typo_map() -> dict[str, str]:
    if not MAP_PATH.is_file():
        return {"admission_officer": "admissions_officer"}
    with MAP_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    return dict(raw.get("normalize_assigned_role_typo") or {})


def normalize_assigned_role(code: str | None, typo: dict[str, str]) -> str:
    if not code or not str(code).strip():
        return ""
    c = str(code).strip()
    return str(typo.get(c, c))


def default_task_for_role(role: str, typo: dict[str, str]) -> str:
    normalized = normalize_assigned_role(role, typo)
    if normalized in DEFAULT_OPERATOR_TASK_FA:
        return DEFAULT_OPERATOR_TASK_FA[normalized]
    return f"بررسی پرونده و ثبت اقدام لازم در این مرحله ({normalized or role})."


def seed_file(path: Path, typo: dict[str, str], dry_run: bool = False) -> tuple[int, int]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    changed = 0
    touched_states = 0
    for state in data.get("states") or []:
        role = normalize_assigned_role(state.get("assigned_role"), typo)
        if not role or role in EXCLUDE_ROLES:
            continue
        meta = state.setdefault("metadata", {})
        if not isinstance(meta, dict):
            meta = {}
            state["metadata"] = meta
        task = (meta.get("operator_task_fa") or "").strip()
        if not task:
            meta["operator_task_fa"] = default_task_for_role(role, typo)
            changed += 1
        short = (meta.get("operator_short_fa") or "").strip()
        name_fa = (state.get("name_fa") or "").strip()
        if not short and name_fa:
            meta["operator_short_fa"] = name_fa
            changed += 1
        touched_states += 1
    if changed and not dry_run:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return changed, touched_states


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    typo = _load_typo_map()
    total_changed = 0
    total_states = 0
    files_touched = 0
    for path in sorted(PROCESSES_DIR.glob("*.json")):
        n_changed, n_states = seed_file(path, typo, dry_run=dry_run)
        if n_changed:
            files_touched += 1
        total_changed += n_changed
        total_states += n_states
    mode = "dry-run" if dry_run else "write"
    print(
        f"seed_operator_task_fa ({mode}): "
        f"operator_states={total_states} fields_set={total_changed} files={files_touched}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
