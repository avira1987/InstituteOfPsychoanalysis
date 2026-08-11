"""گام بعدی پرداخت جلسات آتی — راهنمای دانشجو."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load_session_payment_definition() -> dict:
    with open(PROCESSES_DIR / "session_payment.json", encoding="utf-8") as f:
        return json.load(f)


def test_session_payment_metadata_has_short_and_task_on_key_states():
    definition = _load_session_payment_definition()
    states = {s["code"]: s for s in definition["states"]}
    for code in (
        "payment_due",
        "payment_selection",
        "awaiting_payment",
        "payment_failed",
        "payment_confirmed",
        "session_suspended",
    ):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_short_fa"), f"missing student_short_fa on {code}"
        assert meta.get("student_task_fa"), f"missing student_task_fa on {code}"


def test_build_student_guidance_awaiting_payment_mentions_sep():
    definition = _load_session_payment_definition()
    detail = {"current_state": "awaiting_payment", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "سپ" in out["task_fa"] or "پرداخت" in out["task_fa"]
    assert out.get("why_fa")


def test_build_student_guidance_payment_failed_retry_sep():
    definition = _load_session_payment_definition()
    detail = {"current_state": "payment_failed", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "سپ" in out["task_fa"] or "پرداخت" in out["task_fa"]


def test_build_student_guidance_payment_confirmed_online_sessions():
    definition = _load_session_payment_definition()
    states = {s["code"]: s for s in definition["states"]}
    meta = states["payment_confirmed"].get("metadata") or {}
    assert "جلسات آنلاین" in meta["student_task_fa"] or "جلسات" in meta["student_task_fa"]
    detail = {"current_state": "payment_confirmed", "is_completed": True}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert out["short_fa"]
    assert meta.get("student_why_fa") == out.get("why_fa")
