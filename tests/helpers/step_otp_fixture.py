"""کمک‌کنندهٔ تست برای دروازه OTP فرم مرحله (اسناد / تعهدنامه)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.meta.student_step_forms import stamp_step_otp_verified
from app.models.operational_models import ProcessInstance


def field_specs_include_step_otp(field_specs: list[dict[str, Any]] | None) -> bool:
    for spec in field_specs or []:
        if (spec.get("type") or "").lower() == "step_otp":
            return True
    return False


async def stamp_instance_step_otp_verified(
    db: AsyncSession,
    instance_id,
    state_code: str,
) -> None:
    """فلگ سروری تأیید OTP را روی context نمونه می‌گذارد (برای flow-through)."""
    inst = await db.get(ProcessInstance, instance_id)
    if inst is None:
        raise AssertionError(f"instance not found: {instance_id}")
    inst.context_data = stamp_step_otp_verified(inst.context_data, state_code)
    flag_modified(inst, "context_data")
    await db.commit()
