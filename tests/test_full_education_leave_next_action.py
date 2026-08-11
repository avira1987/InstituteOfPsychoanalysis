"""گام بعدی مرخصی از کل آموزش — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "full_education_leave.json", encoding="utf-8") as f:
        return json.load(f)


def test_full_leave_wait_states_have_guidance():
    states = {s["code"]: s for s in _load()["states"]}
    for code in ("committee_review", "deputy_alerted", "committee_decision"):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_task_fa"), code
        assert meta.get("student_why_fa"), code


def test_full_leave_all_states_with_task_have_why():
    states = {s["code"]: s for s in _load()["states"]}
    for code, st in states.items():
        meta = st.get("metadata") or {}
        if meta.get("student_task_fa"):
            assert meta.get("student_why_fa"), f"missing why on {code}"


def test_build_student_guidance_leave_request():
    definition = _load()
    detail = {"current_state": "leave_request", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert out.get("why_fa")


@pytest.mark.parametrize("code", ["leave_complete", "violation_registered"])
def test_full_leave_terminal_states(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa")
    assert meta.get("student_task_fa")
