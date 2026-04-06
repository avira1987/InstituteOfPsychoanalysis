"""Outbound integration (مثلاً LMS) و ثبت رویداد روی نمونهٔ فرایند.

اگر آدرس وب‌هوک تنظیم نشده باشد، فقط روی ``context_data.integration_events`` لاگ می‌شود
(بدون وابستگی به سامانهٔ بیرونی). برای آموزش و قرارداد payload نگاه کنید به
``docs/ACTIONS_AND_INTEGRATION_FA.md``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_EVENTS = 100


def append_integration_event(instance, action_type: str, detail: dict[str, Any]) -> None:
    """یک رویداد ساخت‌یافته به ``instance.context_data['integration_events']`` اضافه می‌کند."""
    ctx = dict(instance.context_data or {})
    events = list(ctx.get("integration_events") or [])
    events.append({"action": action_type, **detail})
    if len(events) > MAX_EVENTS:
        events = events[-MAX_EVENTS:]
    ctx["integration_events"] = events
    instance.context_data = ctx
    flag_modified(instance, "context_data")


async def post_optional_webhook(
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 15.0,
) -> Optional[dict[str, Any]]:
    """در صورت تنظیم ``LMS_INTEGRATION_WEBHOOK_URL``، POST JSON؛ وگرنه ``None``."""
    settings = get_settings()
    url = (settings.LMS_INTEGRATION_WEBHOOK_URL or "").strip()
    if not url:
        return None
    headers: dict[str, str] = {}
    secret = (settings.LMS_INTEGRATION_SECRET or "").strip()
    if secret:
        headers["X-Integration-Secret"] = secret
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {"status_code": r.status_code, "text": (r.text or "")[:500]}
    except Exception as e:
        logger.warning("LMS webhook POST failed: %s", e)
        return {"error": str(e)}


async def notify_integration(
    action_type: str,
    instance_id: UUID,
    student_id: UUID,
    process_code: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """پاکت استاندارد برای وب‌هوک؛ اگر URL نباشد ``skipped`` برمی‌گرداند."""
    payload = {
        "event": "integration_action",
        "action_type": action_type,
        "instance_id": str(instance_id),
        "student_id": str(student_id),
        "process_code": process_code,
        **(extra or {}),
    }
    result = await post_optional_webhook(payload)
    if result is None:
        return {"skipped": True, "reason": "LMS_INTEGRATION_WEBHOOK_URL not set"}
    return result
