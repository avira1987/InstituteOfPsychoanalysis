"""گام بعدی ثبت‌نام دوره آشنایی — راهنمای دانشجو و گیت."""

import json
from pathlib import Path

import pytest

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load_intro_definition() -> dict:
    with open(PROCESSES_DIR / "introductory_course_registration.json", encoding="utf-8") as f:
        return json.load(f)


def test_intro_metadata_has_short_and_task_on_key_states():
    definition = _load_intro_definition()
    states = {s["code"]: s for s in definition["states"]}
    for code in (
        "application_submitted",
        "course_selection",
        "payment",
        "registration_complete",
        "installment_overdue",
    ):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_short_fa"), f"missing student_short_fa on {code}"
        assert meta.get("student_task_fa"), f"missing student_task_fa on {code}"


def test_build_student_guidance_course_selection_portal_not_lms():
    definition = _load_intro_definition()
    detail = {"current_state": "course_selection", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "LMS" not in out["task_fa"]
    assert "همین صفحه" in out["task_fa"] or "پرتال" in out["task_fa"]


def test_build_student_guidance_installment_overdue_mentions_sep():
    definition = _load_intro_definition()
    detail = {"current_state": "installment_overdue", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "سپ" in out["task_fa"] or "پرداخت" in out["task_fa"]


def test_build_student_guidance_gate_closed_on_admission_result():
    definition = _load_intro_definition()
    detail = {"current_state": "result_full_admission", "is_completed": False}
    gate = {"allowed": False, "reason_fa": "ثبت‌نام ترم هنوز باز نشده."}
    out = build_student_guidance(
        definition,
        detail,
        [],
        [],
        step_form_locked=False,
        registration_gate=gate,
    )
    assert "ثبت‌نام ترم هنوز باز نشده" in out["task_fa"]


def test_build_student_guidance_context_override():
    definition = _load_intro_definition()
    detail = {
        "current_state": "result_full_admission",
        "is_completed": False,
        "context_data": {"student_next_action_fa": "متن سفارشی از موتور."},
    }
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert out["task_fa"] == "متن سفارشی از موتور."


def test_build_student_guidance_why_fa_from_metadata():
    definition = _load_intro_definition()
    detail = {"current_state": "application_submitted", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert out.get("why_fa")
    assert "رزرو" in out["why_fa"] or "پرداخت" in out["why_fa"]
