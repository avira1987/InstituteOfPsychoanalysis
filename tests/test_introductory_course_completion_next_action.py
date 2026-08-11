"""گام بعدی خاتمه دوره آشنایی — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "introductory_course_completion.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "code",
    [
        "all_courses_passed",
        "invitation_sent",
        "certificate_draft_generated",
        "certificate_review",
        "certificate_approved",
        "process_complete",
    ],
)
def test_intro_completion_states_have_guidance(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code
