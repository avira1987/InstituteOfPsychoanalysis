"""دامنهٔ شروع دستی فرایند — هم‌تراز admin-ui/src/utils/processStartScope.js."""

from __future__ import annotations

from typing import Literal

ManualStartScope = Literal["student", "staff", "institute"]

# آماده‌سازی ترم — فقط هاب /panel/semester-prep (INST-OPS)
INSTITUTE_START_CODES = frozenset({
    "fall_semester_preparation",
    "winter_semester_preparation",
})

# Alias برای سازگاری با process_restart_policy و کدهای قدیمی
INSTITUTE_PROCESS_CODES = INSTITUTE_START_CODES

# شروع از مدیریت کاربران؛ carrier = INST-OPS + subject_user_* در context
STAFF_START_CODES = frozenset({
    "class_session_cancellation",
    "live_supervision_session_prep",
    "live_therapy_observation_session_prep",
    "class_attendance",
})

# نقش‌های مجاز برای شروع دستی staff (و مسدود کردن institute از /process/start)
MANUAL_START_OPERATOR_ROLES = frozenset({"admin", "deputy_education", "staff"})


def get_manual_start_scope(process_code: str | None) -> ManualStartScope:
    code = (process_code or "").strip()
    if code in INSTITUTE_START_CODES:
        return "institute"
    if code in STAFF_START_CODES:
        return "staff"
    return "student"


def is_institute_start_process(process_code: str | None) -> bool:
    return get_manual_start_scope(process_code) == "institute"


def is_staff_start_process(process_code: str | None) -> bool:
    return get_manual_start_scope(process_code) == "staff"
