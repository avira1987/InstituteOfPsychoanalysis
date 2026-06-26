#!/usr/bin/env python3
"""Expand customer_acceptance_alternate_paths for all instructor/course processes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALT = ROOT / "metadata" / "customer_acceptance_alternate_paths.json"

INSTRUCTOR_PROCESSES = [
    "theory_course_completion",
    "skills_course_completion",
    "film_observation_course_completion",
    "live_supervision_course_completion",
    "live_therapy_observation_course_completion",
    "group_supervision_course_completion",
    "film_observation_ta_attendance_completion",
    "live_supervision_ta_evaluation",
    "live_therapy_observation_ta_attendance_completion",
    "class_attendance",
    "class_session_cancellation",
    "live_therapy_observation_session_prep",
    "ta_instructor_leave",
]

STAFF_PANEL = {
    "frontend": "admin-ui/src/components/OperatorProcessInstancePanel.jsx",
    "mechanism": "StaffPortal instruction lane + OperatorStepFormsSection + triggerTransition",
}

COMMITTEE_PANEL = {
    "frontend": "admin-ui/src/pages/CommitteePortal.jsx",
    "mechanism": "CommitteePortal + OperatorProcessInstancePanel",
}


def main() -> None:
    data = json.loads(ALT.read_text(encoding="utf-8"))
    forms = data.setdefault("form_alternate_paths", {})
    visibility = data.setdefault("student_result_visibility", {})

    for code in INSTRUCTOR_PROCESSES:
        entry = dict(STAFF_PANEL)
        entry["backend"] = "app/api/process/routes.py"
        if code.endswith("_course_completion") or code.endswith("_attendance_completion"):
            entry["states"] = ["grades_entry"]
        elif code == "class_attendance":
            entry["states"] = ["attendance_list_ready"]
        elif code == "class_session_cancellation":
            entry["states"] = ["cancellation_request"]
        elif code == "live_therapy_observation_session_prep":
            entry["states"] = ["coordination_pending", "patient_referral"]
        elif code == "ta_instructor_leave":
            entry["states"] = ["leave_request", "course_committee_review"]
        forms[code] = entry

    for code in INSTRUCTOR_PROCESSES:
        if code not in visibility:
            visibility[code] = {
                "frontend": "admin-ui/src/components/StudentCourseStatusPanel.jsx",
                "field": "extra_data.lms",
                "note_fa": "نمره/وضعیت درس پس از ثبت مدرس",
            }

    extra_forms = {
        "full_education_leave": {**STAFF_PANEL, "backend": "app/api/process/routes.py", "states": ["leave_request"]},
        "return_to_full_education": {"frontend": "admin-ui/src/pages/StudentPortal.jsx", "mechanism": "StudentQuestCard + ProcessStepForms"},
        "upgrade_to_educational_therapist": {**COMMITTEE_PANEL, "states": ["monitoring_review", "student_start"]},
        "intern_bulk_patient_referral": {**COMMITTEE_PANEL, "states": ["coordination_followup", "general_therapy_committee_review"]},
        "student_session_cancellation": forms.get("student_session_cancellation") or {"frontend": "admin-ui/src/pages/StudentPortal.jsx"},
        "student_supervision_cancellation": forms.get("student_supervision_cancellation") or {"frontend": "admin-ui/src/pages/StudentPortal.jsx"},
    }
    for k, v in extra_forms.items():
        forms.setdefault(k, v)

    for code in ("full_education_leave", "return_to_full_education", "upgrade_to_educational_therapist", "intern_bulk_patient_referral"):
        visibility.setdefault(code, {
            "frontend": "admin-ui/src/pages/StudentPortal.jsx",
            "note_fa": "وضعیت فرایند در پورتال دانشجو/کمیته",
        })

    visibility.setdefault("student_instructor_evaluation", {
        "frontend": "admin-ui/src/pages/StudentPortal.jsx",
        "note_fa": "فرم ارزیابی اختیاری در پنجره evaluation_open",
    })

    ALT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("updated alternate paths")


if __name__ == "__main__":
    main()
