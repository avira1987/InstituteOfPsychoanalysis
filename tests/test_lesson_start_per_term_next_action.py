"""گام بعدی آغاز درس در هر ترم — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "lesson_start_per_term.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "code",
    ["student_enrollment", "links_created", "attendance_list_ready", "lesson_active"],
)
def test_lesson_start_states_have_guidance(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code


def test_build_student_guidance_student_enrollment():
    definition = _load()
    detail = {"current_state": "student_enrollment", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert out.get("task_fa")
    assert out.get("why_fa")
