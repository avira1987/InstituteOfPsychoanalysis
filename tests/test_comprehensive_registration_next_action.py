"""گام بعدی ثبت‌نام دوره جامع — راهنمای دانشجو."""

import json
from pathlib import Path

from app.services.student_tracker_summary import build_student_guidance

PROCESSES_DIR = Path(__file__).resolve().parents[1] / "metadata" / "processes"


def _load_comp_definition() -> dict:
    with open(PROCESSES_DIR / "comprehensive_course_registration.json", encoding="utf-8") as f:
        return json.load(f)


def test_comp_metadata_has_short_and_task_on_key_states():
    definition = _load_comp_definition()
    states = {s["code"]: s for s in definition["states"]}
    for code in (
        "application_submitted",
        "document_upload",
        "interview_scheduled",
        "payment",
        "registration_complete",
    ):
        meta = states[code].get("metadata") or {}
        assert meta.get("student_short_fa"), f"missing student_short_fa on {code}"
        assert meta.get("student_task_fa"), f"missing student_task_fa on {code}"


def test_build_student_guidance_interview_scheduled_portal_not_site():
    definition = _load_comp_definition()
    detail = {"current_state": "interview_scheduled", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "سایت" not in out["task_fa"] and "پیامک" not in out["task_fa"]
    assert "همین صفحه" in out["task_fa"] or "تقویم" in out["task_fa"]


def test_build_student_guidance_payment_mentions_sep():
    definition = _load_comp_definition()
    detail = {"current_state": "payment", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "سپ" in out["task_fa"] or "پرداخت" in out["task_fa"]
