"""بستن / حذف اعلان‌های اقدام از فید پنل."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import PanelActionNotificationDismissal, PanelFlashMessage
from app.services.panel_task_reminders import dismiss_panel_task_reminder


def _parse_notification_id(notification_id: str) -> tuple[str, str] | None:
    raw = (notification_id or "").strip()
    if not raw or ":" not in raw:
        return None
    kind, rest = raw.split(":", 1)
    kind = kind.strip().lower()
    rest = rest.strip()
    if not kind or not rest:
        return None
    return kind, rest


async def load_dismissed_notification_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> set[str]:
    r = await db.execute(
        select(PanelActionNotificationDismissal.notification_id).where(
            PanelActionNotificationDismissal.user_id == user_id
        )
    )
    return {row[0] for row in r.all() if row[0]}


async def _record_dismissal(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    notification_id: str,
) -> None:
    nid = (notification_id or "").strip()
    if not nid:
        return
    existing = await db.execute(
        select(PanelActionNotificationDismissal).where(
            PanelActionNotificationDismissal.user_id == user_id,
            PanelActionNotificationDismissal.notification_id == nid,
        )
    )
    if existing.scalars().first() is not None:
        return
    db.add(
        PanelActionNotificationDismissal(
            user_id=user_id,
            notification_id=nid,
        )
    )


async def dismiss_action_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    notification_id: str,
) -> bool:
    """بستن یک اعلان — یادآوری روزانه، فلش، یا ثبت dismiss برای موارد زندهٔ فرایند."""
    parsed = _parse_notification_id(notification_id)
    if parsed is None:
        return False
    kind, payload = parsed

    if kind == "daily_overdue":
        try:
            rid = uuid.UUID(payload)
        except ValueError:
            return False
        return await dismiss_panel_task_reminder(db, reminder_id=rid, user_id=user_id)

    if kind == "flash":
        try:
            fid = uuid.UUID(payload)
        except ValueError:
            return False
        r = await db.execute(
            delete(PanelFlashMessage).where(
                PanelFlashMessage.id == fid,
                PanelFlashMessage.user_id == user_id,
            )
        )
        return (r.rowcount or 0) > 0

    await _record_dismissal(db, user_id=user_id, notification_id=notification_id.strip())
    return True


async def dismiss_notifications_for_instance(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    instance_id: uuid.UUID,
) -> None:
    """پس از انجام اقدام روی یک نمونه — حذف اعلان‌های مرتبط از فید کاربر."""
    from app.models.operational_models import PanelTaskReminder

    iid = str(instance_id)
    await _record_dismissal(db, user_id=user_id, notification_id=f"process:{iid}")

    now = datetime.now(timezone.utc)
    r = await db.execute(
        select(PanelTaskReminder).where(
            PanelTaskReminder.user_id == user_id,
            PanelTaskReminder.instance_id == instance_id,
            PanelTaskReminder.dismissed_at.is_(None),
        )
    )
    for rem in r.scalars().all():
        rem.dismissed_at = now


async def prune_stale_task_reminders(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    active_instance_ids: set[str],
) -> None:
    """یادآوری‌های روزانهٔ مربوط به نمونه‌ای که دیگر در کارتابل کاربر نیست را می‌بندد."""
    from app.models.operational_models import PanelTaskReminder

    r = await db.execute(
        select(PanelTaskReminder).where(
            PanelTaskReminder.user_id == user_id,
            PanelTaskReminder.dismissed_at.is_(None),
            PanelTaskReminder.instance_id.isnot(None),
        )
    )
    now = datetime.now(timezone.utc)
    for rem in r.scalars().all():
        if str(rem.instance_id) not in active_instance_ids:
            rem.dismissed_at = now


def filter_dismissed_items(
    items: list[dict[str, Any]],
    dismissed_ids: set[str],
) -> list[dict[str, Any]]:
    if not dismissed_ids:
        return items
    return [it for it in items if (it.get("notification_id") or "") not in dismissed_ids]
