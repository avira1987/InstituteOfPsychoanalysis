#!/usr/bin/env python3
"""Add record_* actions to process transitions for customer acceptance audit."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSES = ROOT / "metadata" / "processes"

RECORD_BY_PROCESS: dict[str, list[tuple[str, str, str]]] = {
    "theory_course_completion": [("grades_entry", "grades_submitted", "record_course_grades")],
    "skills_course_completion": [("grades_entry", "grades_submitted", "record_course_grades")],
    "film_observation_course_completion": [("grades_entry", "grades_submitted", "record_course_grades")],
    "live_supervision_course_completion": [("grades_entry", "grades_submitted", "record_course_grades")],
    "live_therapy_observation_course_completion": [("grades_entry", "grades_submitted", "record_course_grades")],
    "group_supervision_course_completion": [("grades_entry", "grades_submitted", "record_course_grades")],
    "film_observation_ta_attendance_completion": [("grades_entry", "grades_submitted", "record_course_grades")],
    "live_therapy_observation_ta_attendance_completion": [("grades_entry", "grades_submitted", "record_course_grades")],
    "live_supervision_ta_evaluation": [("evaluation_computed", "result_pass", "record_course_grades")],
    "class_attendance": [("attendance_list_ready", "attendance_submitted", "record_class_attendance")],
    "class_session_cancellation": [("cancellation_request", "cancellation_confirmed", "record_class_cancellation")],
    "full_education_leave": [("leave_request", "request_submitted", "record_leave_request")],
    "return_to_full_education": [("return_request", "request_submitted", "record_return_request")],
    "upgrade_to_educational_therapist": [("monitoring_review", "approved", "record_upgrade_decision")],
    "intern_bulk_patient_referral": [("coordination_followup", "coordination_followup_complete", "record_intern_referral")],
    "article_writing_completion": [("class_closed_student", "defense_requested", "record_article_milestone")],
    "live_therapy_observation_session_prep": [("coordination_pending", "time_registered", "record_session_prep")],
    "ta_instructor_leave": [("leave_request", "request_submitted", "record_ta_leave")],
}


def _ensure_action(transition: dict, record_type: str) -> None:
    actions = transition.setdefault("actions", [])
    if not isinstance(actions, list):
        actions = []
        transition["actions"] = actions
    for a in actions:
        if isinstance(a, dict) and a.get("type") == record_type:
            return
    actions.append({"type": record_type})


def patch_file(path: Path, specs: list[tuple[str, str, str]]) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for from_state, trigger, record_type in specs:
        for t in data.get("transitions") or []:
            if t.get("from") == from_state and t.get("trigger") == trigger:
                before = json.dumps(t.get("actions"), ensure_ascii=False)
                _ensure_action(t, record_type)
                after = json.dumps(t.get("actions"), ensure_ascii=False)
                if before != after:
                    changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def patch_student_evaluation() -> bool:
    path = PROCESSES / "student_instructor_evaluation.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    transitions = data.setdefault("transitions", [])
    for t in transitions:
        if t.get("trigger") == "deadline_reached":
            _ensure_action(t, "record_evaluation_closed")
    has_submit = any(t.get("trigger") == "evaluation_submitted" for t in transitions)
    if not has_submit:
        transitions.insert(0, {
            "from": "evaluation_open",
            "to": "evaluation_closed",
            "trigger": "evaluation_submitted",
            "required_role": "student",
            "description_fa": "ثبت فرم ارزیابی توسط دانشجو",
            "actions": [{"type": "record_evaluation_submission"}],
        })
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    return False


def main() -> None:
    patched = []
    for code, specs in RECORD_BY_PROCESS.items():
        p = PROCESSES / f"{code}.json"
        if not p.is_file():
            print(f"skip missing {code}")
            continue
        if patch_file(p, specs):
            patched.append(code)
    if patch_student_evaluation():
        patched.append("student_instructor_evaluation")
    # student cancellations — all confirm transitions
    for code in ("student_session_cancellation", "student_supervision_cancellation"):
        p = PROCESSES / f"{code}.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        ch = False
        for t in data.get("transitions") or []:
            if t.get("trigger") == "student_confirms" and t.get("from") == "sessions_selected":
                rt = "record_cancellation_applied" if "session" in code else "record_supervision_cancellation"
                before = json.dumps(t.get("actions"), ensure_ascii=False)
                _ensure_action(t, rt)
                if before != json.dumps(t.get("actions"), ensure_ascii=False):
                    ch = True
        if ch:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            patched.append(code)
    print("patched:", ", ".join(patched) or "(none)")


if __name__ == "__main__":
    main()
