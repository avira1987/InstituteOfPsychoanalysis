# -*- coding: utf-8 -*-
"""
ماتریس چرخه عمر دانشجو تا فارغ‌التحصیلی — هم‌راستا با فهرست فرایندهای ثبت‌شده در متادیتا.
برای نمای عمومی و بدون وابستگی به پایگاه داده.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_PROCESS_LABEL_FA = "فرایند ثبت‌شده در سامانه"

SCHEMA_VERSION = "1.1"


@lru_cache(maxsize=1)
def _load_process_index_json() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    path = root / "metadata" / "process_registry" / "INDEX.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _process_name_fa_by_code() -> dict[str, str]:
    idx = _load_process_index_json()
    out: dict[str, str] = {}
    for proc in idx.get("processes") or []:
        code = proc.get("code")
        if not code:
            continue
        raw = (proc.get("name_fa") or "").strip()
        out[code] = raw or _DEFAULT_PROCESS_LABEL_FA
    return out


def _public_label_fa(code: str, names: dict[str, str]) -> str:
    """نام نمایشی بدون حروف لاتین؛ در صورت نبود یا مخلوط بودن، برچسب عمومی فارسی."""
    raw = (names.get(code) or "").strip()
    if raw and not re.search(r"[A-Za-z]", raw):
        return raw
    return _DEFAULT_PROCESS_LABEL_FA


ROLES_ORDER: list[str] = [
    "admin",
    "staff",
    "finance",
    "therapist",
    "supervisor",
    "site_manager",
    "deputy_education",
    "monitoring_committee_officer",
    "progress_committee",
    "education_committee",
    "supervision_committee",
    "specialized_commission",
    "therapy_committee_chair",
    "therapy_committee_executor",
    "student",
]

_ROLE_FALLBACK_FA: dict[str, str] = {
    "admin": "مدیر سیستم",
    "staff": "کارمند دفتر",
    "finance": "اپراتور مالی",
    "therapist": "درمانگر",
    "supervisor": "سوپروایزر",
    "site_manager": "مسئول سایت",
    "deputy_education": "معاون مدیر آموزش",
    "monitoring_committee_officer": "مسئول علمی اجرایی کمیته نظارت",
    "progress_committee": "کمیته پیشرفت",
    "education_committee": "کمیته آموزش",
    "supervision_committee": "کمیته نظارت",
    "specialized_commission": "کمیسیون تخصصی",
    "therapy_committee_chair": "مسئول پروژه کمیته درمان آموزشی و سوپرویژن",
    "therapy_committee_executor": "مجری کمیته درمان آموزشی و سوپرویژن",
    "student": "دانشجو",
}


@lru_cache(maxsize=1)
def _role_labels_fa() -> dict[str, str]:
    root = Path(__file__).resolve().parents[2]
    path = root / "metadata" / "roles.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    out: dict[str, str] = {}
    for entry in data:
        code = entry.get("code")
        name = entry.get("name_fa")
        if code and name and code not in out:
            out[code] = name
    for code in ROLES_ORDER:
        out.setdefault(code, _ROLE_FALLBACK_FA.get(code, "نقش کاربری"))
    return out


LIFECYCLE_PHASES: list[dict[str, Any]] = [
    {
        "phase_id": "P0_admissions_path",
        "title_fa": "مسیر ورود و ثبت‌نام (آشنایی / جامع)",
        "student_state_hints": [
            "درخواست ورود داده‌اید و هنوز ثبت‌نام نهایی نشده است.",
            "تازه در دورهٔ آشنایی (مقدماتی) پذیرفته شده‌اید.",
            "تازه در دورهٔ جامع پذیرفته شده‌اید.",
        ],
        "process_codes": [
            "introductory_course_registration",
            "comprehensive_course_registration",
            "student_non_registration",
            "fall_semester_preparation",
            "winter_semester_preparation",
        ],
    },
    {
        "phase_id": "P1_intro_terms",
        "title_fa": "ترم‌های آشنایی و گذار بین ترم‌ها",
        "student_state_hints": [
            "در ترم اول یا دوم دورهٔ آشنایی هستید و منتظر پایان ترم یا اقدام بعدی‌اید.",
            "برای ادامه باید ثبت‌نام ترم دوم آشنایی را انجام دهید.",
        ],
        "process_codes": [
            "comprehensive_term_start",
            "lesson_start_per_term",
            "introductory_term_end",
            "intro_second_semester_registration",
            "introductory_course_completion",
        ],
    },
    {
        "phase_id": "P2_comprehensive_terms",
        "title_fa": "چرخه ترم در دوره جامع",
        "student_state_hints": [
            "در دورهٔ جامع هستید و بین دو ترم یا در حال گذر از یک ترم به ترم بعد هستید.",
            "یک ترم تمام شده و برای ترم بعد باید طبق اعلام سامانه اقدام کنید.",
        ],
        "process_codes": [
            "comprehensive_term_end",
            "comprehensive_term_start",
            "lesson_start_per_term",
            "student_instructor_evaluation",
        ],
    },
    {
        "phase_id": "P3_educational_therapy",
        "title_fa": "درمان آموزشی (از شروع تا خاتمه)",
        "student_state_hints": [
            "هنوز درمان آموزشی شخصی شروع نشده است.",
            "درمان در جریان است؛ پرداخت و حضور در جلسات را دنبال کنید.",
            "درخواست تغییر درمانگر، افزایش یا کاهش جلسه دارید.",
            "درمان در وضعیت پایان، وقفه، یا خاتمهٔ زودهنگام قرار گرفته است.",
        ],
        "process_codes": [
            "start_therapy",
            "therapy_changes",
            "extra_session",
            "session_payment",
            "attendance_tracking",
            "fee_determination",
            "therapy_completion",
            "therapy_session_increase",
            "therapy_session_reduction",
            "therapy_early_termination",
            "therapy_interruption",
            "therapist_session_cancellation",
            "student_session_cancellation",
            "unannounced_absence_reaction",
        ],
    },
    {
        "phase_id": "P4_supervision",
        "title_fa": "سوپرویژن فردی و گروهی",
        "student_state_hints": [
            "در دورهٔ سوپرویژن هستید و بین بلوک‌های سوپرویژن جابه‌جا می‌شوید.",
            "نزدیک به پایان یک بلوک ۵۰ ساعته هستید.",
            "تعداد جلسات سوپرویژن را تغییر می‌دهید یا جلسه‌ای لغو می‌شود.",
        ],
        "process_codes": [
            "supervision_block_transition",
            "supervision_50h_completion",
            "supervision_session_increase",
            "supervision_session_reduction",
            "extra_supervision_session",
            "student_supervision_cancellation",
            "supervisor_session_cancellation",
            "supervision_interruption",
            "unannounced_supervision_absence_reaction",
            "group_supervision_course_completion",
        ],
    },
    {
        "phase_id": "P5_leave_and_return",
        "title_fa": "مرخصی‌ها و بازگشت به تحصیل",
        "student_state_hints": [
            "مرخصی موقت از کلاس دارید.",
            "از تحصیل کامل مرخص شده‌اید.",
            "پس از مرخصی به تحصیل بازگشته‌اید یا در حال بازگشت هستید.",
        ],
        "process_codes": [
            "educational_leave",
            "full_education_leave",
            "return_to_full_education",
        ],
    },
    {
        "phase_id": "P6_committees",
        "title_fa": "کمیسیون‌ها و کمیته‌ها (تصمیم‌گیری)",
        "student_state_hints": [
            "پروندهٔ شما نیاز به بررسی در کمیسیون یا کمیته دارد.",
            "موضوع مربوط به کارورزی یا نظارت است.",
        ],
        "process_codes": [
            "specialized_commission_review",
            "committees_review",
            "process_merged_to_one",
        ],
    },
    {
        "phase_id": "P7_internship",
        "title_fa": "کارورزی و آمادگی / شرایط دوازده ماهه",
        "student_state_hints": [
            "در دورهٔ کارورزی هستید؛ در حال آماده‌سازی یا افزایش ساعت هستید.",
            "بحث ارجاع بیمار در گروه کارورزی مطرح می‌شود.",
        ],
        "process_codes": [
            "internship_readiness_consultation",
            "internship_12month_conditional_review",
            "intern_hours_increase",
            "intern_bulk_patient_referral",
        ],
    },
    {
        "phase_id": "P8_courses_completion",
        "title_fa": "دروس نظری و عملی و تکمیل مقاله/پایان‌نامه",
        "student_state_hints": [
            "در حال گذراندن درس‌ها هستید؛ در نهایت تکمیل نمره یا نهایی کردن واحد پیش رو می‌آید.",
        ],
        "process_codes": [
            "theory_course_completion",
            "skills_course_completion",
            "film_observation_course_completion",
            "live_therapy_observation_course_completion",
            "live_therapy_observation_session_prep",
            "live_supervision_course_completion",
            "live_supervision_session_prep",
            "article_writing_completion",
            "thesis_defense_request",
            "upgrade_to_educational_therapist",
        ],
    },
    {
        "phase_id": "P9_ta_track",
        "title_fa": "مسیر کمک‌آموز و ارتقا به مدرس/دستیار",
        "student_state_hints": [
            "در نقش کمک‌آموز هستید یا در مسیر ارتقا به مدرس یا دستیار آموزشی.",
        ],
        "process_codes": [
            "ta_conceptual_questions",
            "ta_student_consultation",
            "ta_essay_upload",
            "ta_blog_content",
            "upgrade_to_ta",
            "mentor_private_sessions",
            "ta_to_assistant_faculty",
            "ta_to_instructor_auto",
            "ta_track_change",
            "ta_track_completion",
            "ta_instructor_leave",
            "live_supervision_ta_evaluation",
            "live_therapy_observation_ta_attendance_completion",
            "film_observation_ta_attendance_completion",
        ],
    },
    {
        "phase_id": "P10_class_ops",
        "title_fa": "کلاس، حضور، کنسلی، تخلف",
        "student_state_hints": [
            "کلاس حضوری یا مجازی برای شما فعال است.",
            "برای جلسهٔ کلاس لغو یا جابه‌جایی ثبت کرده‌اید.",
            "تخلف آموزشی ثبت شده یا در حال پیگیری است.",
        ],
        "process_codes": [
            "class_attendance",
            "class_session_cancellation",
            "violation_registration",
        ],
    },
]

ROLE_ACTION_PATTERNS: dict[str, list[str]] = {
    "admin": [
        "ایجاد کاربران و تعیین نقش‌ها در سامانه",
        "در صورت نیاز، رفع مسدودیت فرایندها با مجوز مدیریتی",
        "مشاهده گزارش‌های مدیریتی و وضعیت کلی سامانه",
    ],
    "staff": [
        "پیگیری پروندهٔ دانشجویان و روند کارها",
        "هماهنگی بین دانشجو و درمانگر یا سوپروایزر در امور اداری",
        "بررسی وضعیت فرایندها برای رفع گیرهای روزمره",
    ],
    "finance": [
        "ثبت و تأیید پرداخت‌ها و هماهنگی با هزینه‌های آموزشی و جلسات",
        "بررسی بدهی و مانده حساب دانشجویان",
        "مشاهده گزارش‌های مالی در داشبورد مالی",
    ],
    "therapist": [
        "پذیرش یا رد دانشجوی اختصاص‌یافته به شما",
        "ثبت حضور و غیاب و جلسات؛ رعایت زمان‌بندی اعلام‌شده برای جلسات",
    ],
    "supervisor": [
        "همراهی درمانگران و دانشجویان تحت پوشش شما",
        "ثبت بازخورد و تأیید گزارش‌های مربوط به سوپرویژن",
    ],
    "site_manager": [
        "پیگیری هشدارهای مربوط به حضور درمانگران و بستن پیگیری",
        "هماهنگی با درمانگر در صورت تکرار غیبت یا تأخیر در ثبت حضور",
    ],
    "deputy_education": [
        "پیگیری پرونده‌های با مرخصی طولانی یا تأخیر در کمیته‌ها",
        "در صورت نیاز، ارتقای موضوع به مدیران مربوطه",
    ],
    "monitoring_committee_officer": [
        "پیگیری پیام‌های مربوط به تخلف آموزشی یا ارجاع بیمار در کارورزی",
    ],
    "progress_committee": [
        "بررسی درخواست‌های مرخصی و تغییرات درمان در حیطهٔ صلاحیت کمیته",
    ],
    "education_committee": [
        "تصمیم‌گیری دربارهٔ ادامه یا خاتمه مسیر در پرونده‌های ارجاع‌شده به کمیته آموزش",
    ],
    "supervision_committee": [
        "بررسی پرونده‌های انضباطی/سوپرویژن که به این کمیته ارجاع شده است",
    ],
    "specialized_commission": [
        "جلسه و تصمیم‌گیری دربارهٔ خاتمهٔ زودهنگام و موارد تخصصی",
    ],
    "therapy_committee_chair": [
        "تفویض پیگیری و نظارت بر پرونده‌های غیبت از جلسات درمان",
    ],
    "therapy_committee_executor": [
        "پیگیری عملی دانشجو و ثبت گزارش مجری",
    ],
    "student": [
        "ارسال درخواست‌ها، پرداخت، و انتخاب درمانگر طبق اعلام سامانه",
        "پیگیری فرایند فعال در پنل و تکمیل فرم‌های مرحله در صورت نیاز",
        "مشاهده جلسات و تکالیف از بخش‌های مربوط در پنل",
    ],
}


def get_panel_action_queue_for_role(role: str) -> dict[str, Any]:
    """
    صف اقدامات پیشنهادی برای نمایش در پنل نقش‌ها.
    ترکیب الگوی نقش و فرایندهایی که در متادیتا به این نقش نیاز دارند.
    """
    items: list[dict[str, Any]] = []
    patterns = ROLE_ACTION_PATTERNS.get(role)
    if not patterns:
        patterns = [
            "بررسی بخش‌های پنل مرتبط با نقش شما؛ در صورت ابهام با مدیریت هماهنگ کنید.",
        ]
    for i, title in enumerate(patterns):
        items.append(
            {
                "id": f"{role}_pattern_{i}",
                "title_fa": title,
                "kind": "role_pattern",
            }
        )

    if role != "admin":
        idx = _load_process_index_json()
        seen: set[str] = set()
        max_proc = 12
        proc_list = list(idx.get("processes") or [])
        proc_list.sort(key=lambda p: (p.get("name_fa") or p.get("code") or ""))
        for proc in proc_list:
            if len(seen) >= max_proc:
                break
            needed = proc.get("roles_needed") or []
            if role not in needed:
                continue
            code = proc.get("code")
            if not code or code in seen:
                continue
            seen.add(code)
            name_fa = proc.get("name_fa") or code
            items.append(
                {
                    "id": f"{role}_registry_{code}",
                    "title_fa": f"پیگیری فرایند: {name_fa}",
                    "kind": "registry_process",
                    "process_code": code,
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "role": role,
        "items": items,
        "stats": {
            "total": len(items),
            "pattern_count": len(patterns),
            "registry_count": len([x for x in items if x.get("kind") == "registry_process"]),
        },
    }


def get_student_lifecycle_matrix() -> dict[str, Any]:
    """خروجی آمادهٔ نمایش؛ نام هر فرایند از فهرست ثبت‌شده و بدون حروف لاتین در متن نمایشی."""
    names = _process_name_fa_by_code()
    all_codes: list[str] = []
    phases_out: list[dict[str, Any]] = []
    for p in LIFECYCLE_PHASES:
        codes = p.get("process_codes") or []
        all_codes.extend(codes)
        phases_out.append(
            {
                "phase_id": p["phase_id"],
                "title_fa": p["title_fa"],
                "student_state_hints": p["student_state_hints"],
                "process_codes": codes,
                "process_labels_fa": [_public_label_fa(c, names) for c in codes],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "title_fa": "مسیر آموزشی از ورود تا پایان دوره",
        "description_fa": (
            "نقشهٔ کلی مراحل آموزشی، مثال‌هایی از وضعیت شما در هر بخش، "
            "کارهایی که ممکن است در سامانه ثبت شود، و نقش افراد مختلف — بدون نیاز به دانش فنی."
        ),
        "roles_order": ROLES_ORDER,
        "role_labels_fa": _role_labels_fa(),
        "phases": phases_out,
        "role_action_patterns": ROLE_ACTION_PATTERNS,
        "stats": {
            "phase_count": len(LIFECYCLE_PHASES),
            "unique_process_codes": len(set(all_codes)),
            "total_process_refs": len(all_codes),
        },
    }
