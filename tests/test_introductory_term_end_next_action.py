"""گام بعدی پایان ترم دوره آشنایی — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "introductory_term_end.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "code",
    [
        "grades_submitted",
        "transcript_generated",
        "therapy_check",
        "therapy_blocked",
        "registration_notification_sent",
        "followup_in_progress",
        "followup_complete",
    ],
)
def test_intro_term_end_states_have_guidance(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code
