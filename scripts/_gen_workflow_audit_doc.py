"""Generate docs/workflow_interprocess_gap_audit.md from _workflow_audit_extract.json."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "_workflow_audit_extract.json"
OUT = ROOT / "docs" / "workflow_interprocess_gap_audit.md"
AUDIT_MD = ROOT / "reports" / "customer_acceptance_audit.md"

# Known gaps from exploration (pre-filled per process code)
KNOWN_GAPS: dict[str, list[str]] = {
    "patient_referral": [
        "فاقد پوشه رجیستری در metadata/process_registry/processes/",
        "فاقد 04_status.md",
        "نگاشت SOP↔state↔UI ندارد",
    ],
    "process_merged_to_one": [
        "استاب — ادغام در educational_leave",
        "user_can_complete: NO در audit",
        "بدون ترنزیشن عملیاتی",
    ],
    "full_education_leave": [
        "audit: ۳ گام SOP بدون نگاشت",
        "UI دانشجو مشابه educational_leave — نیاز به تفکیک واضح‌تر",
    ],
    "theory_course_completion": [
        "audit: user_can_complete NO — action_missing start_sub_process",
        "stuck_state: grades_computed بدون خروجی",
    ],
    "skills_course_completion": [
        "audit: user_can_complete NO — action_missing + stuck_state",
    ],
    "group_supervision_course_completion": [
        "audit: user_can_complete NO — action_missing start_sub_process",
    ],
    "live_supervision_course_completion": [
        "audit: user_can_complete NO — action_missing start_sub_process",
    ],
    "ta_essay_upload": [
        "audit: user_can_complete NO — portal_missing برای marketing و reference_center",
        "۸ گام SOP بدون نگاشت",
    ],
    "upgrade_to_educational_therapist": [
        "audit: user_can_complete NO — stuck_state therapy_frequency_escalation",
        "فاقد نگاشت sop_step_mappings",
    ],
    "finance": [],  # not a process
    "start_therapy": [
        "UI توضیحی ضعیف برای week9_blocked",
        "۳ گام SOP بدون نگاشت در audit",
    ],
    "internship_readiness_consultation": [
        "تحویل سفته حضوری — فقط بنر دانشجو، بدون checkbox staff",
    ],
    "article_writing_completion": [
        "CTA دانشجو فعال؛ ارزیابی مدرس فقط staff",
    ],
    "fee_determination": [
        "۴ از ۵ گام SOP بدون نگاشت صریح",
        "زیرفرایند leaf — فقط از والد trigger می‌شود",
    ],
    "session_payment": [
        "۵ از ۶ گام SOP بدون نگاشت",
    ],
    "student_non_registration": [
        "۱۰ از ۱۷ گام SOP بدون نگاشت",
        "عمدتاً scheduler + committee",
    ],
    "film_observation_ta_attendance_completion": [
        "۱۵ از ۱۶ گام SOP بدون نگاشت",
    ],
    "ta_track_completion": [
        "۵ از ۵ گام SOP بدون نگاشت — عمدتاً سیستمی",
    ],
    "live_therapy_observation_ta_attendance_completion": [
        "فاقد نگاشت sop_step_mappings",
        "handoff به live_therapy_observation_course_completion — نیاز به تأیید end-to-end",
    ],
    "film_observation_ta_attendance_completion": [
        "handoff به film_observation_course_completion — نیاز به تأیید end-to-end",
    ],
    "live_supervision_ta_evaluation": [
        "handoff به live_supervision_course_completion",
    ],
    "intro_second_semester_registration": [
        "بدون operator_gap rule برای CTA دستی ترم ۲ (اختیاری)",
    ],
    "lesson_start_per_term": [
        "فقط scheduler — بدون CTA دستی اگر scheduler عقب بیفتد",
    ],
    "class_attendance": [
        "۷ گام SOP بدون نگاشت",
        "دانشجو فقط ویجت N/۵ — بدون اقدام مستقیم",
    ],
    "live_therapy_observation_session_prep": [
        "۳ از ۴ گام SOP بدون نگاشت",
        "handoff بین admissions و therapy-coord lane",
    ],
    "live_supervision_session_prep": [
        "۳ از ۴ گام SOP بدون نگاشت",
    ],
}

# Panel component hints (student / staff / committee)
PANEL_HINTS: dict[str, dict[str, str]] = {
    "theory_course_completion": {
        "student": "StudentTheoryCourseCompletionPanel",
        "instructor": "TheoryCourseCompletionPanel (instruction lane)",
    },
    "skills_course_completion": {
        "student": "StudentSkillsCourseCompletionPanel",
        "instructor": "SkillsCourseCompletionPanel",
    },
    "group_supervision_course_completion": {
        "student": "StudentGroupSupervisionCourseCompletionPanel",
        "instructor": "GroupSupervisionCourseCompletionPanel",
    },
    "film_observation_course_completion": {
        "student": "StudentFilmObservationCourseCompletionPanel",
        "instructor": "FilmObservationCourseCompletionPanel",
    },
    "live_therapy_observation_course_completion": {
        "student": "StudentLiveTherapyObservationCourseCompletionPanel",
        "instructor": "LiveTherapyObservationCourseCompletionPanel",
    },
    "live_supervision_course_completion": {
        "student": "StudentLiveSupervisionCoursePanel + MirrorWrite",
        "instructor": "LiveSupervisionCourseCompletionPanel",
    },
    "introductory_course_registration": {
        "student": "StudentQuestCard + InterviewSlotPicker + SepPaymentPanel",
        "admissions_officer": "StaffPortal/admissions + DocumentsReviewPanel",
        "interviewer": "InterviewerResultPanel",
    },
    "fall_semester_preparation": {
        "course_committee": "SemesterPrepWorkbenchPage",
        "deputy_education": "SemesterPrepWorkbenchPage",
        "site_manager": "SemesterPrepWorkbenchPage (interview slots)",
    },
    "violation_registration": {
        "supervision_committee": "ViolationRegistrationReviewPanel",
        "education_committee": "ViolationRegistrationReviewPanel",
    },
    "thesis_defense_request": {
        "student": "StudentThesisDefenseRequestPanel",
        "progress_committee": "ThesisDefenseProgressReviewPanel",
        "supervision_committee": "ThesisDefenseSupervisionReviewPanel",
        "education_committee": "ThesisDefenseEducationSchedulePanel",
    },
}

# Engine hooks (source -> mechanism -> target)
ENGINE_HOOKS = [
    ("introductory_course_registration", "engine hook", "proceed_to_documents", "introductory_registration_chaining"),
    ("lesson_start_per_term", "engine hook", "links_placed → ready", "lesson_start_chaining"),
    ("ta_track_change", "engine hook", "request_sent", "ta_track_change_chaining"),
    ("student_non_registration", "engine hook", "invitation_sent / branch deadlines", "student_non_registration_chaining"),
    ("intern_bulk_patient_referral", "engine hook", "patient_list_published", "intern_bulk_patient_referral_chaining"),
    ("therapy_changes", "engine hook", "propagate to absence/termination parents", "therapy_changes_chaining"),
    ("educational_leave / full_education_leave", "start_process hook", "leave_process_started", "student_non_registration (42)"),
    ("introductory_course_registration", "terminal hook", "registration_complete", "start_therapy"),
    ("start_therapy", "terminal hook", "therapy_active", "session_payment"),
    ("session_payment", "terminal hook", "completed", "repoint primary instance"),
    ("upgrade_to_ta", "post-transition", "ta_registered", "ta_upgrade_service.chain_after_transition"),
    ("ta_to_assistant_faculty", "post-transition", "—", "ta_to_assistant_faculty_service.chain_after_transition"),
    ("comprehensive_term_start / intro_second_semester_registration", "post-transition", "courses_selected", "student_non_registration advance"),
    ("return_to_full_education", "post-transition", "therapy payment / unlock", "branch_after_therapy_payment"),
]

SCHEDULER_STARTS = [
    ("student_instructor_evaluation", "academic_term_batch", "پنجره ارزیابی استاد"),
    ("comprehensive_term_start", "academic_term_batch", "ثبت‌نام ترم جامع"),
    ("student_non_registration", "academic_term_batch", "عدم ثبت‌نام"),
    ("lesson_start_per_term", "academic_term_batch", "شروع درس هر ترم"),
    ("intern_hours_increase", "student_milestones", "افزایش ساعات کارورزی"),
    ("internship_12month_conditional_review", "student_milestones", "بررسی ۱۲ ماهه انترن"),
    ("ta_to_instructor_auto", "student_milestones", "ارتقای خودکار TA→مدرس"),
    ("ta_to_assistant_faculty", "student_milestones", "ارتقای TA→دستیار آموزشی"),
    ("ta_student_consultation", "lms_session_hooks", "مشاوره دانشجو با TA"),
    ("mentor_private_sessions", "lms_session_hooks", "جلسات خصوصی منتور"),
    ("class_attendance", "lms_session_hooks", "حضور کلاس"),
    ("start_therapy", "start_therapy_week9", "دسته هفته ۹"),
    ("theory_course_completion", "calendar dispatch", "جلسه ۱۸"),
    ("skills_course_completion", "calendar dispatch", "جلسات ۱۷/۱۸"),
]

HUB_PROCESSES = {
    "violation_registration": "هاب تخلف — ~۲۵ فرایند والد",
    "fee_determination": "هاب مالی جلسه — attendance، cancellation، supervision",
    "patient_referral": "هاب ارجاع بیمار — leave، interruption، intern",
    "session_payment": "پرداخت جلسه — start_therapy، supervision_block، extra_supervision",
    "supervision_50h_completion": "تکمیل ۵۰h — increase، extra، supervisor cancellation",
    "attendance_tracking": "حضور درمان — extra_session، therapist cancellation",
    "committees_review": "کمیته‌ها — early termination، specialized reject",
    "educational_leave": "مرخصی — non_registration، process_merged_to_one",
}


def load_audit_failures() -> dict[str, str]:
    if not AUDIT_MD.exists():
        return {}
    text = AUDIT_MD.read_text(encoding="utf-8")
    failures: dict[str, str] = {}
    for line in text.splitlines():
        if "|" not in line or line.startswith("|---") or "Process |" in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            continue
        code = parts[1]
        can = parts[5]
        missing = parts[4] if len(parts) > 4 else ""
        if can == "**NO**" or "NO" in can:
            failures[code] = missing
    return failures


def infer_gaps(proc: dict, audit_failures: dict[str, str]) -> list[str]:
    code = proc["code"]
    gaps: list[str] = list(KNOWN_GAPS.get(code, []))
    if not proc.get("has_04"):
        gaps.append("فاقد 04_status.md در رجیستری")
    if not proc.get("has_01") and proc.get("sop_order"):
        gaps.append("فاقد 01_input.md / 02_flowchart در رجیستری")
    if not proc.get("in_sop_mapping") and "course_completion" in code:
        gaps.append("فاقد نگاشت در sop_step_mappings.json")
    if proc.get("no_registry_folder"):
        gaps.append("فاقد پوشه process_registry")
    if code in audit_failures:
        gaps.append(f"audit user_can_complete: NO — {audit_failures[code][:100]}")
    if not proc.get("staff_lane") and any(
        r in proc.get("roles_needed", [])
        for r in ("instructor", "teaching_assistant", "admissions_officer", "course_committee_executive")
    ):
        if code not in ("start_therapy", "therapy_changes"):
            gaps.append("staff lane در portalStaffLanes.js صریح تعریف نشده — ممکن است deep-link به StudentTracker برود")
    # dedupe
    seen: set[str] = set()
    out: list[str] = []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out if out else ["— (نیاز به بررسی دستی)"]


def status_icon(gaps: list[str]) -> str:
    if gaps == ["— (نیاز به بررسی دستی)"]:
        return "❓"
    joined = " ".join(gaps)
    if "user_can_complete: NO" in joined or "استاب" in joined:
        return "🔴"
    if any(x in joined for x in ("فاقد", "بدون", "ضعیف", "فقط scheduler", "NO")):
        return "🟡"
    return "✅"


def render_process_block(proc: dict, audit_failures: dict[str, str]) -> str:
    code = proc["code"]
    sop = proc.get("sop_order")
    sop_label = f"SOP {sop}" if sop else "بدون شماره SOP"
    gaps = infer_gaps(proc, audit_failures)
    icon = status_icon(gaps)
    panels = PANEL_HINTS.get(code, {})

    lines = [
        f"#### `{code}` ({sop_label}) — {icon}",
        "",
        f"- **نام:** {proc.get('name_fa', '')}",
        f"- **فاز:** {proc.get('phase', '')}",
        f"- **وضعیت اولیه:** `{proc.get('initial_state')}` | **نقش اولیه:** `{proc.get('initial_role')}`",
        f"- **تعداد state:** {proc.get('state_count')}",
        f"- **رجیستری:** 01_input={proc.get('has_01')} | 04_status={proc.get('has_04')} | sop_mapping={proc.get('in_sop_mapping')}",
        "",
        "**نقش‌ها و پنل:**",
    ]
    for role in proc.get("roles_needed", []):
        portal = proc.get("role_portals", {}).get(role, "?")
        panel = panels.get(role, "ProcessStepForms / OperatorProcessInstancePanel / QuestCard")
        lines.append(f"- `{role}` → {portal} | پنل: {panel}")

    if proc.get("staff_lane"):
        lines.append(f"- **Staff lane پیشنهادی:** `{proc['staff_lane']}`")

    lines.extend(["", "**ورودی (started_by):**"])
    started = proc.get("started_by") or []
    if started:
        lines.append(", ".join(f"`{s}`" for s in started))
    else:
        lines.append("- دستی / scheduler / شروع اولیه مسیر")

    lines.extend(["", "**خروجی (sub_process_refs / chaining):**"])
    outs = proc.get("sub_process_refs") or []
    if outs:
        lines.append(", ".join(f"`{s}`" for s in outs))
    else:
        lines.append("- — (leaf یا بدون زیرفرایند)")

    lines.extend(["", "**گردش کار (state → نقش):**"])
    for w in proc.get("workflow", [])[:12]:
        task = f" — {w['task_fa']}" if w.get("task_fa") else ""
        lines.append(f"- `{w['state']}` → `{w['role']}` ({w.get('type', '')}){task}")
    if len(proc.get("workflow", [])) > 12:
        lines.append(f"- … و {len(proc['workflow']) - 12} state دیگر")

    lines.extend(["", "**نواقص / یادداشت:**"])
    for g in gaps:
        lines.append(f"- [ ] {g}")

    lines.append("")
    return "\n".join(lines)


def build_chaining_table(processes: list[dict]) -> str:
    rows = []
    for p in processes:
        for child in p.get("sub_process_refs", []):
            rows.append((p["code"], "transition action (metadata)", child))
    for src, mech, tgt, note in [
        (h[0], h[1], h[2] if len(h) > 2 else "", h[3] if len(h) > 3 else "")
        for h in ENGINE_HOOKS
    ]:
        rows.append((src, mech, tgt or note))
    for pcode, mech, note in SCHEDULER_STARTS:
        rows.append(("process_scheduler", mech, pcode, note))

    # dedupe sort
    seen = set()
    out_lines = [
        "| منبع | مکانیزم | مقصد | یادداشت |",
        "|------|---------|------|---------|",
    ]
    for row in sorted(rows, key=lambda r: (r[0], r[2] if len(r) > 2 else "")):
        key = row[:3]
        if key in seen:
            continue
        seen.add(key)
        src, mech, tgt = row[0], row[1], row[2]
        note = row[3] if len(row) > 3 else ""
        out_lines.append(f"| `{src}` | {mech} | `{tgt}` | {note} |")
    return "\n".join(out_lines)


def main() -> None:
    data = json.loads(EXTRACT.read_text(encoding="utf-8"))
    processes: list[dict] = data["processes"]
    phase_labels: dict[str, str] = data["phase_labels"]
    audit_failures = load_audit_failures()

    by_phase: dict[str, list[dict]] = defaultdict(list)
    for p in processes:
        by_phase[p.get("phase", "P_other")].append(p)
    for phase in by_phase:
        by_phase[phase].sort(key=lambda x: (x.get("sop_order") or 999, x["code"]))

    today = date.today().isoformat()
    parts: list[str] = [
        "# ممیزی گردش کار بین‌فرایندی و نواقص اتوماسیون",
        "",
        f"**نسخه:** 1.0  ",
        f"**تاریخ:** {today}  ",
        "**هدف:** نقشه جامع گردش کار، ارتباط بین‌فرایندی، وظایف هر نقش در پنل‌ها، و چک‌لیست نواقص — از آماده‌سازی ترم تا فارغ‌التحصیلی.",
        "",
        "**مکمل (نه جایگزین):**",
        "- [`docs/student_lifecycle_ui_gaps_automation.md`](student_lifecycle_ui_gaps_automation.md) — تمرکز UI مسیر دانشجو",
        "- [`metadata/process_registry/GAPS.json`](../metadata/process_registry/GAPS.json) — وضعیت فنی رسمی",
        "- [`reports/customer_acceptance_audit.md`](../reports/customer_acceptance_audit.md) — ممیزی پذیرش (Readiness ~91.8%)",
        "",
        "---",
        "",
        "## بخش ۰ — راهنما و نمادها",
        "",
        "### نحوه استفاده",
        "",
        "هر بلوک فرایند در **بخش ۲** یک واحد قابل‌تحویل است. پس از رفع هر نقص:",
        "1. چک‌باکس همان بند را تیک بزنید",
        "2. در صورت نیاز `04_status.md` همان فرایند را به‌روز کنید",
        "3. `GAPS.json` / `INDEX.json` را هماهنگ نگه دارید (قانون process-registry)",
        "4. `python scripts/audit_customer_acceptance.py` را اجرا کنید",
        "",
        "### نماد وضعیت",
        "",
        "| نماد | معنی |",
        "|------|------|",
        "| ✅ | کامل — گردش کار، پنل، و handoff مشخص و عملیاتی |",
        "| 🟡 | جزئی — UI/workflow/chaining ناقص اما workaround دارد |",
        "| 🔴 | ناقص — مسیر مسدود یا audit=user_can_complete NO |",
        "| ⚪ | سیستمی — اقدام انسانی در پنل لازم نیست (scheduler/backend) |",
        "| ❓ | نیاز به بررسی دستی — هنوز ارزیابی نشده |",
        "",
        "### نقشه پنل‌ها (خلاصه)",
        "",
        "| نقش | پنل / مسیر |",
        "|------|------------|",
        "| student | [`StudentPortal.jsx`](../admin-ui/src/pages/StudentPortal.jsx) |",
        "| therapist | [`TherapistPortal.jsx`](../admin-ui/src/pages/TherapistPortal.jsx) |",
        "| supervisor | [`SupervisorPortal.jsx`](../admin-ui/src/pages/SupervisorPortal.jsx) |",
        "| interviewer | [`InterviewerPortal.jsx`](../admin-ui/src/pages/InterviewerPortal.jsx) |",
        "| site_manager | [`SiteManagerPortal.jsx`](../admin-ui/src/pages/SiteManagerPortal.jsx) |",
        "| staff lanes | [`StaffPortal.jsx`](../admin-ui/src/pages/StaffPortal.jsx) — admissions / instruction / content-ops / therapy-coord / course-committee |",
        "| committees | [`CommitteePortal.jsx`](../admin-ui/src/pages/CommitteePortal.jsx) — progress / education / supervision / therapy |",
        "| semester prep | [`SemesterPrepWorkbenchPage.jsx`](../admin-ui/src/pages/SemesterPrepWorkbenchPage.jsx) |",
        "| finance | [`FinancialDashboard.jsx`](../admin-ui/src/pages/FinancialDashboard.jsx) — بدون process inbox |",
        "| applicant | مسیر عمومی ثبت‌نام — بدون portal اختصاصی |",
        "| system | خودکار — [`engine.py`](../app/core/engine.py) + scheduler |",
        "",
        "**Deep-link:** [`operatorFollowupDeepLinks.js`](../admin-ui/src/utils/operatorFollowupDeepLinks.js) — fallback نهایی: `StudentTracker`",
        "",
        "---",
        "",
        "## بخش ۱ — نقشه چرخه حیات (فازها)",
        "",
        "```mermaid",
        "flowchart TB",
        "  subgraph P0 [فاز0 آماده‌سازی]",
        "    fallPrep[fall_semester_preparation]",
        "    winterPrep[winter_semester_preparation]",
        "  end",
        "  subgraph P1 [فاز1 پذیرش]",
        "    introReg[introductory_course_registration]",
        "    compReg[comprehensive_course_registration]",
        "  end",
        "  subgraph P2 [فاز2 ترم آشنایی]",
        "    lessonStart[lesson_start_per_term]",
        "    introEnd[introductory_term_end]",
        "    introSem2[intro_second_semester_registration]",
        "  end",
        "  subgraph P3 [فاز3 جامع]",
        "    compStart[comprehensive_term_start]",
        "    nonReg[student_non_registration]",
        "  end",
        "  subgraph P4 [فاز4 درمان]",
        "    startTherapy[start_therapy]",
        "    sessionPay[session_payment]",
        "    attendance[attendance_tracking]",
        "  end",
        "  subgraph P5 [فاز5 سوپرویژن]",
        "    sup50[supervision_50h_completion]",
        "    blockTrans[supervision_block_transition]",
        "  end",
        "  subgraph P8 [فاز8 کارورزی]",
        "    internReady[internship_readiness_consultation]",
        "    patientRef[patient_referral]",
        "  end",
        "  subgraph P9 [فاز9 تکمیل]",
        "    courseComp[course_completion x6]",
        "    thesis[thesis_defense_request]",
        "  end",
        "  subgraph Hubs [هاب‌های مشترک]",
        "    violation[violation_registration]",
        "    fee[fee_determination]",
        "  end",
        "  fallPrep --> introReg",
        "  introReg --> lessonStart",
        "  introSem2 --> startTherapy",
        "  startTherapy --> sessionPay",
        "  compStart --> courseComp",
        "  courseComp --> thesis",
        "  attendance --> fee",
        "  manyProcesses[چندین فرایند] --> violation",
        "  leaveProcesses[مرخصی/وقفه] --> patientRef",
        "```",
        "",
        "### فهرست فرایندها به تفکیک فاز",
        "",
    ]

    phase_order = [
        "P0_prep", "P1_admission", "P2_intro_terms", "P3_comprehensive",
        "P4_therapy", "P5_supervision", "P6_leave", "P7_ta",
        "P8_internship", "P9_completion", "P_other",
    ]
    for phase in phase_order:
        procs = by_phase.get(phase, [])
        if not procs:
            continue
        label = phase_labels.get(phase, phase)
        codes = ", ".join(f"`{p['code']}`" for p in procs)
        parts.append(f"- **{label}:** {codes}")
        parts.append("")

    parts.extend([
        "---",
        "",
        "## بخش ۲ — ماتریس فرایند × نقش × پنل × handoff",
        "",
        f"**تعداد فرایندها:** {len(processes)} (شامل زیرفرایند `patient_referral`)",
        "",
    ])

    for phase in phase_order:
        procs = by_phase.get(phase, [])
        if not procs:
            continue
        label = phase_labels.get(phase, phase)
        parts.append(f"### {label}")
        parts.append("")
        for proc in procs:
            parts.append(render_process_block(proc, audit_failures))

    parts.extend([
        "---",
        "",
        "## بخش ۳ — نقشه ارتباط بین‌فرایندی (Chaining Map)",
        "",
        "### دیاگرام هاب‌ها",
        "",
        "```mermaid",
        "flowchart LR",
        "  subgraph parents [فرایندهای والد]",
        "    cancel[student_session_cancellation]",
        "    leave[educational_leave]",
        "    earlyTerm[therapy_early_termination]",
        "    courseDone[theory_course_completion]",
        "  end",
        "  subgraph hubs [هاب‌ها]",
        "    violation[violation_registration]",
        "    fee[fee_determination]",
        "    patient[patient_referral]",
        "    pay[session_payment]",
        "    sup50[supervision_50h_completion]",
        "  end",
        "  cancel --> fee",
        "  cancel --> violation",
        "  leave --> patient",
        "  leave --> violation",
        "  earlyTerm --> violation",
        "  earlyTerm --> committees_review",
        "  blockTrans[supervision_block_transition] --> pay",
        "  extraSup[extra_supervision_session] --> pay",
        "  extraSup --> sup50",
        "  filmTA[film_observation_ta_attendance_completion] --> filmComp[film_observation_course_completion]",
        "  liveTA[live_therapy_observation_ta_attendance_completion] --> liveComp[live_therapy_observation_course_completion]",
        "  liveSupTA[live_supervision_ta_evaluation] --> liveSupComp[live_supervision_course_completion]",
        "  introReg2[intro_second_semester_registration] --> startTherapy[start_therapy]",
        "  startTherapy --> pay",
        "```",
        "",
        "### هاب‌های مرکزی",
        "",
    ])
    for code, desc in HUB_PROCESSES.items():
        parts.append(f"- `{code}` — {desc}")
    parts.append("")
    parts.append("### جدول handoff (منبع → مکانیزم → مقصد)")
    parts.append("")
    parts.append(build_chaining_table(processes))
    parts.extend([
        "",
        "### حلقه‌های مشکوک / گمشده (نیاز به بررسی)",
        "",
        "- [ ] `patient_referral` — JSON اجرایی دارد اما پوشه `process_registry` ندارد",
        "- [ ] `process_merged_to_one` — استاب؛ همه مسیرها باید به `educational_leave` هدایت شوند",
        "- [ ] `start_sub_process` — audit گزارش action_missing برای theory/skills/group/live_supervision completion",
        "- [ ] `grades_computed` stuck_state — theory و skills completion",
        "- [ ] `therapy_frequency_escalation` stuck_state — upgrade_to_educational_therapist",
        "- [ ] فرایندهای فقط-scheduler بدون CTA دستی: lesson_start_per_term، comprehensive_term_start، class_attendance",
        "- [ ] deep-link fallback به StudentTracker برای فرایندهای بدون staff_lane",
        "- [ ] نقش‌های marketing / reference_center — portal اختصاصی ندارند (ta_essay_upload)",
        "- [ ] finance — بدون process inbox؛ فقط FinancialDashboard",
        "- [ ] applicant — بدون portal؛ تبدیل به student پس از ثبت‌نام",
        "- [ ] LMS بیرونی — extra_data داخلی واقعی است؛ sync دوطرفه اختیاری (GAPS.json)",
        "- [ ] TA attendance completion → course completion — end-to-end دستی تأیید شود",
        "",
        "---",
        "",
        "## بخش ۴ — کاتالوگ نواقص (اولویت‌دار)",
        "",
        "### ۴.۱ شکاف پوشش پنل / نقش",
        "",
        "| اولویت | نقص | فرایند / نقش | اقدام پیشنهادی |",
        "|--------|-----|--------------|----------------|",
        "| بالا | portal_missing | ta_essay_upload → marketing, reference_center | lane content-ops یا نقش staff |",
        "| بالا | بدون portal | applicant | مسیر عمومی + تبدیل نقش پس از پذیرش |",
        "| متوسط | inbox ندارد | finance | اتصال process inbox یا deep-link مالی |",
        "| متوسط | deep-link نامطمئن | فرایندهای بدون staff_lane | گسترش portalStaffLanes.js |",
        "| متوسط | تفکیک UI ضعیف | full_education_leave | هم‌تراز با educational_leave + audit |",
        "| پایین | توضیح block | start_therapy week9_blocked | بنر/راهنمای علت مسدودیت |",
        "",
        "### ۴.۲ شکاف اتوماسیون / chaining",
        "",
        "| اولویت | نقص | جزئیات |",
        "|--------|-----|--------|",
        "| بالا | action_missing | start_sub_process در ۴ فرایند course completion |",
        "| بالا | stuck_state | grades_computed، therapy_frequency_escalation |",
        "| بالا | استاب | process_merged_to_one |",
        "| متوسط | scheduler-only | lesson_start، term_start، class_attendance — بدون CTA دستی |",
        "| متوسط | silent pass | edge paths در scheduler/chaining — لاگ و retry |",
        "| پایین | payment callback | BUILD_TODO § و — session_payment از gateway |",
        "",
        "### ۴.۳ شکاف نگاشت SOP ↔ state ↔ UI",
        "",
        f"- فقط **۶** فرایند در [`sop_step_mappings.json`](../metadata/process_registry/sop_step_mappings.json)",
        f"- **{sum(1 for p in processes if p.get('has_01'))}** فرایند دارای `01_input.md`",
        f"- **{sum(1 for p in processes if p.get('has_04'))}** فرایند دارای `04_status.md`",
        "- فرایندهای با بیشترین SOP unmapped (از audit): student_non_registration، film_observation_ta_attendance_completion، ta_instructor_leave",
        "",
        "### ۴.۴ شکاف SLA / اعلان",
        "",
        "- BUILD_TODO § ج-۲ — قالب SLA deputy_education در sla_monitor",
        "- BUILD_TODO § ب — activate_therapy، block_class_access در action_handler",
        "- BUILD_TODO § د — قوانین hours/week در engine context",
        "",
        "### ۴.۵ شکاف داده / LMS",
        "",
        "- همگام‌سازی دوطرفه LMS بیرونی (GAPS.json remaining_gaps)",
        "- قوانین وابسته به extra_data واقعی دانشجو — پر بودن پروفایل",
        "",
        "### ۴.۶ فرایندهای audit=user_can_complete NO",
        "",
    ])
    for code, detail in sorted(audit_failures.items()):
        parts.append(f"- [ ] `{code}` — {detail[:200]}")
    if not audit_failures:
        parts.append("- (از audit استخراج نشد)")

    parts.extend([
        "",
        "### ۴.۷ اولویت پیشنهادی تکمیل (ترتیب کار)",
        "",
        "| # | کار | تلاش | اثر |",
        "|---|-----|------|-----|",
        "| 1 | رفع start_sub_process + stuck_state در course completions | بالا | رفع ۴ فرایند NO |",
        "| 2 | portal marketing/reference_center برای ta_essay_upload | متوسط | رفع NO |",
        "| 3 | stuck_state upgrade_to_educational_therapist | متوسط | رفع NO |",
        "| 4 | حذف/redirect process_merged_to_one | کم | پاکسازی مسیر |",
        "| 5 | patient_referral registry folder + 04_status | کم | ثبات رجیستری |",
        "| 6 | CTA دستی scheduler-only processes | متوسط | UX اپراتور |",
        "| 7 | گسترش sop_step_mappings به فرایندهای پرتکرار | بالا | audit دقیق‌تر |",
        "| 8 | سفته انترn — checkbox staff | کم | کارورزی |",
        "",
        "---",
        "",
        "## بخش ۵ — روال به‌روزرسانی",
        "",
        "پس از رفع هر نقص در این سند:",
        "",
        "1. [ ] چک‌باکس بند مربوطه در **بخش ۲** یا **بخش ۴**",
        "2. [ ] به‌روزرسانی [`metadata/process_registry/processes/{code}/04_status.md`](../metadata/process_registry/processes/)",
        "3. [ ] در صورت بسته شدن شکاف فنی: [`GAPS.json`](../metadata/process_registry/GAPS.json) → `resolved_*`",
        "4. [ ] در صورت مسیر UI جدید: [`customer_acceptance_alternate_paths.json`](../metadata/customer_acceptance_alternate_paths.json)",
        "5. [ ] اجرا: `python scripts/audit_customer_acceptance.py`",
        "6. [ ] بررسی [`reports/customer_acceptance_audit.md`](../reports/customer_acceptance_audit.md)",
        "7. [ ] در صورت تغییر deep-link: [`operatorFollowupDeepLinks.js`](../admin-ui/src/utils/operatorFollowupDeepLinks.js)",
        "8. [ ] در صورت نقش/lane جدید: [`portalStaffLanes.js`](../admin-ui/src/utils/portalStaffLanes.js) + [`portalRoleNav.js`](../admin-ui/src/utils/portalRoleNav.js)",
        "",
        "### منابع حقیقت",
        "",
        "| منبع | مسیر |",
        "|------|------|",
        "| فهرست فرایندها | [`metadata/process_registry/INDEX.json`](../metadata/process_registry/INDEX.json) |",
        "| state machine | [`metadata/processes/*.json`](../metadata/processes/) |",
        "| موتور گردش کار | [`app/core/engine.py`](../app/core/engine.py) |",
        "| chaining | [`app/services/*_chaining.py`](../app/services/) |",
        "| scheduler | [`app/services/process_scheduler.py`](../app/services/process_scheduler.py) |",
        "| API پنل | [`app/api/panel_routes.py`](../app/api/panel_routes.py) |",
        "| ممیزی UI دانشجو | [`docs/student_lifecycle_ui_gaps_automation.md`](student_lifecycle_ui_gaps_automation.md) |",
        "",
        "---",
        "",
        f"*تولید خودکار اولیه: `scripts/_gen_workflow_audit_doc.py` — {today} — {len(processes)} فرایند*",
        "",
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {OUT} ({len(parts)} sections, ~{OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
