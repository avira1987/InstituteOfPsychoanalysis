"""SMS when a process instance is started for a student (any actor)."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meta_models import ProcessDefinition
from app.models.operational_models import ProcessInstance, Student, User
from app.services.notification_service import notification_service
from app.services.sms_gateway import normalize_ir_mobile

logger = logging.getLogger(__name__)

# Automated / chain-driven processes: no "process started" SMS noise.
_SKIP_START_SMS_PROCESS_CODES = frozenset({"lesson_start_per_term"})


async def _student_phone(db: AsyncSession, student_id) -> Optional[str]:
    stmt = (
        select(User.phone)
        .join(Student, Student.user_id == User.id)
        .where(Student.id == student_id)
    )
    raw = (await db.execute(stmt)).scalar_one_or_none()
    if not raw or not str(raw).strip():
        return None
    normalized = normalize_ir_mobile(str(raw).strip())
    return normalized or str(raw).strip()


async def notify_manual_process_started(
    db: AsyncSession,
    instance: ProcessInstance,
    process_def: ProcessDefinition,
) -> Optional[str]:
    """Notify the student by SMS that a process was started (portal, staff, or automation)."""
    if (instance.process_code or "") in _SKIP_START_SMS_PROCESS_CODES:
        logger.info(
            "process start SMS skipped (process excluded): instance=%s process=%s",
            instance.id,
            instance.process_code,
        )
        return "skipped"

    phone = await _student_phone(db, instance.student_id)
    if not phone:
        logger.info(
            "process start SMS skipped (no phone): instance=%s process=%s",
            instance.id,
            instance.process_code,
        )
        return "no_phone"

    process_name = (process_def.name_fa or process_def.code or instance.process_code).strip()
    ctx = {
        "process_name_fa": process_name,
        "process_code": instance.process_code,
    }
    try:
        await notification_service.send_notification(
            "sms",
            "manual_process_started",
            phone,
            ctx,
        )
    except Exception:
        logger.exception(
            "process start SMS failed: instance=%s process=%s",
            instance.id,
            instance.process_code,
        )
        return "sms_failed"
    return "sms_sent"
