"""ساخت خودکار اسلات مصاحبه از الگوهای هفتگی مصاحبه‌گر (منطقهٔ زمانی تهران)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models.operational_models import InterviewSlot, InterviewSlotRecurringRule, User

TEHRAN = ZoneInfo("Asia/Tehran")

# مالک الگو با نقش staff/admin → اسلات در استخر عمومی (بدون مصاحبه‌گر اختصاصی)
_POOL_RULE_OWNER_ROLES = frozenset({"admin", "staff"})


def _combine_tehran(day: date, t: time) -> datetime:
    return datetime.combine(day, t).replace(tzinfo=TEHRAN)


def _clamp_horizon_days(rule: InterviewSlotRecurringRule) -> int:
    cap = max(7, int(get_settings().INTERVIEW_RECURRING_MAX_HORIZON_DAYS))
    return max(1, min(int(rule.horizon_days or 21), cap))


def normalize_rule_weekdays(raw: Any) -> list[int] | None:
    if not isinstance(raw, list):
        return None
    out: list[int] = []
    for x in raw:
        try:
            i = int(x)
        except (TypeError, ValueError):
            return None
        if i < 0 or i > 6:
            return None
        out.append(i)
    seen: set[int] = set()
    unique = []
    for i in sorted(out):
        if i not in seen:
            seen.add(i)
            unique.append(i)
    return unique if unique else None


async def generate_interview_slots_from_recurring_rules(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """برای هر Rule فعال، در بازهٔ horizon اسلات آزاد در DB می‌سازد (بدون حذف دستی)."""
    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    stmt = select(InterviewSlotRecurringRule).where(InterviewSlotRecurringRule.is_active == True)
    rules = list((await db.execute(stmt)).scalars().all())

    created_total = 0
    per_rule: list[dict[str, Any]] = []

    today_tehran = now_utc.astimezone(TEHRAN).date()

    for rule in rules:
        days = normalize_rule_weekdays(rule.days_of_week)
        if not days:
            per_rule.append({"rule_id": str(rule.id), "error": "invalid_days_of_week"})
            continue

        horizon = _clamp_horizon_days(rule)
        n_created = 0
        start_t = rule.start_local_time
        end_t = rule.end_local_time
        if start_t is None or end_t is None:
            per_rule.append({"rule_id": str(rule.id), "error": "missing_time"})
            continue

        for offset in range(horizon + 1):
            d = today_tehran + timedelta(days=offset)
            if d.weekday() not in days:
                continue

            starts_local = _combine_tehran(d, start_t)
            ends_local = _combine_tehran(d, end_t)
            if ends_local <= starts_local:
                continue

            starts_at = starts_local.astimezone(timezone.utc)
            ends_at = ends_local.astimezone(timezone.utc)

            if ends_at <= now_utc:
                continue
            if starts_at <= now_utc:
                continue

            dup = (
                await db.execute(
                    select(InterviewSlot.id).where(
                        InterviewSlot.generated_from_rule_id == rule.id,
                        InterviewSlot.starts_at == starts_at,
                    )
                )
            ).first()
            if dup:
                continue

            interviewer_uid = rule.interviewer_user_id
            created_by = rule.interviewer_user_id
            owner = await db.get(User, rule.interviewer_user_id)
            if owner and (owner.role or "").strip() in _POOL_RULE_OWNER_ROLES:
                interviewer_uid = None

            slot = InterviewSlot(
                id=uuid.uuid4(),
                starts_at=starts_at,
                ends_at=ends_at,
                course_type=rule.course_type,
                mode=rule.mode or "online",
                location_fa=(rule.location_fa or "").strip() or None,
                meeting_link=(rule.meeting_link or "").strip() or None,
                label_fa=(rule.label_fa or "").strip() or None,
                created_by=created_by,
                interviewer_user_id=interviewer_uid,
                generated_from_rule_id=rule.id,
                assigned_student_id=None,
                assigned_instance_id=None,
            )
            db.add(slot)
            await db.flush()
            n_created += 1

        created_total += n_created
        per_rule.append({"rule_id": str(rule.id), "created": n_created})

    return {
        "created_total": created_total,
        "rules": per_rule,
        "at": now_utc.isoformat(),
    }


async def delete_unbooked_future_slots_generated_from_rule(db: AsyncSession, *, rule_id: uuid.UUID) -> int:
    """فقط اسلات آزادِ آینده که از همین Rule ساخته شده‌اند؛ رزروشده دست‌نخورده می‌ماند."""
    now_utc = datetime.now(timezone.utc)
    stmt = select(InterviewSlot).where(
        InterviewSlot.generated_from_rule_id == rule_id,
        InterviewSlot.assigned_student_id.is_(None),
        InterviewSlot.starts_at > now_utc,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for slot in rows:
        await db.delete(slot)
    if rows:
        await db.flush()
    return len(rows)
