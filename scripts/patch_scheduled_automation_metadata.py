#!/usr/bin/env python3
"""Merge scheduled_automation blocks from index into metadata/processes/*.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "metadata" / "scheduled_automation_index.json"
PROC_DIR = ROOT / "metadata" / "processes"

SLA_STATE_PATCHES = {
    "theory_course_completion": ("grades_entry", 7),
    "skills_course_completion": ("grades_entry", 7),
    "group_supervision_course_completion": ("grades_entry", 7),
    "film_observation_course_completion": ("grades_entry", 7),
    "live_supervision_course_completion": ("mirror_implementation_pending", 5),
    "live_therapy_observation_course_completion": ("grades_entry", 7),
    "film_observation_ta_attendance_completion": ("grades_entry", 7),
    "live_therapy_observation_ta_attendance_completion": ("grades_entry", 7),
    "ta_student_consultation": ("ta_form_fill", 4),
    "article_writing_completion": [
        ("class_closed_student", 8),
        ("instructor_eval_pending", 4),
    ],
}


def main() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    processes = index.get("processes") or {}
    updated = 0
    for code, automation in processes.items():
        path = PROC_DIR / f"{code}.json"
        if not path.is_file():
            print(f"skip missing {path.name}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("scheduled_automation") != automation:
            data["scheduled_automation"] = automation
            updated += 1
        patch = SLA_STATE_PATCHES.get(code)
        if patch:
            states = data.get("states") or []
            if isinstance(patch, tuple):
                patch = [patch]
            for state_code, days in patch:
                for st in states:
                    if st.get("code") == state_code and st.get("sla_days") is None and st.get("sla_hours") is None:
                        st["sla_days"] = days
                        updated += 1
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"patched {code}")
    print(f"done ({updated} field updates)")


if __name__ == "__main__":
    main()
