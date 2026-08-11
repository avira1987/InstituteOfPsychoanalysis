"""گام بعدی آغاز درمان آموزشی — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load_start_therapy_definition() -> dict:
    with open(PROCESSES_DIR / "start_therapy.json", encoding="utf-8") as f:
        return json.load(f)


def test_start_therapy_metadata_has_short_and_task_on_key_states():
    definition = _load_start_therapy_definition()
    states = {s["code"]: s for s in definition["states"]}
    for code in (
        "eligibility_check",
        "therapist_selection",
        "first_session_24h_check",
        "payment_pending",
        "therapy_active",
    ):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_short_fa"), f"missing student_short_fa on {code}"
        assert meta.get("student_task_fa"), f"missing student_task_fa on {code}"
    assert "therapist_confirmation" not in states


def test_start_therapy_metadata_has_why_on_student_states():
    definition = _load_start_therapy_definition()
    states = {s["code"]: s for s in definition["states"]}
    for code in (
        "therapist_selection",
        "payment_pending",
        "therapy_active",
    ):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_why_fa"), f"missing student_why_fa on {code}"


def test_start_therapy_no_therapist_confirmation_gate():
    definition = _load_start_therapy_definition()
    transitions = definition["transitions"]
    assert not any(t.get("from") == "therapist_confirmation" for t in transitions)
    assert not any(t.get("trigger") in ("therapist_accepted", "therapist_declined") for t in transitions)
    selected = next(t for t in transitions if t.get("trigger") == "therapist_selected")
    assert selected["to"] == "first_session_24h_check"
    action_types = {a.get("type") for a in (selected.get("actions") or [])}
    assert "book_educational_therapist_slots" in action_types
    assert "apply_start_therapy_session_schedule" in action_types


def test_build_student_guidance_payment_pending_mentions_payment():
    definition = _load_start_therapy_definition()
    detail = {"current_state": "payment_pending", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "پرداخت" in out["task_fa"]
    assert out.get("why_fa")


def test_build_student_guidance_therapy_active_next_step():
    definition = _load_start_therapy_definition()
    states = {s["code"]: s for s in definition["states"]}
    meta = states["therapy_active"].get("metadata") or {}
    assert "جلسات آتی" in meta["student_task_fa"] or "پرداخت" in meta["student_task_fa"]
    detail = {"current_state": "therapy_active", "is_completed": True}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert out["short_fa"]
    assert meta.get("student_why_fa") == out.get("why_fa")


@pytest.mark.parametrize(
    "code",
    ["already_completed", "ineligible", "week9_blocked"],
)
def test_start_therapy_terminal_states_have_guidance(code: str):
    definition = _load_start_therapy_definition()
    states = {s["code"]: s for s in definition["states"]}
    meta = states[code].get("metadata") or {}
    assert meta.get("student_short_fa")
    assert meta.get("student_task_fa")
