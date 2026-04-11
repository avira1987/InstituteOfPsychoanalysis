"""شمارهٔ مرحلهٔ SOP هر فرایند از روی metadata/process_registry/INDEX.json."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

def _resolve_index_path() -> Optional[Path]:
    """مسیر INDEX.json؛ چند ریشهٔ رایج (uvicorn از ریشهٔ مخزن یا یک پوشه بالاتر)."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "metadata" / "process_registry" / "INDEX.json",
        here.parents[3] / "metadata" / "process_registry" / "INDEX.json",
        Path.cwd() / "metadata" / "process_registry" / "INDEX.json",
        Path.cwd().parent / "metadata" / "process_registry" / "INDEX.json",
    ]
    seen: set[Path] = set()
    for c in candidates:
        try:
            r = c.resolve()
        except OSError:
            continue
        if r in seen:
            continue
        seen.add(r)
        if r.is_file():
            return r
    return None

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# فرایندهایی که در notes هنوز «مرحله N» ندارند؛ ترتیب با سند SOP و جایگاه در INDEX هم‌راستا است.
_FALLBACK_SOP_ORDER: dict[str, int] = {
    "educational_leave": 1,
    "start_therapy": 2,
    "therapy_changes": 3,
    "extra_session": 4,
    "session_payment": 5,
    "attendance_tracking": 6,
    "fee_determination": 7,
    "therapy_completion": 8,
    "therapy_session_increase": 9,
    "therapy_session_reduction": 10,
    "therapy_early_termination": 11,
    "specialized_commission_review": 12,
    "committees_review": 13,
    "therapist_session_cancellation": 14,
    "unannounced_absence_reaction": 15,
    "therapy_interruption": 16,
    "student_session_cancellation": 17,
    "supervision_block_transition": 18,
    "supervision_50h_completion": 20,
    "supervision_session_increase": 21,
    "extra_supervision_session": 22,
    "supervision_session_reduction": 24,
    "student_supervision_cancellation": 25,
    "supervisor_session_cancellation": 26,
    "unannounced_supervision_absence_reaction": 27,
    "supervision_interruption": 28,
    "fall_semester_preparation": 29,
    "winter_semester_preparation": 30,
    "introductory_course_registration": 31,
    "introductory_term_end": 32,
    "intro_second_semester_registration": 33,
    "introductory_course_completion": 34,
    "comprehensive_course_registration": 35,
    "comprehensive_term_end": 36,
    "internship_readiness_consultation": 37,
    "internship_12month_conditional_review": 38,
    "intern_hours_increase": 39,
    "comprehensive_term_start": 40,
    "lesson_start_per_term": 41,
    "student_non_registration": 42,
    "ta_conceptual_questions": 43,
    "ta_student_consultation": 44,
    "ta_essay_upload": 45,
    "ta_blog_content": 46,
    "upgrade_to_ta": 47,
    "mentor_private_sessions": 48,
    "ta_to_assistant_faculty": 49,
    "ta_to_instructor_auto": 50,
    "ta_track_change": 51,
    "ta_track_completion": 52,
    "ta_instructor_leave": 53,
    "class_attendance": 54,
    "violation_registration": 55,
    "class_session_cancellation": 56,
    "student_instructor_evaluation": 57,
    "process_merged_to_one": 58,
    "full_education_leave": 59,
    "return_to_full_education": 60,
    "theory_course_completion": 61,
    "group_supervision_course_completion": 62,
    "skills_course_completion": 63,
    "film_observation_course_completion": 64,
    "live_therapy_observation_course_completion": 65,
    "live_therapy_observation_session_prep": 66,
    "live_supervision_course_completion": 67,
    "live_supervision_session_prep": 68,
    "article_writing_completion": 69,
    "thesis_defense_request": 70,
    "upgrade_to_educational_therapist": 71,
    "intern_bulk_patient_referral": 72,
    "live_supervision_ta_evaluation": 73,
    "live_therapy_observation_ta_attendance_completion": 74,
    "film_observation_ta_attendance_completion": 75,
}


def _parse_marhale_from_notes(notes: Optional[str]) -> Optional[int]:
    if not notes or not isinstance(notes, str):
        return None
    m = re.search(r"مرحله\s*([۰-۹\d]+)", notes)
    if not m:
        return None
    raw = m.group(1).translate(_PERSIAN_DIGITS)
    try:
        return int(raw)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _load_index_process_entries() -> tuple[dict[str, int], dict[str, Optional[int]]]:
    """برمی‌گرداند (نگاشت صریح sop_order از INDEX، نگاشت نهایی code -> sop_order)."""
    explicit: dict[str, int] = {}
    index_path = _resolve_index_path()
    if not index_path:
        return explicit, {}
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("processes") or []
    merged: dict[str, Optional[int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = row.get("code")
        if not code:
            continue
        if isinstance(row.get("sop_order"), int):
            explicit[code] = row["sop_order"]
            merged[code] = row["sop_order"]
            continue
        parsed = _parse_marhale_from_notes(row.get("notes"))
        if parsed is not None:
            merged[code] = parsed
        elif code in _FALLBACK_SOP_ORDER:
            merged[code] = _FALLBACK_SOP_ORDER[code]
        else:
            merged[code] = None
    return explicit, merged


def get_sop_order_for_process_code(code: str) -> Optional[int]:
    """شمارهٔ مرحلهٔ SOP برای کد فرایند، در صورت نبود None."""
    _, merged = _load_index_process_entries()
    if code in merged and merged[code] is not None:
        return merged[code]
    if code in _FALLBACK_SOP_ORDER:
        return _FALLBACK_SOP_ORDER[code]
    return None


def get_all_sop_orders() -> dict[str, Optional[int]]:
    """همهٔ کدهای ثبت‌شده در INDEX به‌همراه شماره (یا None)."""
    _, merged = _load_index_process_entries()
    return dict(merged)


def clear_sop_order_cache() -> None:
    _load_index_process_entries.cache_clear()
