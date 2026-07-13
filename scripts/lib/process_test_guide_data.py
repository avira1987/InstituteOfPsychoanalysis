"""Extract process test specs and cross-process links from metadata."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSES_DIR = ROOT / "metadata" / "processes"
INDEX_PATH = ROOT / "metadata" / "process_registry" / "INDEX.json"

RESTART_BLOCKED = frozenset({
    "fee_determination",
    "session_payment",
    "fall_semester_preparation",
    "winter_semester_preparation",
})

SCHEDULER_HEAVY_PROCESSES = frozenset({
    "class_attendance",
    "ta_to_instructor_auto",
    "ta_to_assistant_faculty",
    "ta_student_consultation",
    "mentor_private_sessions",
    "student_instructor_evaluation",
    "comprehensive_term_start",
    "student_non_registration",
    "lesson_start_per_term",
    "intern_hours_increase",
    "internship_12month_conditional_review",
    "ta_track_completion",
})

ROLE_FA: dict[str, str] = {
    "student": "دانشجو",
    "applicant": "متقاضی",
    "therapist": "درمانگر",
    "supervisor": "سوپروایزر",
    "staff": "کارمند",
    "admissions_officer": "مسئول پذیرش",
    "site_manager": "مسئول سایت",
    "interviewer": "مصاحبه‌گر",
    "instructor": "مدرس",
    "teaching_assistant": "کمک‌مدرس",
    "teaching_assistant_or_instructor": "کمک‌مدرس/مدرس",
    "progress_committee": "کمیته پیشرفت",
    "education_committee": "کمیته آموزش",
    "supervision_committee": "کمیته نظارت",
    "specialized_commission": "کمیسیون تخصصی",
    "therapy_committee_chair": "رئیس کمیته درمان",
    "therapy_committee_executor": "مجری کمیته درمان",
    "deputy_education": "معاون آموزش",
    "deputy_education_director": "معاون مدیر آموزش",
    "course_committee": "کمیته دروس",
    "course_committee_scientific": "کمیته علمی دروس",
    "course_committee_executive": "کمیته اجرایی دروس",
    "scientific_officer_course_committee": "مسئول علمی کمیته دروس",
    "monitoring_committee_officer": "مسئول کمیته نظارت",
    "therapy_education_coordinator": "هماهنگ‌کننده آموزش درمان",
    "system": "سامانه (خودکار)",
}

ROLE_PORTAL: dict[str, tuple[str, str, str]] = {
    "student": ("/panel/portal/student", "?tab=processes", "student1"),
    "applicant": ("/panel/portal/student", "?tab=processes", "regdemo_intro_app"),
    "therapist": ("/panel/portal/therapist", "?tab=pending", "therapist1"),
    "supervisor": ("/panel/portal/supervisor", "?tab=reviews", "supervisor1"),
    "staff": ("/panel/portal/staff/admissions", "?tab=pending", "staff1"),
    "admissions_officer": ("/panel/portal/staff/admissions", "?tab=pending", "demo_admissions"),
    "site_manager": ("/panel/portal/site-manager", "?tab=pending", "site_manager1"),
    "interviewer": ("/panel/portal/interviewer", "", "demo_interviewer"),
    "instructor": ("/panel/portal/staff/instruction", "?tab=pending", "staff1"),
    "teaching_assistant": ("/panel/portal/staff/instruction", "?tab=pending", "staff1"),
    "teaching_assistant_or_instructor": ("/panel/portal/staff/instruction", "?tab=pending", "staff1"),
    "progress_committee": ("/panel/portal/committee/progress", "?tab=reviews", "progress_committee1"),
    "education_committee": ("/panel/portal/committee/education", "?tab=reviews", "education_committee1"),
    "supervision_committee": ("/panel/portal/committee/supervision", "?tab=reviews", "supervision_committee1"),
    "specialized_commission": ("/panel/portal/committee/supervision", "?tab=reviews", "supervision_committee1"),
    "therapy_committee_chair": ("/panel/portal/committee/therapy", "?tab=reviews", "therapy_committee_chair1"),
    "therapy_committee_executor": ("/panel/portal/committee/therapy", "?tab=reviews", "therapy_committee_executor1"),
    "deputy_education": ("/panel/semester-prep", "", "deputy_education1"),
    "deputy_education_director": ("/panel/semester-prep", "", "deputy_education1"),
    "course_committee": ("/panel/portal/staff/course-committee", "?tab=pending", "course_committee1"),
    "course_committee_scientific": ("/panel/portal/staff/course-committee", "?tab=pending", "course_committee1"),
    "course_committee_executive": ("/panel/portal/staff/course-committee", "?tab=pending", "course_committee1"),
    "scientific_officer_course_committee": ("/panel/portal/staff/course-committee", "?tab=pending", "course_committee1"),
    "monitoring_committee_officer": ("/panel/portal/committee/supervision", "?tab=reviews", "monitoring_committee_officer1"),
    "therapy_education_coordinator": ("/panel/portal/staff/therapy-coord", "?tab=pending", "staff1"),
    "system": ("", "", ""),
}

PROCESS_PORTAL_OVERRIDE: dict[str, tuple[str, str, str]] = {
    "fall_semester_preparation": (
        "/panel/semester-prep/workbench?process_code=fall_semester_preparation",
        "",
        "deputy_education1",
    ),
    "winter_semester_preparation": (
        "/panel/semester-prep/workbench?process_code=winter_semester_preparation",
        "",
        "deputy_education1",
    ),
    "session_payment": ("/panel/portal/student", "?tab=processes", "student1"),
    "fee_determination": ("/panel/portal/student", "?tab=processes", "student1"),
    "student_instructor_evaluation": ("/panel/portal/student", "?tab=dashboard", "student1"),
    "comprehensive_term_start": ("/panel/portal/student", "?tab=processes", "student2"),
    "intro_second_semester_registration": ("/panel/portal/student", "?tab=processes", "student1"),
    "introductory_course_registration": ("/panel/portal/student", "?tab=processes", "regdemo_intro_app"),
    "comprehensive_course_registration": ("/panel/portal/student", "?tab=processes", "student2"),
}

LINK_TYPE_FA = {
    "spawn": "ایجاد فرایند جدید",
    "subprocess": "زیرفرایند",
    "redirect": "هدایت به فرایند دیگر",
    "prerequisite": "پیش‌نیاز",
    "registry": "ارجاع ثبت‌شده",
}

# نام منوی سایدبار — منبع: portalRoleNav.js، portalStaffLanes.js، portalCommitteeKinds.js
PATH_MENU_FA: dict[str, str] = {
    "/panel": "داشبورد",
    "/panel/portal/student": "پنل آموزشی",
    "/panel/portal/therapist": "پنل درمانگر",
    "/panel/portal/supervisor": "پنل سوپروایزر",
    "/panel/portal/interviewer": "پنل مصاحبه‌گر",
    "/panel/portal/site-manager": "پنل مسئول سایت",
    "/panel/portal/staff/admissions": "پنل پذیرش",
    "/panel/portal/staff/instruction": "پنل مدرس",
    "/panel/portal/staff/content-ops": "تولید محتوا",
    "/panel/portal/staff/therapy-coord": "هماهنگی درمان",
    "/panel/portal/staff/course-committee": "کمیته درس",
    "/panel/portal/committee/progress": "کمیته پیشرفت",
    "/panel/portal/committee/education": "کمیته آموزش",
    "/panel/portal/committee/supervision": "کمیته نظارت",
    "/panel/portal/committee/therapy": "کمیته درمان",
    "/panel/semester-prep/workbench": "مرحلهٔ آماده‌سازی ترم",
    "/panel/semester-prep/calendar": "تدوین تقویم آموزشی دو ترم",
    "/panel/semester-prep/course-list-review": "بازبینی و ویرایش لیست دروس ترم زمستان",
    "/panel/semester-prep/sla-warnings": "هشدارهای مهلت آماده‌سازی ترم",
    "/panel/semester-prep": "آماده‌سازی ترم",
    "/panel/automation-scheduler": "اتوماسیون زمان‌محور",
    "/panel/tickets": "تیکت‌ها و درخواست‌ها",
    "/panel/students": "ردیابی دانشجو",
    "/panel/reports": "گزارشات",
    "/panel/guide": "راهنمای جامع",
}

TAB_FA: dict[str, str] = {
    "processes": "فرایندها",
    "pending": "کارهای من",
    "reviews": "بررسی‌ها",
    "dashboard": "داشبورد",
    "documentsReview": "بررسی مدارک",
    "students": "دانشجویان",
    "interviewSlots": "وقت مصاحبه",
    "onlineClasses": "کلاس آنلاین",
    "all": "همه",
    "activity": "فعالیت‌ها",
}

# Enriched narrative overrides keyed by process_code
ENRICHMENT_OVERRIDES: dict[str, dict[str, Any]] = {
    "fall_semester_preparation": {
        "who": "مدیر سامانه (admin) یا معاون آموزش؛ برای زمان مصاحبه: مسئول سایت",
        "where": "منو → آماده‌سازی ترم → ادامه مرحله فعلی",
        "steps": [
            "با admin یا deputy_education1 وارد شوید.",
            "به آماده‌سازی ترم بروید؛ در صورت نیاز «شروع فرایند» را بزنید.",
            "مراحل: تقویم، شهریه، پروانه، لیست دروس، نهایی‌سازی، تبلیغات، مصاحبه‌گران، زمان‌بندی.",
            "برای زمان‌بندی مصاحبه با site_manager1 وارد شوید.",
            "تا وضعیت «انتشار» ادامه دهید.",
        ],
        "expect": "ترم پاییز منتشر شود؛ بدون انتشار ثبت‌نام آشنایی قفل می‌ماند.",
        "tips": ["اگر فرمی خالی ماند دکمه بعدی کار نمی‌کند.", "بعضی مراحل فقط برای یک نقش خاص است."],
    },
    "introductory_course_registration": {
        "who": "متقاضی/دانشجو؛ مصاحبه‌گر؛ مسئول پذیرش",
        "where": "پورتال دانشجو → داشبورد/فرایندها؛ مصاحبه‌گر → ثبت نتیجه؛ پذیرش → بررسی مدارک",
        "steps": [
            "با regdemo_intro_app فرم پذیرش را پر کنید.",
            "وقت مصاحبه و پرداخت مصاحبه را انجام دهید.",
            "با demo_interviewer نتیجه مصاحبه را ثبت کنید.",
            "با demo_admissions مدارک را تأیید کنید.",
            "دوباره دانشجو: مدارک، انتخاب درس، پرداخت شهریه.",
        ],
        "expect": "مسیر از درخواست تا ثبت‌نام نهایی بدون گیر غیرمنطقی.",
        "tips": ["میانبر: regdemo_intro_done_iv برای شروع از بعد مصاحبه."],
    },
    "start_therapy": {
        "who": "دانشجو؛ درمانگر",
        "where": "پورتال دانشجو → فرایندها؛ پورتال درمانگر → کارهای منتظر",
        "steps": [
            "دانشجو درمانگر را انتخاب کند.",
            "درمانگر درخواست را تأیید کند.",
            "دانشجو زمان اولین جلسه و پرداخت را انجام دهد.",
        ],
        "expect": "وضعیت درمان فعال شود.",
    },
    "attendance_tracking": {
        "who": "درمانگر؛ در صورت نیاز مسئول سایت یا معاون آموزش",
        "where": "پورتال درمانگر → کارهای منتظر",
        "steps": [
            "درمانگر حضور/غیاب جلسه را ثبت کند.",
            "در صورت اسکیلیشن، مسئول سایت پرونده را بررسی کند.",
        ],
        "expect": "ساعات درمان در پروفایل دانشجو به‌روز شود.",
    },
    "therapy_early_termination": {
        "who": "درمانگر؛ سپس دانشجو یا کمیته‌ها بسته به علت",
        "where": "پورتال درمانگر؛ سپس پورتال کمیته نظارت برای زیرفرایندها",
        "steps": [
            "درمانگر یکی از ۴ علت قطع را انتخاب کند.",
            "علت ۱/۲: مهلت ۵ روز برای آغاز مجدد توسط دانشجو.",
            "علت ۳: زیرفرایند کمیسیون تخصصی.",
            "علت ۴: زیرفرایند بررسی کمیته‌ها.",
        ],
        "expect": "فرایند فرزند (تخلف/کمیته) در inbox نقش مربوط ظاهر شود.",
    },
    "educational_leave": {
        "who": "دانشجو؛ کمیته پیشرفت؛ معاون آموزش",
        "where": "پورتال دانشجو؛ پورتال کمیته پیشرفت",
        "steps": [
            "دانشجو درخواست مرخصی آموزشی را ثبت کند.",
            "کمیته جلسه برگزار و تصمیم بگیرد.",
            "در صورت تأیید، وضعیت مرخصی فعال شود.",
        ],
        "expect": "ثبت‌نام کلاس‌ها قفل شود؛ در صورت تخلف فرایند violation_registration ایجاد شود.",
    },
    "upgrade_to_ta": {
        "who": "دانشجو؛ کمیته نظارت؛ کمیته دروس",
        "where": "پورتال دانشجو؛ پورتال کمیته نظارت؛ پورتال کمیته دروس",
        "steps": [
            "دانشجو درخواست ارتقا به کمک‌مدرس را بزند.",
            "کمیته نظارت بررسی کند.",
            "کمیته دروس مصاحبه و رسته را تعیین کند.",
            "دانشجو تعهدنامه را امضا کند.",
        ],
        "expect": "وضعیت کمک‌مدرس ثبت شود.",
    },
    "violation_registration": {
        "who": "مسئول کمیته نظارت؛ کمیته نظارت؛ کمیته آموزش",
        "where": "پورتال کمیته نظارت → بررسی‌ها",
        "steps": [
            "پرونده تخلف را از صندوق باز کنید.",
            "وضعیت بررسی و جلسه را ثبت کنید.",
            "حکم صادر و در صورت نیاز به کمیته آموزش ارجاع دهید.",
        ],
        "expect": "پرونده تخلف بسته شود یا به کمیته آموزش برود.",
    },
    "fee_determination": {
        "who": "سامانه (خودکار) — دانشجو نتیجه را می‌بیند",
        "where": "پورتال دانشجو → فرایندها یا پروفایل مالی",
        "steps": [
            "پس از غیبت/کنسلی مرتبط، این فرایند خودکار شروع می‌شود.",
            "فقط نتیجه (بدهی/اعتبار/بدون اقدام) را بررسی کنید.",
        ],
        "expect": "نتیجه مالی منطقی با رویداد قبلی باشد.",
        "tips": ["این فرایند غیرقابل ریست است — در صورت گیرکردن GAP ثبت کنید."],
    },
    "committees_review": {
        "who": "کمیته نظارت؛ کمیته آموزش؛ دانشجو",
        "where": "پورتال کمیته نظارت و آموزش",
        "steps": [
            "کمیته نظارت بررسی اولیه را انجام دهد.",
            "کمیته آموزش بررسی تکمیلی.",
            "دانشجو در صورت مجاز بودن درمان را از نو آغاز کند.",
        ],
        "expect": "ارجاع بیمار یا ثبت تخلف در صورت عدم آغاز مجدد.",
    },
    "specialized_commission_review": {
        "who": "کمیسیون تخصصی؛ دانشجو",
        "where": "پورتال کمیته نظارت (کمیسیون تخصصی)",
        "steps": [
            "کمیسیون تصمیم خود را ثبت کند.",
            "دانشجو در مهلت ۵ روز درمان را از نو آغاز کند یا تخلف ثبت شود.",
        ],
        "expect": "در صورت عدم آغاز مجدد، committees_review یا violation_registration ایجاد شود.",
    },
    "supervision_block_transition": {
        "who": "دانشجو؛ سوپروایزر",
        "where": "پورتال دانشجو → فرایندها",
        "steps": [
            "دانشجو در جلسه ۵۰ام قصد پرداخت را اعلام کند.",
            "سوپروایزر بلوک بعدی را انتخاب کند.",
            "پرداخت جلسه اول بلوک جدید را انجام دهد.",
        ],
        "expect": "بلوک سوپرویژن جدید فعال شود؛ در غیر ۵۰ام به session_payment هدایت شود.",
    },
    "internship_readiness_consultation": {
        "who": "دانشجو؛ کمیته نظارت؛ کمیته پیشرفت",
        "where": "پورتال دانشجو؛ پورتال کمیته‌ها",
        "steps": [
            "دانشجو درخواست آمادگی کارورزی را ثبت کند.",
            "کمیته‌ها مصاحبه و قراردادها را بررسی کنند.",
            "دانشجو سوپروایزر و پرداخت اولین جلسه را انجام دهد.",
        ],
        "expect": "وضعیت کارورزی فعال شود.",
    },
    "thesis_defense_request": {
        "who": "دانشجو؛ کمیته پیشرفت؛ کمیته نظارت؛ کمیته آموزش",
        "where": "پورتال دانشجو؛ پورتال کمیته‌ها",
        "steps": [
            "پیش‌نیاز: خاتمه درس مقاله‌نویسی.",
            "دانشجو درخواست دفاع و فایل‌ها را آپلود کند.",
            "کمیته‌ها بررسی و زمان دفاع تعیین کنند.",
        ],
        "expect": "مسیر دفاع قابل پیگیری باشد.",
    },
    "patient_referral": {
        "who": "مسئول کمیته نظارت",
        "where": "پورتال کمیته نظارت",
        "steps": [
            "فهرست بیماران انترن را ببینید.",
            "درمانگر جدید برای هر بیمار تعیین کنید.",
        ],
        "expect": "ارجاع کامل و پرونده بسته شود.",
    },
    "return_to_full_education": {
        "who": "دانشجو؛ هماهنگ‌کننده درمان",
        "where": "پورتال دانشجو؛ پورتال کمیته پیشرفت",
        "steps": [
            "پس از پایان مرخصی کامل، دانشجو درخواست بازگشت دهد.",
            "مسیر درمان و سوپرویژن از نو تنظیم شود.",
        ],
        "expect": "ثبت‌نام مجدد باز شود.",
    },
    "winter_semester_preparation": {
        "who": "معاون آموزش؛ کمیته دروس؛ مسئول پذیرش",
        "where": "آماده‌سازی ترم → workbench زمستان",
        "steps": [
            "پروانه و لیست دروس را بررسی کنید.",
            "تبلیغات و مصاحبه‌گران را تنظیم کنید.",
            "تا انتشار ادامه دهید.",
        ],
        "expect": "ترم زمستان منتشر شود.",
    },
}

LIFECYCLE_ORDER: list[str] = [
    "fall_semester_preparation",
    "introductory_course_registration",
    "lesson_start_per_term",
    "introductory_term_end",
    "intro_second_semester_registration",
    "introductory_course_completion",
    "comprehensive_course_registration",
    "comprehensive_term_start",
    "student_instructor_evaluation",
    "comprehensive_term_end",
    "start_therapy",
    "attendance_tracking",
    "session_payment",
    "supervision_block_transition",
    "supervision_50h_completion",
    "educational_leave",
    "internship_readiness_consultation",
    "upgrade_to_ta",
    "article_writing_completion",
    "thesis_defense_request",
]

# فاز ۱ — فرایندهای حیاتی برای تست سریع با اپراتور غیرفنی (ساخت از صفر، بدون seed پرونده)
PHASE_1_CRITICAL: list[tuple[str, str]] = [
    (
        "fall_semester_preparation",
        "بدون انتشار ترم پاییز، ثبت‌نام و اکثر مسیر آموزشی قفل می‌ماند.",
    ),
    (
        "introductory_course_registration",
        "درگاه ورود متقاضی — مصاحبه، مدارک، پرداخت و ثبت‌نام آشنایی.",
    ),
    (
        "lesson_start_per_term",
        "آغاز دروس هر ترم — پایهٔ حضور و غیاب و عملیات کلاسی.",
    ),
    (
        "start_therapy",
        "شروع درمان شخصی — هستهٔ آموزش سه‌وجهی انستیتو.",
    ),
    (
        "attendance_tracking",
        "ثبت حضور/غیاب جلسات درمان — پیگیری ساعات دانشجو.",
    ),
    (
        "session_payment",
        "پرداخت جلسات درمان — مسیر مالی حیاتی.",
    ),
    (
        "supervision_block_transition",
        "سوپرویژن فردی و انتقال بلوک — مسیر اصلی پیشرفت درمان.",
    ),
    (
        "educational_leave",
        "مرخصی آموزشی — تعامل دانشجو با کمیته پیشرفت.",
    ),
    (
        "violation_registration",
        "ثبت و رسیدگی تخلف — حاکمیت انضباطی مجموعه.",
    ),
    (
        "comprehensive_course_registration",
        "ثبت‌نام دوره جامع — مسیر اصلی دانشجویان پس از آشنایی.",
    ),
    (
        "comprehensive_term_start",
        "آغاز ترم دوره جامع — عملیات ترم جامع.",
    ),
]


def filter_phase1_specs(specs: list[ProcessTestSpec]) -> list[ProcessTestSpec]:
    by_code = {s.code: s for s in specs if not s.is_stub}
    result: list[ProcessTestSpec] = []
    for code, _why in PHASE_1_CRITICAL:
        spec = by_code.get(code)
        if spec:
            result.append(spec)
    return result


@dataclass
class CrossProcessLink:
    source_code: str
    source_name_fa: str
    from_state: str
    trigger: str
    target_code: str
    target_name_fa: str
    link_type: str
    verifier_role: str
    verify_portal: str
    test_scenario: str

    @property
    def key(self) -> str:
        return f"{self.source_code}:{self.from_state}:{self.target_code}:{self.link_type}"


@dataclass
class StateTestSpec:
    index: int
    code: str
    name_fa: str
    assigned_role: str
    role_fa: str
    is_automatic: bool
    operator_task_fa: str
    portal_path: str
    portal_menu_nav: str
    demo_username: str
    gap_id: str
    state_type: str


@dataclass
class ProcessTestSpec:
    code: str
    number: int
    name_fa: str
    description: str
    initial_state: str
    initial_role: str
    states: list[StateTestSpec]
    portal_path: str
    portal_menu_nav: str
    demo_username: str
    gap_prefix: str
    preconditions: list[str]
    outbound_links: list[CrossProcessLink] = field(default_factory=list)
    inbound_links: list[CrossProcessLink] = field(default_factory=list)
    enrichment: dict[str, Any] | None = None
    is_stub: bool = False
    restart_blocked: bool = False
    scheduler_note: str | None = None
    human_state_count: int = 0


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def resolve_portal(role: str, process_code: str = "") -> tuple[str, str, str]:
    if process_code in PROCESS_PORTAL_OVERRIDE:
        return PROCESS_PORTAL_OVERRIDE[process_code]
    return ROLE_PORTAL.get(role, ("/panel", "", "admin"))


def _extract_tab_key(path_or_tab: str) -> str:
    """Extract tab key from ?tab=... query or bare tab id."""
    if not path_or_tab:
        return ""
    if path_or_tab.startswith("?tab="):
        return path_or_tab[5:].split("&")[0]
    if "tab=" in path_or_tab:
        for part in path_or_tab.split("?")[-1].split("&"):
            if part.startswith("tab="):
                return part[4:].split("&")[0]
    if path_or_tab.startswith("?"):
        return ""
    return path_or_tab


def menu_nav(portal_path: str = "", tab: str = "") -> str:
    """Return non-technical sidebar navigation (no URLs)."""
    combined = (portal_path or "").strip()
    base = combined.split("?")[0]

    tab_key = _extract_tab_key(tab)
    if not tab_key:
        tab_key = _extract_tab_key(combined)

    menu_name = "پورتال مربوطه"
    if base:
        for path_key in sorted(PATH_MENU_FA.keys(), key=len, reverse=True):
            if base == path_key or base.startswith(path_key + "/"):
                menu_name = PATH_MENU_FA[path_key]
                break
        else:
            if base.startswith("/panel/portal/staff/"):
                menu_name = "پنل کارمند"
            elif base.startswith("/panel/portal/committee/"):
                menu_name = "پنل کمیته"

    if tab_key and tab_key in TAB_FA:
        return f"منوی کناری / {menu_name} / تب «{TAB_FA[tab_key]}»"
    return f"منوی کناری / {menu_name}"


def _gap_prefix(number: int) -> str:
    return f"GAP-{number:02d}"


def _default_operator_task(
    role: str,
    state_name: str,
    state_code: str,
    process_code: str = "",
) -> str:
    if role == "system":
        return (
            "خودکار — فقط بررسی کنید نتیجه در پرونده، پروفایل یا اعلان "
            "به‌درستی نمایش داده شده باشد."
        )
    role_fa = ROLE_FA.get(role, role)
    portal_path, tab, username = resolve_portal(role, process_code)
    nav = menu_nav(portal_path, tab)
    return (
        f"با حساب {username} ({role_fa}) وارد شوید، از {nav} "
        f"پرونده را باز کنید، مرحله «{state_name}» را تکمیل و ثبت کنید."
    )


def _extract_transition_links(
    source_code: str,
    source_name: str,
    transitions: list[dict[str, Any]],
    process_names: dict[str, str],
) -> list[CrossProcessLink]:
    links: list[CrossProcessLink] = []
    seen: set[str] = set()
    for tr in transitions or []:
        from_state = str(tr.get("from") or "")
        trigger = str(tr.get("trigger") or "")
        for action in tr.get("actions") or []:
            if not isinstance(action, dict):
                continue
            atype = action.get("type")
            target = None
            link_type = "spawn"
            if atype == "start_process":
                target = action.get("process_code")
            elif atype == "call_bpms_subprocess":
                target = action.get("subprocess_code") or action.get("process_code")
                link_type = "subprocess"
            elif atype == "redirect_to_process":
                target = action.get("process_code")
                link_type = "redirect"
            if not target:
                continue
            target = str(target)
            verifier_role = "staff1"
            portal_path, tab, verifier_role_user = resolve_portal(
                _guess_role_for_process(target), target
            )
            verify_portal = menu_nav(portal_path, tab or "?tab=pending")
            scenario = (
                f"پس از رویداد «{trigger}» در مرحله «{from_state}»، "
                f"با حساب {verifier_role_user} از {verify_portal} پرونده "
                f"«{process_names.get(target, target)}» را ببینید."
            )
            link = CrossProcessLink(
                source_code=source_code,
                source_name_fa=source_name,
                from_state=from_state,
                trigger=trigger,
                target_code=target,
                target_name_fa=process_names.get(target, target),
                link_type=link_type,
                verifier_role=verifier_role_user,
                verify_portal=verify_portal,
                test_scenario=scenario,
            )
            if link.key not in seen:
                seen.add(link.key)
                links.append(link)
    return links


def _guess_role_for_process(process_code: str) -> str:
    overrides = {
        "violation_registration": "supervision_committee",
        "patient_referral": "monitoring_committee_officer",
        "fee_determination": "student",
        "session_payment": "student",
        "committees_review": "supervision_committee",
        "specialized_commission_review": "supervision_committee",
        "intern_bulk_patient_referral": "therapy_committee_executor",
    }
    return overrides.get(process_code, "staff")


def _extract_precondition_links(
    source_code: str,
    source_name: str,
    preconditions: list[dict[str, Any]],
    process_names: dict[str, str],
) -> list[CrossProcessLink]:
    links: list[CrossProcessLink] = []
    for pre in preconditions or []:
        if not isinstance(pre, dict):
            continue
        if pre.get("type") != "process_completed":
            continue
        target = str(pre.get("process_code") or "")
        if not target:
            continue
        portal_path, tab, user = resolve_portal("student", source_code)
        links.append(
            CrossProcessLink(
                source_code=source_code,
                source_name_fa=source_name,
                from_state="(پیش‌نیاز)",
                trigger="process_completed",
                target_code=target,
                target_name_fa=process_names.get(target, target),
                link_type="prerequisite",
                verifier_role=user,
                verify_portal=menu_nav(portal_path, tab),
                test_scenario=(
                    f"قبل از شروع «{source_name}»، فرایند "
                    f"«{process_names.get(target, target)}» باید کامل شده باشد."
                ),
            )
        )
    return links


def _order_states(states: list[dict[str, Any]], initial_state: str) -> list[dict[str, Any]]:
    """Best-effort ordering: initial first, then intermediates, terminals last."""
    by_code = {s["code"]: s for s in states}
    initial = by_code.get(initial_state)
    rest = [s for s in states if s.get("code") != initial_state]
    type_order = {"initial": 0, "intermediate": 1, "terminal": 2}
    rest.sort(key=lambda s: (type_order.get(s.get("type", ""), 1), s.get("code", "")))
    ordered = []
    if initial:
        ordered.append(initial)
    ordered.extend(rest)
    return ordered


def build_process_specs() -> list[ProcessTestSpec]:
    raw_processes: dict[str, dict[str, Any]] = {}
    process_names: dict[str, str] = {}
    all_links: list[CrossProcessLink] = []

    for path in sorted(PROCESSES_DIR.glob("*.json")):
        data = _load_json(path)
        proc = data.get("process") or {}
        code = proc.get("code") or path.stem
        raw_processes[code] = data
        process_names[code] = proc.get("name_fa") or code

    index_data = _load_json(INDEX_PATH) if INDEX_PATH.is_file() else {"processes": []}
    registry_refs: dict[str, list[str]] = {}
    for entry in index_data.get("processes") or []:
        code = entry.get("code")
        refs = entry.get("sub_process_refs") or []
        if code and refs:
            registry_refs[str(code)] = [str(r) for r in refs]

    for code, data in raw_processes.items():
        proc = data.get("process") or {}
        name_fa = proc.get("name_fa") or code
        transitions = data.get("transitions") or []
        all_links.extend(_extract_transition_links(code, name_fa, transitions, process_names))
        preconds = proc.get("preconditions") or []
        all_links.extend(_extract_precondition_links(code, name_fa, preconds, process_names))

    for source, refs in registry_refs.items():
        source_name = process_names.get(source, source)
        for target in refs:
            if target not in process_names:
                continue
            portal_path, tab, user = resolve_portal(_guess_role_for_process(target), target)
            link = CrossProcessLink(
                source_code=source,
                source_name_fa=source_name,
                from_state="(ثبت رجیستری)",
                trigger="sub_process_refs",
                target_code=target,
                target_name_fa=process_names.get(target, target),
                link_type="registry",
                verifier_role=user,
                verify_portal=menu_nav(portal_path, tab or "?tab=pending"),
                test_scenario=(
                    f"پس از تکمیل/رویداد در «{source_name}»، پرونده "
                    f"«{process_names.get(target, target)}» در inbox نقش مربوط ظاهر شود."
                ),
            )
            all_links.append(link)

    outbound_by_source: dict[str, list[CrossProcessLink]] = {}
    inbound_by_target: dict[str, list[CrossProcessLink]] = {}
    seen_keys: set[str] = set()
    for link in all_links:
        if link.key in seen_keys:
            continue
        seen_keys.add(link.key)
        outbound_by_source.setdefault(link.source_code, []).append(link)
        inbound_by_target.setdefault(link.target_code, []).append(link)

    specs: list[ProcessTestSpec] = []
    for code, data in raw_processes.items():
        proc = data.get("process") or {}
        number = proc.get("number")
        if number is None:
            m = re.search(r"(\d+)", code)
            number = int(m.group(1)) if m else 9000 + len(specs)
        number = int(number)

        initial_state = proc.get("initial_state") or ""
        initial_role = proc.get("initial_role") or ""
        states_raw = data.get("states") or []
        if not initial_role and states_raw:
            for s in states_raw:
                if s.get("code") == initial_state:
                    initial_role = s.get("assigned_role") or ""
                    break

        portal_path, tab, demo_user = resolve_portal(initial_role, code)
        full_portal = f"{portal_path}{tab}" if portal_path else ""
        full_menu_nav = menu_nav(portal_path, tab)

        ordered_states = _order_states(states_raw, initial_state)
        state_specs: list[StateTestSpec] = []
        gap_pfx = _gap_prefix(number)
        human_count = 0

        for idx, st in enumerate(ordered_states, 1):
            role = str(st.get("assigned_role") or "system")
            meta = st.get("metadata") or {}
            task = meta.get("operator_task_fa") or ""
            if not task:
                task = _default_operator_task(
                    role, st.get("name_fa", ""), st.get("code", ""), code
                )
            is_auto = role == "system"
            if not is_auto:
                human_count += 1
            st_portal, st_tab, st_user = resolve_portal(role, code)
            st_full = f"{st_portal}{st_tab}" if st_portal else full_portal
            st_menu_nav = menu_nav(st_portal, st_tab)
            state_specs.append(
                StateTestSpec(
                    index=idx,
                    code=str(st.get("code") or ""),
                    name_fa=str(st.get("name_fa") or ""),
                    assigned_role=role,
                    role_fa=ROLE_FA.get(role, role),
                    is_automatic=is_auto,
                    operator_task_fa=task,
                    portal_path=st_full,
                    portal_menu_nav=st_menu_nav,
                    demo_username=st_user,
                    gap_id=f"{gap_pfx}-{st.get('code', '')}",
                    state_type=str(st.get("type") or ""),
                )
            )

        precond_texts = []
        for pre in proc.get("preconditions") or []:
            if isinstance(pre, dict) and pre.get("description_fa"):
                precond_texts.append(str(pre["description_fa"]))
            elif isinstance(pre, dict) and pre.get("process_code"):
                pc = pre["process_code"]
                precond_texts.append(
                    f"فرایند {process_names.get(pc, pc)} باید تکمیل شده باشد"
                )

        sched_note = None
        if code in SCHEDULER_HEAVY_PROCESSES:
            sched_note = (
                "این فرایند اغلب توسط زمان‌بند خودکار "
                "(منوی کناری / اتوماسیون زمان‌محور) یا seed دمو شروع می‌شود — "
                "در صورت نبود پرونده از مسئول فنی بخواهید."
            )

        specs.append(
            ProcessTestSpec(
                code=code,
                number=number,
                name_fa=proc.get("name_fa") or code,
                description=str(proc.get("description") or "").strip(),
                initial_state=initial_state,
                initial_role=initial_role,
                states=state_specs,
                portal_path=full_portal,
                portal_menu_nav=full_menu_nav,
                demo_username=demo_user,
                gap_prefix=gap_pfx,
                preconditions=precond_texts,
                outbound_links=outbound_by_source.get(code, []),
                inbound_links=inbound_by_target.get(code, []),
                enrichment=ENRICHMENT_OVERRIDES.get(code),
                is_stub=code == "process_merged_to_one",
                restart_blocked=code in RESTART_BLOCKED,
                scheduler_note=sched_note,
                human_state_count=human_count,
            )
        )

    specs.sort(key=lambda s: (s.number, s.code))
    return specs


def collect_cross_process_links(specs: list[ProcessTestSpec]) -> list[CrossProcessLink]:
    seen: set[str] = set()
    links: list[CrossProcessLink] = []
    for spec in specs:
        for link in spec.outbound_links + spec.inbound_links:
            if link.key in seen:
                continue
            seen.add(link.key)
            links.append(link)
    links.sort(key=lambda l: (l.source_code, l.target_code, l.link_type))
    return links


def processes_missing_operator_tasks(specs: list[ProcessTestSpec]) -> list[str]:
    missing = []
    for spec in specs:
        if spec.is_stub:
            continue
        for st in spec.states:
            if st.is_automatic:
                continue
            if "با حساب" in st.operator_task_fa and "منوی کناری" in st.operator_task_fa:
                missing.append(f"{spec.code}:{st.code}")
    return missing


@dataclass
class DemoAccountGuide:
    role_fa: str
    username: str
    password: str
    sidebar_menu: str
    when_to_use: str
    what_to_expect: str


DEMO_ACCOUNT_GUIDES: list[DemoAccountGuide] = [
    DemoAccountGuide(
        "مدیر سامانه", "admin", "admin123",
        "داشبورد و همهٔ منوهای سایدبار",
        "فقط وقتی راهنما صریحاً گفته؛ معمولاً برای آماده‌سازی ترم یا رفع گیرکردن.",
        "به همهٔ پنل‌ها دسترسی دارید؛ منوی کناری پر از گزینه است.",
    ),
    DemoAccountGuide(
        "معاون آموزش", "deputy_education1", "demo123",
        "منوی کناری / آماده‌سازی ترم",
        "فرایندهای آماده‌سازی ترم پاییز و زمستان.",
        "صفحهٔ مراحل ترم؛ دکمهٔ ادامه و فرم‌های هر مرحله.",
    ),
    DemoAccountGuide(
        "کارمند پذیرش", "demo_admissions", "demo123",
        "منوی کناری / پنل پذیرش / تب کارهای من",
        "بررسی مدارک، تأیید ثبت‌نام، کارهای پذیرش.",
        "لیست پرونده‌های منتظر؛ با کلیک روی هر پرونده فرم و دکمهٔ ثبت.",
    ),
    DemoAccountGuide(
        "مصاحبه‌گر", "demo_interviewer", "demo123",
        "منوی کناری / پنل مصاحبه‌گر",
        "ثبت نتیجهٔ مصاحبهٔ پذیرش.",
        "پروندهٔ مصاحبه با فرم نتیجه و دکمهٔ تأیید.",
    ),
    DemoAccountGuide(
        "مسئول سایت", "site_manager1", "demo123",
        "منوی کناری / پنل مسئول سایت",
        "زمان‌بندی مصاحبه، موارد اسکیلیشن حضور.",
        "کارهای منتظر سایت؛ فرم زمان‌بندی یا بررسی.",
    ),
    DemoAccountGuide(
        "دانشجو", "student1", "demo123",
        "منوی کناری / پنل آموزشی / تب فرایندها",
        "اکثر فرایندهای دانشجویی (درمان، مرخصی، ثبت‌نام).",
        "لیست فرایندهای فعال؛ وضعیت هر مرحله قابل مشاهده است.",
    ),
    DemoAccountGuide(
        "متقاضی آشنایی", "regdemo_intro_app", "demo123",
        "منوی کناری / پنل آموزشی / تب فرایندها",
        "ثبت‌نام دورهٔ آشنایی از ابتدا.",
        "فرم درخواست، وقت مصاحبه، پرداخت و انتخاب درس.",
    ),
    DemoAccountGuide(
        "دانشجوی جامع", "student2", "demo123",
        "منوی کناری / پنل آموزشی / تب فرایندها",
        "فرایندهای دورهٔ جامع (ثبت‌نام جامع، شروع ترم).",
        "فرایندهای مربوط به دانشجوی جامع در لیست فرایندها.",
    ),
    DemoAccountGuide(
        "درمانگر", "therapist1", "demo123",
        "منوی کناری / پنل درمانگر / تب کارهای من",
        "شروع درمان، حضور و غیاب، قطع درمان.",
        "پرونده‌های درمان در صندوق کارهای من.",
    ),
    DemoAccountGuide(
        "سوپروایزر", "supervisor1", "demo123",
        "منوی کناری / پنل سوپروایزر / تب بررسی‌ها",
        "سوپرویژن، انتخاب بلوک، بررسی جلسات.",
        "پرونده‌های سوپرویژن در تب بررسی‌ها.",
    ),
    DemoAccountGuide(
        "کمیته پیشرفت", "progress_committee1", "demo123",
        "منوی کناری / کمیته پیشرفت / تب بررسی‌ها",
        "مرخصی آموزشی، بازگشت به آموزش، پیشرفت.",
        "پرونده‌های منتظر بررسی کمیته.",
    ),
    DemoAccountGuide(
        "کمیته نظارت", "supervision_committee1", "demo123",
        "منوی کناری / کمیته نظارت / تب بررسی‌ها",
        "تخلف، کمیسیون تخصصی، بررسی انضباطی.",
        "پروندهٔ تخلف یا بررسی در صندوق کمیته.",
    ),
    DemoAccountGuide(
        "کمیته آموزش", "education_committee1", "demo123",
        "منوی کناری / کمیته آموزش / تب بررسی‌ها",
        "تصمیم نهایی آموزشی پس از کمیته نظارت.",
        "پروندهٔ حکم یا ادامه/توقف تحصیل.",
    ),
    DemoAccountGuide(
        "کمیته دروس", "course_committee1", "demo123",
        "منوی کناری / کمیته درس / تب کارهای من",
        "ارتقا به کمک‌مدرس، لیست دروس، مصاحبهٔ رسته.",
        "پرونده‌های مربوط به دروس و کمک‌مدرس.",
    ),
    DemoAccountGuide(
        "مدرس/کارمند", "staff1", "demo123",
        "منوی کناری / پنل مدرس یا پنل پذیرش",
        "کلاس، حضور و غیاب، تکالیف کمک‌مدرس.",
        "بسته به فرایند، پنل مدرس یا پذیرش باز می‌شود.",
    ),
]

DEMO_ACCOUNTS: list[tuple[str, str, str]] = [
    (g.role_fa, g.username, g.password) for g in DEMO_ACCOUNT_GUIDES
]

OPERATOR_TEST_INTRO = (
    "شما نیازی به دانستن جزئیات فنی ندارید. فقط مسیری را که راهنما می‌گوید "
    "در سامانه طی کنید و ببینید آیا همان چیزی که نوشته شده اتفاق می‌افتد یا نه."
)

OPERATOR_FAILURE_STEPS = [
    "در جدول مراحل همان ردیف را «خیر» علامت بزنید.",
    "در ستون «یادداشت» همان ردیف بنویسید چه انتظار داشتید و چه دیدید.",
    "شناسه GAP همان مرحله را در یادداشت یا جعبهٔ پایین صفحه بنویسید.",
    "نوع مشکل را مشخص کنید: UI (دکمه/فرم)، logic (رفتار اشتباه)، text (متن گیج‌کننده)، "
    "missing_step (مرحله نیست)، cross_process (فرایند بعدی ظاهر نشد).",
    "در صورت امکان عکس از صفحه (Print Screen) بگیرید.",
    "معمولاً به مرحلهٔ بعد بروید؛ فقط وقتی راهنما گفته «توقف» متوقف شوید.",
]

TABLE_STEP_COLUMN_GUIDE: list[tuple[str, str]] = [
    ("ردیف", "شمارهٔ ترتیب مرحله در این فرایند."),
    ("نام مرحله", "عنوان مرحله در سامانه."),
    ("نقش", "با کدام نقش (چه کسی) باید این مرحله انجام شود."),
    ("مسیر منو", "از منوی کناری کجا بروید."),
    ("اقدام شما", "دقیقاً چه کاری در صفحه انجام دهید."),
    ("نتیجه مورد انتظار", "اگر همه‌چیز درست باشد چه می‌بینید."),
    ("شناسه GAP", "اگر مشکل بود این کد را در گزارش بنویسید."),
    ("بله / خیر", "آیا نتیجه مورد انتظار رخ داد؟"),
    ("یادداشت", "در صورت «خیر»: انتظار داشتید … / دیدید …"),
]

TABLE_ACCOUNT_COLUMN_GUIDE: list[tuple[str, str]] = [
    ("نقش", "نام فارسی نقش — فقط برای فهم شما."),
    ("نام کاربری", "دقیقاً همین را در صفحهٔ ورود تایپ کنید."),
    ("رمز", "رمز همان حساب."),
    ("منوی سایدبار", "بعد از ورود از کدام منو شروع کنید."),
    ("کی استفاده کنم", "در کدام فرایندها به این حساب نیاز دارید."),
    ("باید ببینم", "نشانهٔ درست بودن ورود و مسیر."),
]


def state_expected_outcome(state_name_fa: str, is_automatic: bool, role_fa: str) -> str:
    if is_automatic:
        return (
            f"بدون کلیک شما، سامانه مرحلهٔ «{state_name_fa}» را انجام دهد "
            "و وضعیت/اعلان/پروفایل درست به‌روز شود."
        )
    return (
        f"نقش {role_fa}: فرم را پر و «ثبت» کنید؛ "
        f"سپس مرحلهٔ «{state_name_fa}» رد شده و مرحلهٔ بعدی نمایان شود."
    )


# ── From-scratch test guide (بدون seed پرونده) ───────────────────────────

SCRATCH_SEED_RUN = [
    ("python scripts/seed_all_roles.py", "فقط حساب‌های ورود — حتماً یک‌بار"),
]

SCRATCH_SEED_DO_NOT_RUN = [
    (
        "python scripts/seed_semester_prep_demo.py",
        "ترم و آماده‌سازی از قبل ساخته می‌شود — برای تست «خودم می‌سازم» نزنید.",
    ),
    (
        "python scripts/seed_operator_pending_demo.py",
        "پروندهٔ آماده در inbox می‌گذارد — برای کشف کمبود UI نزنید.",
    ),
]

UI_GAP_CHECKLIST: list[tuple[str, str]] = [
    ("منوی شروع را پیدا کردم", "بدون راهنمای PDF می‌دانستم از کدام منو بروم."),
    ("دکمه/لینک شروع فرایند بود", "«شروع»، «درخواست جدید»، «ادامه» یا معادل آن دیده شد."),
    ("فرم یا پروندهٔ اول باز شد", "صفحهٔ خالی یا خطای گیج‌کننده نبود."),
    ("بدون seed جلو رفتم", "هیچ پروندهٔ ازپیش‌ساخته لازم نبود (مگر فرایند والد را خودم ساخته باشم)."),
    ("مرحلهٔ اول قابل ثبت بود", "توانستم اولین اقدام انسانی را انجام دهم."),
]

UI_START_OVERRIDES: dict[str, dict[str, str]] = {
    "fall_semester_preparation": {
        "mode_fa": "شروع دستی از UI",
        "first_click": "منوی کناری / آماده‌سازی ترم → ادامه یا شروع فرایند پاییز",
        "success": "صفحهٔ مراحل آماده‌سازی با تقویم/شهریه/… دیده شود.",
    },
    "winter_semester_preparation": {
        "mode_fa": "شروع دستی از UI",
        "first_click": "منوی کناری / آماده‌سازی ترم → workbench زمستان",
        "success": "مراحل پروانه و لیست دروس زمستان نمایان شود.",
    },
    "introductory_course_registration": {
        "mode_fa": "شروع توسط متقاضی",
        "first_click": "ورود regdemo_intro_app → پنل آموزشی / تب فرایندها → شروع ثبت‌نام آشنایی",
        "success": "فرم درخواست پذیرش یا اولین مرحلهٔ ثبت‌نام باز شود.",
    },
    "start_therapy": {
        "mode_fa": "شروع توسط دانشجو",
        "first_click": "ورود student1 → پنل آموزشی / فرایندها → درخواست شروع درمان",
        "success": "فرایند درمان در لیست با مرحلهٔ انتخاب درمانگر.",
    },
    "class_attendance": {
        "mode_fa": "اغلب رویداد/زمان‌بند",
        "first_click": "پس از شروع درس (lesson_start_per_term)؛ یا منوی اتوماسیون زمان‌محور",
        "success": "اگر از UI نمی‌توانید شروع کنید → missing_step ثبت کنید.",
    },
    "fee_determination": {
        "mode_fa": "خودکار پس از رویداد",
        "first_click": "ابتدا غیبت/کنسلی مرتبط را خودتان بسازید؛ سپس پنل دانشجو / فرایندها",
        "success": "فرایند تعیین تکلیف مالی بدون اقدام دستی ظاهر شود.",
    },
    "session_payment": {
        "mode_fa": "خودکار یا پس از جلسه",
        "first_click": "پس از ثبت جلسه درمان؛ پنل دانشجو / فرایندها",
        "success": "پرداخت جلسه در لیست فرایندها.",
    },
}


@dataclass
class UiStartGuide:
    mode_fa: str
    account: str
    role_fa: str
    menu_nav: str
    first_click: str
    first_step_name: str
    build_first: list[str]
    success_signal: str
    empty_inbox_means: str


def derive_ui_start(spec: ProcessTestSpec) -> UiStartGuide:
    """How to start this process from UI without demo seeds."""
    enrich = spec.enrichment or {}
    override = UI_START_OVERRIDES.get(spec.code, {})
    first_human = next((s for s in spec.states if not s.is_automatic), None)
    first_any = spec.states[0] if spec.states else None

    account = (first_human or first_any).demo_username if (first_human or first_any) else spec.demo_username
    role = (first_human or first_any).role_fa if (first_human or first_any) else ROLE_FA.get(spec.initial_role, "")
    menu = (first_human.portal_menu_nav if first_human else spec.portal_menu_nav) or "پورتال نقش مربوط"
    step_name = (first_human.name_fa if first_human else (first_any.name_fa if first_any else "—"))

    build_first: list[str] = []
    for p in spec.preconditions:
        build_first.append(p)
    for link in spec.inbound_links:
        if link.link_type in ("spawn", "subprocess", "redirect", "prerequisite", "registry"):
            build_first.append(
                f"ابتدا «{link.source_name_fa}» را خودتان تا رویداد «{link.from_state}» بسازید"
            )
    build_first = build_first[:5]

    if spec.code in SCHEDULER_HEAVY_PROCESSES:
        mode = override.get("mode_fa") or "رویداد یا زمان‌بند — نه inbox آماده"
        first_click = override.get(
            "first_click",
            "فرایند والد را بسازید؛ یا منوی کناری / اتوماسیون زمان‌محور. "
            "اگر هیچ مسیر UI نیست → GAP نوع missing_step.",
        )
        empty = "طبیعی است تا رویداد قبلی رخ ندهد؛ اگر رخ داد و نیامد → cross_process"
    elif build_first and not override:
        mode = "پس از ساخت فرایند والد"
        first_click = (
            f"بعد از تکمیل پیش‌نیازها، با {account} ({role}) از {menu} "
            f"دنبال پروندهٔ «{spec.name_fa}» بگردید یا دکمهٔ شروع را بزنید."
        )
        empty = "اگر والد را ساختید ولی اینجا نیست → cross_process یا missing_step"
    else:
        mode = override.get("mode_fa") or "شروع دستی از UI"
        if enrich.get("steps"):
            first_click = override.get("first_click") or enrich["steps"][0]
        elif first_human:
            first_click = override.get("first_click") or (
                f"با {account} وارد شوید → {menu} → پرونده/دکمهٔ شروع «{step_name}»"
            )
        else:
            first_click = override.get("first_click") or (
                f"با {account} ({role}) از {menu} فرایند را پیدا یا شروع کنید."
            )
        empty = "اگر منو/دکمهٔ شروع نیست → missing_step یا UI"

    success = override.get("success") or enrich.get("expect") or (
        f"پروندهٔ «{spec.name_fa}» در {menu} با مرحلهٔ «{step_name}» قابل اقدام باشد."
    )

    return UiStartGuide(
        mode_fa=mode,
        account=account,
        role_fa=role,
        menu_nav=menu,
        first_click=first_click,
        first_step_name=step_name,
        build_first=build_first,
        success_signal=success,
        empty_inbox_means=empty,
    )
