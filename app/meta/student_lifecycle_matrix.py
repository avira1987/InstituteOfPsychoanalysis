# -*- coding: utf-8 -*-
"""
ماتریس چرخه عمر دانشجو تا فارغ‌التحصیلی — هم‌راستا با metadata/process_registry/INDEX.json
برای API عمومی و UI اتوماسیون وب (بدون وابستگی به دیتابیس).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"


@lru_cache(maxsize=1)
def _load_process_index_json() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    path = root / "metadata" / "process_registry" / "INDEX.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)

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

LIFECYCLE_PHASES: list[dict[str, Any]] = [
    {
        "phase_id": "P0_admissions_path",
        "title_fa": "مسیر ورود و ثبت‌نام (آشنایی / جامع)",
        "student_state_hints": [
            "متقاضی؛ هنوز student_code ندارد",
            "دانشجوی introductory تازه‌ثبت‌نام",
            "دانشجوی comprehensive تازه‌ثبت‌نام",
        ],
        "process_codes": [
            "introductory_course_registration",
            "comprehensive_course_registration",
            "student_non_registration",
            "fall_semester_preparation",
            "winter_semester_preparation",
        ],
        "demo_student_count_hint": 3,
    },
    {
        "phase_id": "P1_intro_terms",
        "title_fa": "ترم‌های آشنایی و گذار بین ترم‌ها",
        "student_state_hints": [
            "introductory؛ ترم ۱ یا ۲؛ در انتظار پایان ترم",
            "نیاز به ثبت‌نام ترم دوم آشنایی",
        ],
        "process_codes": [
            "comprehensive_term_start",
            "lesson_start_per_term",
            "introductory_term_end",
            "intro_second_semester_registration",
            "introductory_course_completion",
        ],
        "demo_student_count_hint": 4,
    },
    {
        "phase_id": "P2_comprehensive_terms",
        "title_fa": "چرخه ترم در دوره جامع",
        "student_state_hints": [
            "comprehensive؛ میان ترم‌ها",
            "پایان ترم؛ آماده شروع ترم بعد",
        ],
        "process_codes": [
            "comprehensive_term_end",
            "comprehensive_term_start",
            "lesson_start_per_term",
            "student_instructor_evaluation",
        ],
        "demo_student_count_hint": 3,
    },
    {
        "phase_id": "P3_educational_therapy",
        "title_fa": "درمان آموزشی (از شروع تا خاتمه)",
        "student_state_hints": [
            "therapy_started=False (قبل از آغاز)",
            "در حال درمان؛ پرداخت/حضور فعال",
            "درخواست تغییر/افزایش/کاهش جلسه",
            "تکمیل یا وقفه یا خاتمه زودهنگام",
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
        "demo_student_count_hint": 8,
    },
    {
        "phase_id": "P4_supervision",
        "title_fa": "سوپرویژن فردی و گروهی",
        "student_state_hints": [
            "گذر بین بلوک‌های سوپرویژن",
            "نزدیک تکمیل ۵۰ ساعت",
            "تغییر تعداد جلسات یا لغو",
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
        "demo_student_count_hint": 5,
    },
    {
        "phase_id": "P5_leave_and_return",
        "title_fa": "مرخصی‌ها و بازگشت به تحصیل",
        "student_state_hints": [
            "مرخصی آموزشی موقت از کلاس",
            "مرخصی کامل از تحصیل",
            "بازگشت و ادامه",
        ],
        "process_codes": [
            "educational_leave",
            "full_education_leave",
            "return_to_full_education",
        ],
        "demo_student_count_hint": 3,
    },
    {
        "phase_id": "P6_committees",
        "title_fa": "کمیسیون‌ها و کمیته‌ها (تصمیم‌گیری)",
        "student_state_hints": [
            "پرونده نیازمند نظر تخصصی یا چندکمیته",
            "تخلف یا ارجاع بیمار در کارورزی",
        ],
        "process_codes": [
            "specialized_commission_review",
            "committees_review",
            "process_merged_to_one",
        ],
        "demo_student_count_hint": 2,
    },
    {
        "phase_id": "P7_internship",
        "title_fa": "کارورزی و آمادگی / شرایط دوازده ماهه",
        "student_state_hints": [
            "is_intern=True؛ آمادگی یا افزایش ساعت",
            "ارجاع گروهی بیمار",
        ],
        "process_codes": [
            "internship_readiness_consultation",
            "internship_12month_conditional_review",
            "intern_hours_increase",
            "intern_bulk_patient_referral",
        ],
        "demo_student_count_hint": 4,
    },
    {
        "phase_id": "P8_courses_completion",
        "title_fa": "دروس نظری و عملی و تکمیل مقاله/پایان‌نامه",
        "student_state_hints": [
            "در حال گذراندن درس؛ آماده تکمیل نمره نهایی",
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
        "demo_student_count_hint": 6,
    },
    {
        "phase_id": "P9_ta_track",
        "title_fa": "مسیر کمک‌آموز و ارتقا به مدرس/دستیار",
        "student_state_hints": [
            "دانشجو در نقش TA یا در مسیر ارتقا",
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
        "demo_student_count_hint": 5,
    },
    {
        "phase_id": "P10_class_ops",
        "title_fa": "کلاس، حضور، کنسلی، تخلف",
        "student_state_hints": [
            "کلاس حضوری/مجازی فعال",
            "کنسلی جلسه کلاس",
            "ثبت تخلف آموزشی",
        ],
        "process_codes": [
            "class_attendance",
            "class_session_cancellation",
            "violation_registration",
        ],
        "demo_student_count_hint": 3,
    },
]

ROLE_ACTION_PATTERNS: dict[str, list[str]] = {
    "admin": [
        "ایجاد/تنظیم کاربر و نقش",
        "نظارت بر نمونه فرایندها و رفع بن‌بست با override",
        "بازبینی گزارش حسابرسی برای سناریوهای دمو",
    ],
    "staff": [
        "ایجاد یا به‌روزرسانی نمونه دانشجو و پیگیری نمونه فرایند",
        "هماهنگی بین دانشجو و درمانگر/سوپروایزر در موارد اداری",
        "مشاهده وضعیت فرایند در پنل برای رفع گیر",
    ],
    "finance": [
        "ثبت/تأیید پرداخت‌های مرتبط با session_payment و هزینه‌ها",
        "هم‌ترازی بدهی/اعتبار با سناریوهای حضور و کنسلی",
        "بازبینی تراکنش‌ها و مانده بدهکاران در داشبورد مالی",
    ],
    "therapist": [
        "پذیرش یا رد دانشجوی اختصاص‌یافته",
        "ثبت حضور، کنسلی، و اجرای قوانین ۲۴ ساعته/هفته نهم در فرایندهای درمان",
    ],
    "supervisor": [
        "نظارت بر درمانگران و دانشجویان تحت پوشش",
        "تأیید/بازخورد در مسیرهای سوپرویژن و گزارش جلسات",
    ],
    "site_manager": [
        "پیگیری هشدارهای حضور درمانگر و بستن follow-up",
        "مرور تب هشدارها و ثبت اقدام پیگیری برای هر مورد",
        "هماهنگی با درمانگر در صورت تکرار غیبت یا تأخیر ثبت حضور",
    ],
    "deputy_education": [
        "رسیدگی به SLA مرخصی/کمیته و escalation تأخیر",
    ],
    "monitoring_committee_officer": [
        "مدیریت هشدار تخلف و ارجاع بیمار در سناریوهای کارورزی/نظارت",
    ],
    "progress_committee": [
        "بررسی و تأیید/رد درخواست‌های مرخصی و تغییرات درمان طبق صلاحیت",
    ],
    "education_committee": [
        "آرای نهایی ادامه/خاتمه در مسیرهای آموزشی مشمول کمیته آموزش",
    ],
    "supervision_committee": [
        "پرونده‌های انضباطی/سوپرویژن مشمول این کمیته",
    ],
    "specialized_commission": [
        "جلسه و تصمیم برای خاتمه زودهنگام و موارد تخصصی",
    ],
    "therapy_committee_chair": [
        "تفویض پیگیری و نظارت بر پرونده‌های no-show درمان",
    ],
    "therapy_committee_executor": [
        "پیگیری عملی دانشجو و ثبت گزارش مجری",
    ],
    "student": [
        "ارسال درخواست، پرداخت، انتخاب درمانگر، شرکت در جلسات طبق SOP",
        "پیگیری فرایند فعال در تب فرایندها و تکمیل فرم‌های مرحله در صورت نیاز",
        "مرور جلسات و تکالیف از تب‌های مربوطه",
    ],
}


def get_panel_action_queue_for_role(role: str) -> dict[str, Any]:
    """
    صف «اقدامات منتظر انجام» برای نمایش در پنل نقش‌ها + اتوماسیون وب.
    ترکیب: الگوی نقش + فرایندهای رجیستری که roles_needed آن نقش را دارد.
    """
    items: list[dict[str, Any]] = []
    patterns = ROLE_ACTION_PATTERNS.get(role)
    if not patterns:
        patterns = [
            "بررسی تب‌های پنل و فرایندهای مرتبط با نقش شما؛ در صورت ابهام با مدیریت هماهنگ کنید.",
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
    """بار برای JSON — بدون I/O."""
    total_demo = sum(int(p.get("demo_student_count_hint") or 0) for p in LIFECYCLE_PHASES)
    all_codes: list[str] = []
    for p in LIFECYCLE_PHASES:
        all_codes.extend(p.get("process_codes") or [])
    return {
        "schema_version": SCHEMA_VERSION,
        "title_fa": "ماتریس چرخه عمر دانشجو و فرایندها (ثبت‌نام تا فارغ‌التحصیلی)",
        "description_fa": (
            "فازهای آموزشی، نمونه وضعیت دانشجو، کدهای فرایند رجیستری، "
            "تعداد پیشنهادی دانشجوی دمو در هر فاز، و الگوی اقدام به تفکیک نقش."
        ),
        "roles_order": ROLES_ORDER,
        "phases": LIFECYCLE_PHASES,
        "role_action_patterns": ROLE_ACTION_PATTERNS,
        "stats": {
            "phase_count": len(LIFECYCLE_PHASES),
            "unique_process_codes": len(set(all_codes)),
            "total_process_refs": len(all_codes),
            "suggested_total_demo_students": total_demo,
        },
    }
