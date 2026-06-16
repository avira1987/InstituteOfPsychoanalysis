"""Persist failed post-transition actions for operator retry."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import FailedAction, ProcessInstance


async def record_failed_action(
    db: AsyncSession,
    instance: ProcessInstance,
    action_type: str,
    action_payload: Optional[dict[str, Any]],
    error_message: str,
) -> FailedAction:
    row = FailedAction(
        id=uuid.uuid4(),
        instance_id=instance.id,
        action_type=action_type[:100],
        action_payload=action_payload,
        error_message=(error_message or "")[:2000],
    )
    db.add(row)
    await db.flush()
    return row


async def mark_failed_action_resolved(db: AsyncSession, action_id: uuid.UUID) -> None:
    row = await db.get(FailedAction, action_id)
    if row:
        row.resolved = True
        row.resolved_at = datetime.now(timezone.utc)
