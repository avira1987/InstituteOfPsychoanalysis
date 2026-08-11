"""گام بعدی مشورت آمادگی انترنی — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "internship_readiness_consultation.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "code",
    [
        "student_request",
        "contract_practice",
        "contract_rules",
        "promissory_note",
        "supervisor_selection",
        "first_session_payment",
    ],
)
def test_internship_readiness_actable_states(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code


def test_internship_first_session_payment_sep():
    states = {s["code"]: s for s in _load()["states"]}
    meta = states["first_session_payment"]["metadata"]
    assert "سپ" in meta["student_task_fa"]
