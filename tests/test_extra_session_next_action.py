"""گام بعدی جلسه اضافی درمان — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load() -> dict:
    with open(PROCESSES_DIR / "extra_session.json", encoding="utf-8") as f:
        return json.load(f)


def test_extra_session_student_states_have_why():
    states = {s["code"]: s for s in _load()["states"]}
    for code in ("extra_request", "student_response", "payment_required"):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_why_fa"), code


def test_extra_session_payment_gateway_short():
    states = {s["code"]: s for s in _load()["states"]}
    meta = states["payment_required"]["metadata"]
    assert "درگاه" in meta["student_short_fa"] or "درگاه" in meta["student_task_fa"]


def test_build_student_guidance_payment_required():
    definition = _load()
    detail = {"current_state": "payment_required", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "پرداخت" in out["task_fa"] or "درگاه" in out["task_fa"]
    assert out.get("why_fa")


@pytest.mark.parametrize("code", ["extra_request_rejected", "extra_session_cancelled"])
def test_extra_session_terminal_states(code: str):
    states = {s["code"]: s for s in _load()["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa")
    assert meta.get("student_task_fa")
    assert meta.get("student_why_fa")
