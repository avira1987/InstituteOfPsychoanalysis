"""گام بعدی تکمیل درمان آموزشی — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "therapy_completion.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("code", ["initiated", "conditions_not_met", "therapy_completed"])
def test_therapy_completion_states_have_guidance(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code


def test_build_student_guidance_initiated():
    definition = _load()
    detail = {"current_state": "initiated", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert out.get("task_fa")
    assert out.get("why_fa")
