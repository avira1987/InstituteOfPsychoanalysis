"""ذخیره و بازیابی پیام‌های پاپ‌آپ UI برای پنل اعلان‌ها."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import PanelFlashMessage

_RETENTION_DAYS = 90
_MAX_PER_USER = 200


def _flash_to_notification(row: PanelFlashMessage) -> dict[str, Any]:
    level = (row.level or "success").strip().lower()
    title = "خطا" if level == "error" else "پیام سیستم"
    path = (row.source_path or "").strip()
    action_path = path if path.startswith("/") else "/panel/notifications?tab=messages"
    return {
        "notification_id": f"flash:{row.id}",
        "kind": "flash_message",
        "title_fa": title,
        "summary_fa": row.message or "",
        "action_path": action_path,
        "sort_at": row.created_at.isoformat() if row.created_at else "",
        "level": level,
        "flash_id": str(row.id),
    }


async def _prune_old_messages(db: AsyncSession, user_id: uuid.UUID) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    await db.execute(
        delete(PanelFlashMessage).where(
            PanelFlashMessage.user_id == user_id,
            PanelFlashMessage.created_at < cutoff,
        )
    )
    count_r = await db.execute(
        select(func.count()).select_from(PanelFlashMessage).where(
            PanelFlashMessage.user_id == user_id
        )
    )
    total = count_r.scalar() or 0
    if total <= _MAX_PER_USER:
        return
    excess = total - _MAX_PER_USER
    old_r = await db.execute(
        select(PanelFlashMessage.id)
        .where(PanelFlashMessage.user_id == user_id)
        .order_by(PanelFlashMessage.created_at.asc())
        .limit(excess)
    )
    old_ids = [row[0] for row in old_r.all()]
    if old_ids:
        await db.execute(
            delete(PanelFlashMessage).where(PanelFlashMessage.id.in_(old_ids))
        )


async def create_panel_flash_message(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    message: str,
    level: str = "success",
    source_path: str | None = None,
) -> PanelFlashMessage:
    text = (message or "").strip()
    if not text:
        raise ValueError("message is required")
    lvl = (level or "success").strip().lower()
    if lvl not in ("success", "error"):
        lvl = "success"
    path = (source_path or "").strip() or None
    row = PanelFlashMessage(
        user_id=user_id,
        message=text,
        level=lvl,
        source_path=path,
    )
    db.add(row)
    await db.flush()
    await _prune_old_messages(db, user_id)
    return row


async def load_panel_flash_messages(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    cap = min(max(limit, 1), 200)
    r = await db.execute(
        select(PanelFlashMessage)
        .where(PanelFlashMessage.user_id == user_id)
        .order_by(desc(PanelFlashMessage.created_at))
        .limit(cap)
    )
    return [_flash_to_notification(row) for row in r.scalars().all()]
