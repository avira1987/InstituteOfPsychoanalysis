"""گام بعدی خاتمه سوپرویژن گروهی — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "group_supervision_course_completion.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "code",
    [
        "awaiting_session_18",
        "session_18_pass_fail_entry",
        "pass_fail_applied",
        "ta_evaluation_entry",
        "qualitative_eval_pending",
        "grades_locked",
        "session_18_delay",
        "qualitative_eval_delay",
    ],
)
def test_group_supervision_states_have_guidance(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code
