"""One-off extract for workflow_interprocess_gap_audit.md generation."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
index = json.loads((ROOT / "metadata/process_registry/INDEX.json").read_text(encoding="utf-8"))
sop_map = json.loads((ROOT / "metadata/process_registry/sop_step_mappings.json").read_text(encoding="utf-8"))

# Role -> portal mapping (static from admin-ui exploration)
ROLE_PORTAL = {
    "student": "StudentPortal (/panel/portal/student)",
    "applicant": "— (no dedicated portal; public registration)",
    "therapist": "TherapistPortal",
    "supervisor": "SupervisorPortal",
    "instructor": "StaffPortal / instruction lane",
    "teaching_assistant": "StaffPortal / instruction lane",
    "teaching_assistant_or_instructor": "StaffPortal / instruction lane",
    "admissions_officer": "StaffPortal / admissions lane",
    "admission_officer": "StaffPortal / admissions lane",
    "interviewer": "InterviewerPortal + StaffPortal/admissions",
    "site_manager": "SiteManagerPortal",
    "progress_committee": "CommitteePortal / progress",
    "education_committee": "CommitteePortal / education",
    "deputy_education": "CommitteePortal / education + SemesterPrep",
    "deputy_education_director": "CommitteePortal / education",
    "supervision_committee": "CommitteePortal / supervision",
    "specialized_commission": "CommitteePortal / supervision",
    "monitoring_committee_officer": "CommitteePortal / supervision",
    "therapy_committee_chair": "CommitteePortal / therapy",
    "therapy_committee_executor": "CommitteePortal / therapy",
    "therapy_education_coordinator": "StaffPortal / therapy-coord lane",
    "course_committee": "StaffPortal / course-committee lane",
    "course_committee_executive": "StaffPortal / course-committee + SemesterPrep",
    "course_committee_scientific": "StaffPortal / course-committee lane",
    "scientific_officer_course_committee": "StaffPortal / course-committee lane",
    "reference_center": "StaffPortal / content-ops lane",
    "marketing": "StaffPortal / content-ops lane",
    "finance": "FinancialDashboard only (no process inbox)",
    "staff": "StaffPortal (generic)",
    "admin": "Dashboard + all portals",
    "system": "— (automated; no human panel)",
}

# Process -> staff lane hint (from portalStaffLanes.js)
PROCESS_LANE = {
    "introductory_course_registration": "admissions",
    "comprehensive_course_registration": "admissions",
    "fall_semester_preparation": "course-committee",
    "winter_semester_preparation": "course-committee",
    "lesson_start_per_term": "instruction",
    "class_attendance": "instruction",
    "class_session_cancellation": "instruction",
    "theory_course_completion": "instruction",
    "skills_course_completion": "instruction",
    "film_observation_course_completion": "instruction",
    "live_therapy_observation_course_completion": "instruction",
    "live_supervision_course_completion": "instruction",
    "group_supervision_course_completion": "instruction",
    "ta_essay_upload": "content-ops / instruction",
    "ta_blog_content": "content-ops",
    "ta_conceptual_questions": "instruction",
    "live_therapy_observation_session_prep": "therapy-coord",
    "live_supervision_session_prep": "therapy-coord",
    "upgrade_to_ta": "course-committee / supervision committee",
    "ta_track_change": "course-committee",
    "intern_bulk_patient_referral": "therapy committee + supervision",
}

# Phase grouping
PHASES = {
    "P0_prep": ["fall_semester_preparation", "winter_semester_preparation"],
    "P1_admission": ["introductory_course_registration", "comprehensive_course_registration"],
    "P2_intro_terms": [
        "lesson_start_per_term", "class_attendance", "introductory_term_end",
        "intro_second_semester_registration", "introductory_course_completion",
        "student_instructor_evaluation",
    ],
    "P3_comprehensive": [
        "comprehensive_term_start", "comprehensive_term_end", "student_non_registration",
    ],
    "P4_therapy": [
        "start_therapy", "therapy_changes", "extra_session", "session_payment",
        "attendance_tracking", "fee_determination", "therapy_completion",
        "therapy_session_increase", "therapy_session_reduction", "therapy_early_termination",
        "specialized_commission_review", "committees_review", "therapist_session_cancellation",
        "unannounced_absence_reaction", "therapy_interruption", "student_session_cancellation",
    ],
    "P5_supervision": [
        "supervision_block_transition", "supervision_50h_completion", "supervision_session_increase",
        "extra_supervision_session", "supervision_session_reduction", "student_supervision_cancellation",
        "supervisor_session_cancellation", "unannounced_supervision_absence_reaction", "supervision_interruption",
    ],
    "P6_leave": [
        "educational_leave", "full_education_leave", "return_to_full_education", "process_merged_to_one",
    ],
    "P7_ta": [
        "ta_conceptual_questions", "ta_student_consultation", "ta_essay_upload", "ta_blog_content",
        "upgrade_to_ta", "mentor_private_sessions", "ta_to_assistant_faculty", "ta_to_instructor_auto",
        "ta_track_change", "ta_track_completion", "ta_instructor_leave", "class_attendance",
        "violation_registration", "class_session_cancellation", "student_instructor_evaluation",
    ],
    "P8_internship": [
        "internship_readiness_consultation", "internship_12month_conditional_review",
        "intern_hours_increase", "intern_bulk_patient_referral", "patient_referral",
        "live_therapy_observation_session_prep", "live_supervision_session_prep",
    ],
    "P9_completion": [
        "theory_course_completion", "skills_course_completion", "group_supervision_course_completion",
        "film_observation_course_completion", "live_therapy_observation_course_completion",
        "live_supervision_course_completion", "live_supervision_ta_evaluation",
        "film_observation_ta_attendance_completion", "live_therapy_observation_ta_attendance_completion",
        "article_writing_completion", "thesis_defense_request", "upgrade_to_educational_therapist",
    ],
}

code_to_phase = {}
for phase, codes in PHASES.items():
    for c in codes:
        code_to_phase[c] = phase

processes = []
for proc in index["processes"]:
    code = proc["code"]
    meta_path = ROOT / f"metadata/processes/{code}.json"
    if not meta_path.exists():
        continue
    sm = json.loads(meta_path.read_text(encoding="utf-8"))
    p = sm.get("process", {})
    states = sm.get("states", [])
    transitions = sm.get("transitions", [])

    child_refs = set(proc.get("sub_process_refs", []))
    for t in transitions:
        for a in t.get("actions", []) or []:
            at = a.get("type", "")
            if at in (
                "start_process", "start_sub_process", "call_bpms_subprocess",
                "redirect_to_process", "run_patient_referral", "refer_to_violation_registration",
            ):
                tgt = a.get("process_code") or a.get("sub_process_code")
                if not tgt and "violation" in at:
                    tgt = "violation_registration"
                if not tgt and "patient" in at:
                    tgt = "patient_referral"
                if tgt:
                    child_refs.add(tgt)

    workflow_lines = []
    for s in states:
        sc = s.get("code", "")
        role = s.get("assigned_role", "?")
        stype = s.get("type", "intermediate")
        meta = s.get("metadata") or {}
        task = meta.get("operator_task_fa") or meta.get("student_task_fa") or ""
        workflow_lines.append({
            "state": sc,
            "role": role,
            "type": stype,
            "task_fa": (task[:120] + "…") if len(task) > 120 else task,
        })

    reg_path = ROOT / f"metadata/process_registry/processes/{code}"
    processes.append({
        "code": code,
        "name_fa": proc.get("name_fa") or p.get("name_fa", ""),
        "sop_order": proc.get("sop_order"),
        "phase": code_to_phase.get(code, "P_other"),
        "initial_state": p.get("initial_state"),
        "initial_role": p.get("initial_role"),
        "roles_needed": proc.get("roles_needed", []),
        "sub_process_refs": sorted(child_refs),
        "workflow": workflow_lines,
        "state_count": len(states),
        "has_01": (reg_path / "01_input.md").exists(),
        "has_04": (reg_path / "04_status.md").exists(),
        "in_sop_mapping": code in sop_map.get("processes", {}),
        "staff_lane": PROCESS_LANE.get(code),
        "role_portals": {r: ROLE_PORTAL.get(r, f"? portal for {r}") for r in proc.get("roles_needed", [])},
    })

# patient_referral
pr_path = ROOT / "metadata/processes/patient_referral.json"
if pr_path.exists():
    sm = json.loads(pr_path.read_text(encoding="utf-8"))
    p = sm.get("process", {})
    states = sm.get("states", [])
    processes.append({
        "code": "patient_referral",
        "name_fa": p.get("name_fa", "ارجاع بیمار"),
        "sop_order": None,
        "phase": "P8_internship",
        "initial_state": p.get("initial_state"),
        "initial_role": p.get("initial_role"),
        "roles_needed": list({s.get("assigned_role") for s in states if s.get("assigned_role")}),
        "sub_process_refs": [],
        "workflow": [{"state": s.get("code"), "role": s.get("assigned_role"), "type": s.get("type"), "task_fa": ""} for s in states],
        "state_count": len(states),
        "has_01": False,
        "has_04": False,
        "in_sop_mapping": False,
        "staff_lane": None,
        "role_portals": {},
        "no_registry_folder": True,
    })

# Reverse index: who starts whom
started_by = {p["code"]: [] for p in processes}
for p in processes:
    for child in p.get("sub_process_refs", []):
        if child in started_by:
            started_by[child].append(p["code"])

for p in processes:
    p["started_by"] = sorted(started_by.get(p["code"], []))

out = ROOT / "_workflow_audit_extract.json"
out.write_text(json.dumps({"processes": processes, "phase_labels": {
    "P0_prep": "فاز ۰ — آماده‌سازی ترم",
    "P1_admission": "فاز ۱ — پذیرش و ثبت‌نام",
    "P2_intro_terms": "فاز ۲ — ترم‌های آشنایی",
    "P3_comprehensive": "فاز ۳ — چرخه جامع",
    "P4_therapy": "فاز ۴ — درمان آموزشی",
    "P5_supervision": "فاز ۵ — سوپرویژن",
    "P6_leave": "فاز ۶ — مرخصی و بازگشت",
    "P7_ta": "فاز ۷ — کمک‌مدرس / مدرس / تخلف",
    "P8_internship": "فاز ۸ — کارورزی و ارجاع بیمار",
    "P9_completion": "فاز ۹ — تکمیل دروس و فارغ‌التحصیلی",
    "P_other": "سایر",
}}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(processes)} processes to {out}")
