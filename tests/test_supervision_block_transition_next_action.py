"""گام بعدی انتقال بلوک سوپرویژن — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "supervision_block_transition.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "code",
    [
        "payment_intent_50th",
        "supervisor_slots_displayed",
        "slot_selected",
        "not_at_50th",
        "new_block_first_paid",
        "both_paid_completed",
    ],
)
def test_supervision_block_states_have_guidance(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code
