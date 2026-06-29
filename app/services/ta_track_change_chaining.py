"""زنجیرهٔ خودکار فرایند ۵۱ — ارسال درخواست به کمیته پس از انتخاب مسیر."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, User

logger = logging.getLogger(__name__)


async def _resolve_system_actor_id(db) -> uuid.UUID:
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row:
        return row
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row if row else uuid.uuid4()


async def chain_ta_track_change_after_transition(
    db,
    engine: StateMachineEngine,
    instance: ProcessInstance,
    to_state: str,
    actor_id: uuid.UUID,
) -> None:
    """پس از path_chosen، گام سیستمی request_sent را تا course_committee_review پیش ببرد."""
    if instance.process_code != "ta_track_change":
        return
    if instance.is_completed or instance.is_cancelled:
        return
    if to_state != "path_selected":
        return

    sys_id = await _resolve_system_actor_id(db)
    result = await engine.execute_transition(
        instance.id,
        "request_sent",
        sys_id,
        "system",
        None,
    )
    if not result.success:
        logger.warning(
            "ta_track_change auto request_sent failed instance=%s: %s",
            instance.id,
            result.error,
        )
