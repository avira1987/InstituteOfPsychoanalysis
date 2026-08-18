"""سیاست override فرایند (بازگشت مرحله / شروع دوباره پرسنلی).

اقدام‌های override خلاف دست‌به‌دست SOP هستند و فقط مدیر سامانه و معاون آموزش
مجازند. تکمیل مرحله همچنان با assigned_role / semester_prep_rbac کنترل می‌شود.
"""

from __future__ import annotations

from typing import Any, Optional

# نقش‌های مجاز به rollback و restart پرسنلی (هم‌تراز admin-ui process*Utils)
OVERRIDE_ROLES = frozenset({"admin", "deputy_education", "deputy_education_director"})

# حداقل طول دلیل برای ردپای کنترل افراد
OVERRIDE_REASON_MIN_LEN = 3


def actor_role_can_override(actor_role: str | None) -> bool:
    role = (actor_role or "").strip().lower()
    if not role:
        return False
    if role == "admin":
        return True
    return role in OVERRIDE_ROLES


def user_can_override_process(user: Any) -> bool:
    """آیا کاربر (با همهٔ نقش‌ها) مجوز override دارد؟"""
    from app.core.user_roles import user_has_role

    if user is None:
        return False
    return user_has_role(user, *OVERRIDE_ROLES, admin_bypass=True)


def can_actor_rollback_process(*, actor_role: str) -> tuple[bool, str]:
    """مجوز بازگشت به مرحلهٔ قبل. خروجی: (مجاز؟, پیام خطا)."""
    if actor_role_can_override(actor_role):
        return True, ""
    return False, "شما مجوز بازگشت به مرحلهٔ قبل را ندارید."


def override_reason_required(actor_role: str | None) -> bool:
    """دلیل برای override پرسنلی الزامی است (دانشجو جداگانه در restart)."""
    return actor_role_can_override(actor_role)


def validate_override_reason(
    reason: Optional[str],
    *,
    actor_role: str | None,
) -> tuple[bool, str]:
    """اگر دلیل الزامی است و خالی/کوتاه باشد، False و پیام فارسی."""
    if not override_reason_required(actor_role):
        return True, ""
    cleaned = (reason or "").strip()
    if len(cleaned) < OVERRIDE_REASON_MIN_LEN:
        return False, "لطفاً دلیل این اقدام را بنویسید (حداقل چند کاراکتر)."
    return True, ""
