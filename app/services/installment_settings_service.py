"""خواندن و به‌روزرسانی سیاست اقساط (فاصلهٔ سررسید اقساط ترم دوم، گزینه‌های تعداد قسط)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import SiteSetting

INSTALLMENT_POLICY_KEY = "installment_policy"

DEFAULT_INSTALLMENT_POLICY: dict[str, Any] = {
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

    return {
        "term2_installment_gap_days": gap,
        "installment_count_options": opts,
        "updated_at": updated_at,
    }


async def update_installment_policy(
    db: AsyncSession,
    *,
    term2_installment_gap_days: int | None = None,
    installment_count_options: list[int] | None = None,
) -> dict[str, Any]:
    """ذخیرهٔ سیاست اقساط (upsert)."""
    current = await get_installment_policy(db)
    payload = {
        "term2_installment_gap_days": current["term2_installment_gap_days"],
        "installment_count_options": list(current["installment_count_options"]),
    }
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
