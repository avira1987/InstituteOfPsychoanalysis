"""
ترتیب نمایش فرایندها در سایدبار — اولویت راه‌اندازی اتوماسیون و گردشکار مرکز.

هم‌راستا با موج‌های ۱ و ۲ در docs/institute_onboarding_test_guide_fa.md؛
بقیهٔ فرایندها بر اساس sop_order و در نهایت برچسب فارسی.
"""

from __future__ import annotations

from typing import Any

from app.meta.sop_registry import get_sop_order_for_process_code

# موج ۱ — حیاتی برای راه‌اندازی مرکز و چرخهٔ اصلی دانشجو
_WAVE1_ORDER: tuple[str, ...] = (
    "fall_semester_preparation",
    "winter_semester_preparation",
    "introductory_course_registration",
    "introductory_term_end",
    "comprehensive_course_registration",
    "comprehensive_term_start",
    "comprehensive_term_end",
    "start_therapy",
    "session_payment",
    "attendance_tracking",
    "supervision_block_transition",
    "class_attendance",
    "thesis_defense_request",
)

# مسیر ورود مرکز — آماده‌سازی ترم پاییز تا پایان ترم آشنایی
_ONBOARDING_ORDER: tuple[str, ...] = (
    "fall_semester_preparation",
    "introductory_course_registration",
    "introductory_term_end",
)

# موج ۲ — مهم برای پشتیبانی مسیر اصلی
_WAVE2_ORDER: tuple[str, ...] = (
    "violation_registration",
    "educational_leave",
    "full_education_leave",
    "therapy_completion",
    "supervision_50h_completion",
    "internship_readiness_consultation",
    "theory_course_completion",
    "student_non_registration",
)

_WAVE1_INDEX = {code: idx for idx, code in enumerate(_WAVE1_ORDER)}
_WAVE2_INDEX = {code: idx for idx, code in enumerate(_WAVE2_ORDER)}
_ONBOARDING_INDEX = {code: idx for idx, code in enumerate(_ONBOARDING_ORDER)}


def onboarding_process_codes() -> tuple[str, ...]:
    """فرایندهای مسیر ورود مرکز (آماده‌سازی → ثبت‌نام آشنایی → پایان ترم)."""
    return _ONBOARDING_ORDER


def process_nav_sort_key(process_code: str, label_fa: str = "") -> tuple:
    """کلید مرتب‌سازی: کمتر = مهم‌تر."""
    code = (process_code or "").strip().lower()
    if code in _WAVE1_INDEX:
        return (0, _WAVE1_INDEX[code], code)
    if code in _WAVE2_INDEX:
        return (1, _WAVE2_INDEX[code], code)
    sop = get_sop_order_for_process_code(code)
    if sop is not None:
        return (2, sop, code)
    label = (label_fa or code).casefold()
    return (3, label, code)


def sort_process_nav_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """مرتب‌سازی ردیف‌های کاتالوگ سایدبار فرایند."""
    return sorted(
        rows,
        key=lambda r: process_nav_sort_key(
            r.get("process_code") or "",
            r.get("label_fa") or r.get("process_name_fa") or "",
        ),
    )
