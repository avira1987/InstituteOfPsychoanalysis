"""گام بعدی تکمیل ۵۰ ساعت سوپرویژن — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "supervision_50h_completion.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "code",
    [
        "session_scheduled",
        "recording_closed",
        "auto_absence_unpaid",
        "session_completed",
        "absence_recorded",
        "evaluation_completed",
        "evaluation_sla_breach",
    ],
)
def test_supervision_50h_student_visible_states(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code
