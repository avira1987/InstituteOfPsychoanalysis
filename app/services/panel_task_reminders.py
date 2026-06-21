"""ذخیره و بازیابی نوتیفیکیشن‌های ثبت‌شدهٔ پنل (یادآوری روزانه و …)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import PanelTaskReminder


async def dismiss_panel_task_reminder(
    db: AsyncSession,
    *,
    reminder_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    r = await db.execute(
        select(PanelTaskReminder).where(
            PanelTaskReminder.id == reminder_id,
            PanelTaskReminder.user_id == user_id,
            PanelTaskReminder.dismissed_at.is_(None),
        )
    )
    row = r.scalars().first()
    if row is None:
        return False
    row.dismissed_at = datetime.now(timezone.utc)
    return True


async def load_active_panel_reminders(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    r = await db.execute(
        select(PanelTaskReminder)
        .where(
            PanelTaskReminder.user_id == user_id,
            PanelTaskReminder.dismissed_at.is_(None),
        )
        .order_by(desc(PanelTaskReminder.created_at))
        .limit(limit)
    )
    items: list[dict[str, Any]] = []
    for rem in r.scalars().all():
        items.append(
            {
                "notification_id": f"daily_overdue:{rem.id}",
                "kind": "daily_overdue",
                "title_fa": rem.title_fa,
                "summary_fa": rem.summary_fa or rem.title_fa,
                "action_path": rem.action_path,
                "sort_at": rem.created_at.isoformat() if rem.created_at else "",
                "instance_id": str(rem.instance_id) if rem.instance_id else None,
                "student_id": str(rem.student_id) if rem.student_id else None,
                "reminder_id": str(rem.id),
            }
        )
    return items
