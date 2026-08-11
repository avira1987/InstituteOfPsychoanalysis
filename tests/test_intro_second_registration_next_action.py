"""گام بعدی ثبت‌نام ترم دوم آشنایی — راهنمای دانشجو."""

import json
from pathlib import Path

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load_intro2_definition() -> dict:
    with open(PROCESSES_DIR / "intro_second_semester_registration.json", encoding="utf-8") as f:
        return json.load(f)


def test_intro2_metadata_has_short_and_task_on_key_states():
    definition = _load_intro2_definition()
    states = {s["code"]: s for s in definition["states"]}
    for code in (
        "course_selection",
        "payment_method",
        "payment_processing",
        "installment_overdue",
        "term2_registration_closed",
    ):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_short_fa"), f"missing student_short_fa on {code}"
        assert meta.get("student_task_fa"), f"missing student_task_fa on {code}"


def test_build_student_guidance_payment_processing_mentions_sep():
    definition = _load_intro2_definition()
    detail = {"current_state": "payment_processing", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "سپ" in out["task_fa"]


def test_build_student_guidance_installment_overdue_mentions_sep():
    definition = _load_intro2_definition()
    detail = {"current_state": "installment_overdue", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "سپ" in out["task_fa"] or "پرداخت" in out["task_fa"]
