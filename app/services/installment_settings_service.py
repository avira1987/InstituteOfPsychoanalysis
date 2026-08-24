"""خواندن و به‌روزرسانی سیاست اقساط (فعال/غیرفعال بودن، فاصلهٔ سررسید، گزینه‌های تعداد قسط)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import SiteSetting

INSTALLMENT_POLICY_KEY = "installment_policy"

INSTALLMENT_DISABLED_MESSAGE = (
    "پرداخت قسطی در حال حاضر از پنل مالی غیرفعال شده است. لطفاً پرداخت نقدی را انتخاب کنید."
)

DEFAULT_INSTALLMENT_POLICY: dict[str, Any] = {
    "installment_enabled": True,
    "term2_installment_gap_days": 25,
    "installment_count_options": [2, 3, 4],
}


def _normalize_options(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return list(DEFAULT_INSTALLMENT_POLICY["installment_count_options"])
    out: list[int] = []
    for x in raw:
        try:
            n = int(x)
        except (TypeError, ValueError):
            continue
        if 2 <= n <= 24:
            out.append(n)
    out = sorted(set(out))
    if not out:
        return list(DEFAULT_INSTALLMENT_POLICY["installment_count_options"])
    return out[:12]


def _normalize_gap(raw: Any) -> int:
    try:
        g = int(raw)
    except (TypeError, ValueError):
        g = int(DEFAULT_INSTALLMENT_POLICY["term2_installment_gap_days"])
    return max(1, min(365, g))


def _normalize_enabled(raw: Any) -> bool:
    if raw is None:
        return bool(DEFAULT_INSTALLMENT_POLICY["installment_enabled"])
    if isinstance(raw, str):
        return raw.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(raw)


def is_installment_enabled(policy: dict[str, Any] | None) -> bool:
    """اگر کلید در سیاست نباشد، اقساط فعال فرض می‌شود (سازگاری عقب‌رو)."""
    if not isinstance(policy, dict) or "installment_enabled" not in policy:
        return True
    return _normalize_enabled(policy.get("installment_enabled"))


def _option_value(opt: Any) -> Any:
    if isinstance(opt, dict):
        return opt.get("value")
    return opt


def installment_new_selection_blocked(
    policy: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    ctx_before: dict[str, Any] | None = None,
) -> bool:
    """آیا انتخاب جدید «اقساط» باید رد شود؟ اقساط قبلی دانشجو حفظ می‌شود."""
    if is_installment_enabled(policy):
        return False
    if (ctx_before or {}).get("payment_method") == "installment":
        return False
    return (incoming or {}).get("payment_method") == "installment"


def apply_installment_policy_to_forms(
    forms: list | None,
    policy: dict[str, Any] | None,
    *,
    already_on_installment: bool = False,
) -> list:
    """حذف گزینهٔ اقساط از فرم‌ها وقتی سیاست غیرفعال است (نمونه‌های قبلی دست نخورده می‌مانند)."""
    enabled = is_installment_enabled(policy) or already_on_installment
    out: list = []
    for form in forms or []:
        if not isinstance(form, dict):
            out.append(form)
            continue
        form_copy = dict(form)
        fields: list = []
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                fields.append(field)
                continue
            field_copy = dict(field)
            name = field_copy.get("name")
            if not enabled and name == "payment_method" and isinstance(field_copy.get("options"), list):
                field_copy["options"] = [
                    opt for opt in field_copy["options"] if _option_value(opt) != "installment"
                ]
            if not enabled and name == "installment_count":
                continue
            fields.append(field_copy)
        form_copy["fields"] = fields
        out.append(form_copy)
    return out


async def get_installment_policy(db: AsyncSession) -> dict[str, Any]:
    """بازگرداندن سیاست اقساط با ادغام پیش‌فرض و ردیف دیتابیس."""
    row = None
    try:
        stmt = select(SiteSetting).where(SiteSetting.key == INSTALLMENT_POLICY_KEY)
        r = await db.execute(stmt)
        row = r.scalars().first()
    except (ProgrammingError, DBAPIError):
        row = None

    merged = dict(DEFAULT_INSTALLMENT_POLICY)
    updated_at: str | None = None
    if row and isinstance(row.value_json, dict):
        merged.update(row.value_json)
        if row.updated_at:
            updated_at = row.updated_at.isoformat()

    gap = _normalize_gap(merged.get("term2_installment_gap_days"))
    opts = _normalize_options(merged.get("installment_count_options") or merged.get("installment_options"))
    enabled = _normalize_enabled(merged.get("installment_enabled"))

    return {
        "installment_enabled": enabled,
        "term2_installment_gap_days": gap,
        "installment_count_options": opts,
        "updated_at": updated_at,
    }


async def forms_with_installment_policy(
    db: AsyncSession,
    forms: list | None,
    context_data: dict[str, Any] | None = None,
) -> list:
    """اعمال سیاست جاری اقساط روی متادیتای فرم قبل از ارسال به UI."""
    policy = await get_installment_policy(db)
    already = (context_data or {}).get("payment_method") == "installment"
    return apply_installment_policy_to_forms(
        forms,
        policy,
        already_on_installment=already,
    )


async def new_installment_disabled_reason(
    db: AsyncSession,
    incoming: dict[str, Any] | None,
    ctx_before: dict[str, Any] | None = None,
) -> str | None:
    policy = await get_installment_policy(db)
    if installment_new_selection_blocked(policy, incoming, ctx_before):
        return INSTALLMENT_DISABLED_MESSAGE
    return None


async def update_installment_policy(
    db: AsyncSession,
    *,
    installment_enabled: bool | None = None,
    term2_installment_gap_days: int | None = None,
    installment_count_options: list[int] | None = None,
) -> dict[str, Any]:
    """ذخیرهٔ سیاست اقساط (upsert)."""
    current = await get_installment_policy(db)
    payload = {
        "installment_enabled": bool(current["installment_enabled"]),
        "term2_installment_gap_days": current["term2_installment_gap_days"],
        "installment_count_options": list(current["installment_count_options"]),
    }
    if installment_enabled is not None:
        payload["installment_enabled"] = _normalize_enabled(installment_enabled)
    if term2_installment_gap_days is not None:
        payload["term2_installment_gap_days"] = _normalize_gap(term2_installment_gap_days)
    if installment_count_options is not None:
        payload["installment_count_options"] = _normalize_options(installment_count_options)

    stmt = select(SiteSetting).where(SiteSetting.key == INSTALLMENT_POLICY_KEY)
    r = await db.execute(stmt)
    row = r.scalars().first()
    now = datetime.now(timezone.utc)

    if row:
        row.value_json = payload
        row.updated_at = now
    else:
        db.add(
            SiteSetting(
                key=INSTALLMENT_POLICY_KEY,
                value_json=payload,
                updated_at=now,
            )
        )
    await db.flush()
    return await get_installment_policy(db)
