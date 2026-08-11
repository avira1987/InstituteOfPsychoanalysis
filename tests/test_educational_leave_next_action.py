"""گام بعدی مرخصی آموزشی — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "educational_leave.json", encoding="utf-8") as f:
        return json.load(f)


def test_edu_leave_metadata_request_form():
    states = {s["code"]: s for s in _load()["states"]}
    meta = states["request_form"]["metadata"]
    assert meta.get("student_short_fa")
    assert meta.get("student_task_fa")
    assert meta.get("student_why_fa")


def test_edu_leave_wait_states_have_student_guidance():
    states = {s["code"]: s for s in _load()["states"]}
    for code in ("committee_review", "deputy_alerted", "committee_decision"):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_short_fa"), code
        assert meta.get("student_task_fa"), code
        assert meta.get("student_why_fa"), code


def test_build_student_guidance_request_form():
    definition = _load()
    detail = {"current_state": "request_form", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert out.get("why_fa")
    assert "مرخصی" in out["task_fa"] or "وقفه" in out["task_fa"]


@pytest.mark.parametrize("code", ["returned", "violation_registered"])
def test_edu_leave_terminal_states(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa")
    assert meta.get("student_task_fa")
    assert meta.get("student_why_fa")
