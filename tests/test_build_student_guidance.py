"""build_student_guidance: applicant همانند student برای متن پیش‌فرض."""

from app.services.student_tracker_summary import build_student_guidance


def test_build_student_guidance_applicant_with_forms_like_student():
    definition = {
        "process": {"description": "x"},
        "states": [
            {
                "code": "step_a",
                "name_fa": "گام آ",
                "assigned_role": "applicant",
                "metadata": {},
            }
        ],
    }
    detail = {"current_state": "step_a", "is_completed": False}
    forms = [
        {
            "code": "f1",
            "used_in_state": "step_a",
            "fields": [{"name": "n1", "label_fa": "فیلد", "type": "text", "required": True}],
        }
    ]
    out = build_student_guidance(definition, detail, [], forms, step_form_locked=False)
    assert "فرم" in out["task_fa"] or "تکمیل" in out["task_fa"]


def test_build_student_guidance_staff_role_not_applicant():
    definition = {
        "process": {},
        "states": [
            {
                "code": "staff_only",
                "name_fa": "فقط کارمند",
                "assigned_role": "admissions_officer",
                "metadata": {},
            }
        ],
    }
    detail = {"current_state": "staff_only", "is_completed": False}
    out = build_student_guidance(definition, detail, [], [], step_form_locked=False)
    assert "همکاران" in out["task_fa"] or "پنل" in out["task_fa"]
