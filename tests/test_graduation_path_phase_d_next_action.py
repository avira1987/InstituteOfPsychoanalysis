"""گام بعدی فرایندهای مرحله ۸–۱۰ — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"

PHASE_D = {
    "theory_course_completion": [
        "awaiting_session_18", "session_18_entry", "final_exam_open", "grades_locked",
    ],
    "skills_course_completion": [
        "awaiting_session_17", "session_18_grades_entry", "grades_locked",
    ],
    "film_observation_course_completion": ["grades_entry", "grades_locked", "delay_reported"],
    "live_therapy_observation_course_completion": ["grades_entry", "grades_locked"],
    "live_supervision_course_completion": [
        "sessions_in_progress", "mirror_implementation_pending", "completed",
    ],
    "thesis_defense_request": [
        "eligibility_check", "thesis_upload", "defense_passed", "revision_upload",
    ],
    "upgrade_to_educational_therapist": [
        "student_start", "therapist_selection", "et_availability_slots", "promotion_completed",
    ],
}


@pytest.mark.parametrize("process_code,state_code", [
    (proc, state) for proc, states in PHASE_D.items() for state in states
])
def test_phase_d_key_states_have_guidance(process_code: str, state_code: str):
    with open(PROCESSES_DIR / f"{process_code}.json", encoding="utf-8") as f:
        data = json.load(f)
    states = {s["code"]: s for s in data["states"]}
    meta = states[state_code].get("metadata") or {}
    assert meta.get("student_short_fa"), state_code
    assert meta.get("student_task_fa"), state_code
    assert meta.get("student_why_fa"), state_code
