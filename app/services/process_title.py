"""تطبیق عنوان فرایند برای تشخیص تکراری (بر اساس نام فارسی، نه کد)."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_models import ProcessDefinition

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def normalize_process_title(name: str) -> str:
    """
    نرمال‌سازی برای مقایسهٔ عنوان‌ها: برش، NFC، یکسان‌سازی فاصله، ارقام فارسی به انگلیسی.
    """
    if not name or not isinstance(name, str):
        return ""
    t = name.strip()
    t = unicodedata.normalize("NFC", t)
    t = t.translate(_PERSIAN_DIGITS)
    t = re.sub(r"\s+", " ", t)
    return t.casefold()


async def find_process_by_normalized_title(
    db: AsyncSession,
    name_fa: str,
) -> Optional[ProcessDefinition]:
    """اولین فرایندی که عنوان نرمال‌شده‌اش با عنوان ورودی یکی باشد."""
    target = normalize_process_title(name_fa)
    if not target:
        return None
    result = await db.execute(select(ProcessDefinition).order_by(ProcessDefinition.id))
    for p in result.scalars().all():
        if normalize_process_title(p.name_fa) == target:
            return p
    return None
