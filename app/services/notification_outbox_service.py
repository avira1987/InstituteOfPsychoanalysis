"""Durable notification outbox with background retry worker."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.operational_models import NotificationOutbox
from app.services.sms_gateway import send_sms

logger = logging.getLogger(__name__)


async def enqueue_notification(
    db: AsyncSession,
    *,
    recipient: str,
    message: str,
    channel: str = "sms",
    template_key: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> NotificationOutbox:
    row = NotificationOutbox(
        id=uuid.uuid4(),
        channel=channel,
        recipient=recipient,
        message=message,
        template_key=template_key,
        status="pending",
        context_json=context,
        next_retry_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return row


async def process_outbox_batch(db: AsyncSession, *, limit: int = 50) -> int:
    now = datetime.now(timezone.utc)
    stmt = (
        select(NotificationOutbox)
        .where(
            NotificationOutbox.status.in_(("pending", "failed")),
            NotificationOutbox.retry_count < NotificationOutbox.max_retries,
            (NotificationOutbox.next_retry_at.is_(None)) | (NotificationOutbox.next_retry_at <= now),
        )
        .order_by(NotificationOutbox.created_at.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    sent = 0
    for row in rows:
        if row.channel != "sms":
            row.status = "failed"
            row.last_error = f"unsupported channel: {row.channel}"
            continue
        try:
            result = await send_sms(
                row.recipient,
                row.message,
                template_key=row.template_key,
                context=row.context_json or {},
            )
            if result.get("success"):
                row.status = "sent"
                row.sent_at = now
                row.last_error = None
                sent += 1
            else:
                row.status = "failed"
                row.retry_count += 1
                row.last_error = str(result.get("error") or "send failed")[:500]
                row.next_retry_at = now + timedelta(minutes=min(30, 2 ** row.retry_count))
        except Exception as e:
            row.status = "failed"
            row.retry_count += 1
            row.last_error = str(e)[:500]
            row.next_retry_at = now + timedelta(minutes=min(30, 2 ** row.retry_count))
            logger.exception("outbox send failed id=%s", row.id)
    return sent


class NotificationOutboxWorker:
    def __init__(self):
        self._running = False

    def stop(self):
        self._running = False

    async def start_loop(
        self, db_factory: async_sessionmaker, interval_seconds: int = 60
    ) -> None:
        self._running = True
        while self._running:
            try:
                async with db_factory() as db:
                    n = await process_outbox_batch(db)
                    await db.commit()
                    if n:
                        logger.info("Notification outbox: sent %s messages", n)
            except Exception:
                logger.exception("Notification outbox worker error")
            await asyncio.sleep(interval_seconds)


notification_outbox_worker = NotificationOutboxWorker()
