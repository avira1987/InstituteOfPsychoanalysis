"""گام بعدی بازگشت به کل آموزش — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "return_to_full_education.json", encoding="utf-8") as f:
        return json.load(f)


def test_return_all_task_states_have_why():
    states = {s["code"]: s for s in _load()["states"]}
    for code, st in states.items():
        meta = st.get("metadata") or {}
        if meta.get("student_task_fa"):
            assert meta.get("student_why_fa"), f"missing why on {code}"


def test_build_student_guidance_therapy_payment_mentions_gateway():
    definition = _load()
    detail = {"current_state": "therapy_payment_pending", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "پرداخت" in out["task_fa"] or "درگاه" in out["task_fa"]
    assert out.get("why_fa")


@pytest.mark.parametrize("code", ["return_complete", "return_rejected"])
def test_return_terminal_states(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa")
    assert meta.get("student_task_fa")
    assert meta.get("student_why_fa")
