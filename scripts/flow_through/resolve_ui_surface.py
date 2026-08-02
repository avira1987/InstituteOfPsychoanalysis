#!/usr/bin/env python3
"""Resolve UI surface (layer, component, deep link) for each flow-through row."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.flow_through.common import (
    ALT_PATHS_PATH,
    ENRICHED_MATRIX_PATH,
    MATRIX_PATH,
    matrix_paths_for_track,
)

# Wave-1 process custom UI mapping (from codebase audit)
STUDENT_CUSTOM_PANELS: dict[str, dict[str, str]] = {
    "introductory_course_registration": {
        "component": "StudentIntroductoryCourseRegistrationPanel + InterviewSlotPicker + SepPaymentPanel",
        "portal_page": "StudentPortal",
    },
    "comprehensive_course_registration": {
        "component": "StudentComprehensiveCourseRegistrationPanel + InterviewSlotPicker + SepPaymentPanel",
        "portal_page": "StudentPortal",
    },
    "introductory_term_end": {
        "component": "StudentIntroductoryTermEndPanel",
        "portal_page": "StudentPortal",
    },
    "comprehensive_term_end": {
        "component": "StudentComprehensiveTermEndPanel",
        "portal_page": "StudentPortal",
    },
    "comprehensive_term_start": {
        "component": "StudentComprehensiveTermStartPanel",
        "portal_page": "StudentPortal",
    },
    "session_payment": {
        "component": "StudentSessionPaymentPanel",
        "portal_page": "StudentPortal",
    },
    "supervision_block_transition": {
        "component": "StudentSupervisionBlockTransitionPanel + SepPaymentPanel",
        "portal_page": "StudentPortal",
    },
    "class_attendance": {
        "component": "StudentClassAttendancePanel",
        "portal_page": "StudentPortal",
    },
    "start_therapy": {
        "component": "ProcessStepForms + SepPaymentPanel",
        "portal_page": "StudentPortal",
    },
    "thesis_defense_request": {
        "component": "StudentThesisDefenseRequestPanel",
        "portal_page": "StudentPortal",
    },
}

SEMESTER_PREP_CODES = frozenset({"fall_semester_preparation", "winter_semester_preparation"})

STAFF_LANE_BY_ROLE: dict[str, str] = {
    "admissions_officer": "admissions",
    "site_manager": "site",
    "instructor": "instruction",
    "teaching_assistant": "instruction",
    "course_committee": "course_committee",
    "course_committee_executive": "course_committee",
    "course_committee_scientific": "course_committee",
    "scientific_officer_course_committee": "course_committee",
}

PORTAL_ROUTE: dict[str, str] = {
    "student": "/panel/portal/student",
    "staff": "/panel/portal/staff/admissions",
    "therapist": "/panel/portal/therapist",
    "supervisor": "/panel/portal/supervisor",
    "site_manager": "/panel/portal/site-manager",
    "interviewer": "/panel/portal/interviewer",
    "deputy_education": "/panel/semester-prep",
    "course_committee": "/panel/semester-prep",
    "admissions_officer": "/panel/semester-prep",
    "committee": "/panel/portal/committee/education",
    "progress_committee": "/panel/portal/committee/progress",
    "education_committee": "/panel/portal/committee/education",
    "supervision_committee": "/panel/portal/committee/supervision",
    "admin": "/panel",
}


def _load_alt_paths() -> dict[str, Any]:
    if not ALT_PATHS_PATH.is_file():
        return {}
    return json.loads(ALT_PATHS_PATH.read_text(encoding="utf-8"))


def _alternate_for_state(alt: dict[str, Any], process_code: str, state_code: str) -> Optional[dict[str, Any]]:
    entry = (alt.get("form_alternate_paths") or {}).get(process_code)
    if not entry:
        return None
    states = entry.get("states")
    if states and state_code not in states:
        return None
    return entry


def _deep_link(
    row: dict[str, Any],
    ui_layer: str,
    portal_page: str,
) -> str:
    process_code = row["process_code"]
    state_code = row["state_code"]
    portal_role = row.get("portal_role") or ""

    if process_code in SEMESTER_PREP_CODES:
        return f"/panel/semester-prep/workbench?process_code={process_code}&state_code={state_code}"

    base = PORTAL_ROUTE.get(portal_role, "/panel")
    if portal_role == "staff":
        lane = STAFF_LANE_BY_ROLE.get(row.get("required_role") or "", "admissions")
        base = f"/panel/portal/staff/{lane}"

    params = [
        f"instance_id={{instance_id}}",
        f"student_id={{student_id}}",
        f"process_code={process_code}",
        f"state_code={state_code}",
    ]
    if portal_role == "student":
        return f"{base}?tab=processes"
    return f"{base}?{'&'.join(params)}"


def resolve_ui_surface(row: dict[str, Any], alt: dict[str, Any]) -> dict[str, Any]:
    process_code = row["process_code"]
    state_code = row["state_code"]
    portal_role = row.get("portal_role") or ""
    required_role = row.get("required_role") or ""
    has_forms = bool(row.get("has_forms"))

    alt_entry = _alternate_for_state(alt, process_code, state_code)
    if alt_entry:
        return {
            "ui_layer": "alternate",
            "ui_component": alt_entry.get("frontend") or alt_entry.get("mechanism") or "alternate",
            "portal_page": alt_entry.get("frontend", "").split("/")[-1].replace(".jsx", "") or portal_role,
            "deep_link_template": _deep_link(row, "alternate", portal_role),
            "ui_surface_ok": True,
        }

    if process_code in SEMESTER_PREP_CODES:
        return {
            "ui_layer": "operator_semester_prep",
            "ui_component": "SemesterPrepWorkbenchPage + OperatorStepFormsSection",
            "portal_page": "SemesterPrepWorkbenchPage",
            "deep_link_template": _deep_link(row, "operator_semester_prep", portal_role),
            "ui_surface_ok": True,
        }

    if portal_role == "student" or required_role in ("student", "applicant"):
        custom = STUDENT_CUSTOM_PANELS.get(process_code)
        if custom:
            return {
                "ui_layer": "custom_panel",
                "ui_component": custom["component"],
                "portal_page": custom["portal_page"],
                "deep_link_template": _deep_link(row, "custom_panel", custom["portal_page"]),
                "ui_surface_ok": True,
            }
        if has_forms or process_code in ("start_therapy",):
            return {
                "ui_layer": "student_generic",
                "ui_component": "ProcessStepForms (StudentQuestCard)",
                "portal_page": "StudentPortal",
                "deep_link_template": _deep_link(row, "student_generic", "StudentPortal"),
                "ui_surface_ok": True,
            }
        return {
            "ui_layer": "MISSING",
            "ui_component": "",
            "portal_page": "StudentPortal",
            "deep_link_template": _deep_link(row, "MISSING", "StudentPortal"),
            "ui_surface_ok": False,
        }

    # Operator / staff / therapist / etc.
    if process_code == "attendance_tracking" and portal_role in ("therapist", "site_manager"):
        page = "TherapistPortal" if portal_role == "therapist" else "SiteManagerPortal"
        return {
            "ui_layer": "custom_panel",
            "ui_component": f"TherapistAttendancePanel / SiteManager follow-up ({page})",
            "portal_page": page,
            "deep_link_template": _deep_link(row, "custom_panel", page),
            "ui_surface_ok": True,
        }

    if process_code == "thesis_defense_request" and portal_role in ("staff", "committee", "progress_committee"):
        return {
            "ui_layer": "custom_panel",
            "ui_component": "ThesisDefense*ReviewPanel",
            "portal_page": "StaffPortal or CommitteePortal",
            "deep_link_template": _deep_link(row, "custom_panel", "StaffPortal"),
            "ui_surface_ok": True,
        }

    if process_code == "class_attendance" and portal_role in ("staff", "instructor"):
        return {
            "ui_layer": "custom_panel",
            "ui_component": "InstructorClassAttendancePanel",
            "portal_page": "StaffPortal",
            "deep_link_template": _deep_link(row, "custom_panel", "StaffPortal"),
            "ui_surface_ok": True,
        }

    if has_forms:
        page = {
            "therapist": "TherapistPortal",
            "supervisor": "SupervisorPortal",
            "interviewer": "InterviewerPortal",
            "site_manager": "SiteManagerPortal",
            "committee": "CommitteePortal",
            "progress_committee": "CommitteePortal",
            "education_committee": "CommitteePortal",
            "supervision_committee": "CommitteePortal",
            "staff": "StaffPortal",
            "deputy_education": "SemesterPrepWorkbenchPage",
            "course_committee": "SemesterPrepWorkbenchPage",
            "admissions_officer": "SemesterPrepWorkbenchPage",
        }.get(portal_role, "OperatorProcessInstancePanel")
        return {
            "ui_layer": "operator_generic",
            "ui_component": f"OperatorStepFormsSection ({page})",
            "portal_page": page,
            "deep_link_template": _deep_link(row, "operator_generic", page),
            "ui_surface_ok": True,
        }

    # Transition-only (no form metadata) — still may have generic panel
    if portal_role in ("therapist", "supervisor", "interviewer", "staff", "site_manager"):
        page = {
            "therapist": "TherapistPortal",
            "supervisor": "SupervisorPortal",
            "interviewer": "InterviewerPortal",
            "staff": "StaffPortal",
            "site_manager": "SiteManagerPortal",
        }.get(portal_role, "StaffPortal")
        return {
            "ui_layer": "operator_generic",
            "ui_component": f"OperatorProcessInstancePanel ({page})",
            "portal_page": page,
            "deep_link_template": _deep_link(row, "operator_generic", page),
            "ui_surface_ok": True,
        }

    return {
        "ui_layer": "MISSING",
        "ui_component": "",
        "portal_page": "",
        "deep_link_template": "",
        "ui_surface_ok": False,
    }


def enrich_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    alt = _load_alt_paths()
    enriched_rows: list[dict[str, Any]] = []
    missing_count = 0
    for row in matrix.get("rows") or []:
        surface = resolve_ui_surface(row, alt)
        if not surface.get("ui_surface_ok"):
            missing_count += 1
        enriched_rows.append({**row, **surface})
    out = dict(matrix)
    out["rows"] = enriched_rows
    out["meta"] = {
        **(matrix.get("meta") or {}),
        "ui_missing_count": missing_count,
        "enriched": True,
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve UI surfaces for flow-through matrix")
    ap.add_argument("--track", type=str, default=None, help="Track: wave1, wave2, onboarding")
    ap.add_argument("--in", dest="in_path", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.in_path is None or args.out is None:
        matrix_path, enriched_path, _, _ = matrix_paths_for_track(args.track or "wave1")
        in_path = args.in_path or matrix_path
        out_path = args.out or enriched_path
    else:
        in_path = args.in_path
        out_path = args.out

    matrix = json.loads(in_path.read_text(encoding="utf-8"))
    enriched = enrich_matrix(matrix)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Enriched {enriched['meta'].get('row_count', len(enriched['rows']))} rows; "
        f"ui_missing={enriched['meta'].get('ui_missing_count', 0)} -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
