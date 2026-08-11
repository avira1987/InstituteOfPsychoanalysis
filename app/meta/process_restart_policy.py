"""سیاست ریست (شروع دوباره از ابتدا) — هم‌تراز admin-ui/src/utils/instituteProcesses.js."""

from __future__ import annotations

from typing import Any, Optional

from app.meta.process_start_scope import INSTITUTE_PROCESS_CODES

# نقش‌های پرسنل مجاز (هم‌سطح rollback)
RESTART_STAFF_ROLES = frozenset({"admin", "deputy_education", "staff"})

# فرایندهایی که به‌دلیل ماهیت مالی همچنان قابل شروع دوباره نیستند.
# توجه: فرایندهای آماده‌سازی ترم (INSTITUTE_PROCESS_CODES) دیگر مسدود نیستند
# تا اپراتور بتواند آن‌ها را برای تنظیم دوباره از ابتدا شروع کند.
RESTART_BLOCKED_PROCESS_CODES = frozenset({
    "fee_determination",
    "session_payment",
})

# کلیدهای داخلی/سیستمی context که هنگام شروع دوباره کپی نمی‌شوند.
_INTERNAL_CONTEXT_PREFIX = "__"


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


def _restart_preserves_context(process_config: Optional[dict]) -> bool:
    """
    آیا هنگام شروع دوباره باید داده‌های عملیاتی قبلی (غیرسیستمی) حفظ شوند؟
    پیش‌فرض: بله. فرایند می‌تواند با restart_policy.preserve_context=false غیرفعالش کند.
    """
    if not isinstance(process_config, dict):
        return True
    policy = process_config.get("restart_policy")
    if not isinstance(policy, dict):
        return True
    return policy.get("preserve_context") is not False


def build_restart_initial_context(
    *,
    old_context: Optional[dict],
    old_instance_id: str,
    process_config: Optional[dict] = None,
) -> dict[str, Any]:
    """
    context اولیهٔ نمونهٔ جدید هنگام شروع دوباره را می‌سازد.

    - همیشه ارجاع به نمونهٔ قبلی (__restarted_from_instance_id) ثبت می‌شود.
    - در صورت مجاز بودن، کلیدهای عملیاتی قبلی (بدون پیشوند __) کپی می‌شوند
      تا اپراتور مجبور نباشد فرایند را از صفر پیکربندی کند.
    """
    initial: dict[str, Any] = {"__restarted_from_instance_id": old_instance_id}

    if not _restart_preserves_context(process_config):
        return initial

    if isinstance(old_context, dict):
        preserved = {
            key: value
            for key, value in old_context.items()
            if isinstance(key, str) and not key.startswith(_INTERNAL_CONTEXT_PREFIX)
        }
        if preserved:
            initial.update(preserved)
            initial["__restart_context_preserved"] = True

    return initial
