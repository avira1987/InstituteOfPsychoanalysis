"""سیاست ریست (شروع دوباره از ابتدا) — هم‌تراز admin-ui/src/utils/instituteProcesses.js."""

from __future__ import annotations

from typing import Any, Optional

# نقش‌های پرسنل مجاز (هم‌سطح rollback)
RESTART_STAFF_ROLES = frozenset({"admin", "deputy_education", "staff"})

INSTITUTE_PROCESS_CODES = frozenset({
    "fall_semester_preparation",
    "winter_semester_preparation",
})

RESTART_BLOCKED_PROCESS_CODES = frozenset({
    "fee_determination",
    "session_payment",
    *INSTITUTE_PROCESS_CODES,
})


def is_process_restart_blocked(process_code: str) -> bool:
    code = (process_code or "").strip()
    return code in RESTART_BLOCKED_PROCESS_CODES


def _config_blocks_restart(process_config: Optional[dict]) -> bool:
    if not isinstance(process_config, dict):
        return False
    policy = process_config.get("restart_policy")
    if not isinstance(policy, dict):
        return False
    return policy.get("allowed") is False


def can_actor_restart_process(
    *,
    actor_role: str,
    process_code: str,
    is_own_instance: bool,
    process_config: Optional[dict] = None,
) -> tuple[bool, str]:
    """
    بررسی مجوز ریست. خروجی: (مجاز؟, پیام خطای فارسی در صورت عدم مجوز).
    """
    role = (actor_role or "").strip().lower()
    code = (process_code or "").strip()

    if is_process_restart_blocked(code):
        return False, "این فرایند قابل شروع دوباره نیست."

    if _config_blocks_restart(process_config):
        return False, "این فرایند قابل شروع دوباره نیست."

    if role in RESTART_STAFF_ROLES:
        return True, ""

    if role == "student":
        if not is_own_instance:
            return False, "فقط می‌توانید فرایندهای خودتان را از ابتدا شروع کنید."
        policy = (process_config or {}).get("restart_policy") if isinstance(process_config, dict) else None
        if isinstance(policy, dict) and policy.get("student_allowed") is False:
            return False, "شروع دوباره این فرایند برای دانشجو مجاز نیست."
        return True, ""

    return False, "شما مجوز شروع دوباره این فرایند را ندارید."


def student_restart_reason_required(actor_role: str) -> bool:
    return (actor_role or "").strip().lower() == "student"
