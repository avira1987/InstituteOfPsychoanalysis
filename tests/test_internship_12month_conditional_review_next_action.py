"""گام بعدی بررسی ۱۲ ماه انترنی مشروط — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "internship_12month_conditional_review.json", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "code",
    [
        "month_12_trigger",
        "supervision_review",
        "interview_scheduling",
        "interview_held",
        "result_unrestricted",
        "result_conditional",
        "supervision_rejected",
    ],
)
def test_internship_12month_states(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa"), code
    assert meta.get("student_task_fa"), code
    assert meta.get("student_why_fa"), code
