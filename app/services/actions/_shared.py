"""Module-level helpers shared by the action mixins.

Moved verbatim out of action_handler.py when it was split by domain.
"""

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any, List
import json
import logging
import re
import uuid

"""Action Handler - Executes transition actions from process metadata.

This is the bridge between the state machine engine (which reads metadata and
changes states) and the actual business logic (SMS, session management, etc.).

When a transition fires, its `actions` list is published via EventBus.
This handler subscribes to those events and dispatches each action to
the appropriate service method.
"""


logger = logging.getLogger(__name__)


_LIVE_SESSION_PREP_CODES = frozenset({
    "live_supervision_session_prep",
    "live_therapy_observation_session_prep",
})


_LIVE_SESSION_COURSE_KEYWORDS = {
    "live_supervision_session_prep": ("supervision", "سوپرویژن"),
    "live_therapy_observation_session_prep": ("observation", "مشاهده", "therapy_observation"),
}


def parse_therapy_session_id_list(raw) -> list[uuid.UUID]:
    """لیست شناسهٔ جلسات درمان از payload/فرم."""
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                raw = json.loads(s)
            except (json.JSONDecodeError, TypeError):
                raw = [x.strip() for x in s.split(",") if x.strip()]
        else:
            raw = [x.strip() for x in s.replace("،", ",").split(",") if x.strip()]
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[uuid.UUID] = []
    for x in raw:
        try:
            out.append(uuid.UUID(str(x)))
        except (TypeError, ValueError):
            continue
    return out


async def validate_therapy_reduction_preflight(
    db: AsyncSession,
    instance: ProcessInstance,
    payload: dict,
    student: Student,
) -> Optional[str]:
    """
    اعتبارسنجی payload قبل از ترنزیشن sessions_selected.
    برمی‌گرداند رشتهٔ خطا یا None.
    """
    merged = {**_as_mapping(instance.context_data), **(payload or {})}
    rem_raw = merged.get("remaining_sessions_after_reduction")
    if rem_raw is None and merged.get("new_weekly_sessions") is not None:
        try:
            rem_raw = int(merged["new_weekly_sessions"])
        except (TypeError, ValueError):
            rem_raw = None
    try:
        new_weekly = int(rem_raw) if rem_raw is not None else None
    except (TypeError, ValueError):
        new_weekly = None
    if new_weekly is None or new_weekly < 1:
        return "تعداد جلسات هفتگی پس از کاهش را در فرم مشخص کنید (عدد معتبر ≥ ۱)."

    old_ws = int(student.weekly_sessions or 1)
    if new_weekly >= old_ws:
        return "برای کاهش، تعداد جلسات هفتگی پس از تغییر باید کمتر از برنامهٔ فعلی باشد."

    selected_ids = parse_therapy_session_id_list(merged.get("selected_sessions"))
    required = max(1, old_ws - new_weekly)
    if len(selected_ids) < required:
        return (
            f"حداقل {required} جلسهٔ آتی برنامه‌ریزی‌شده را برای لغو انتخاب کنید "
            f"(انتخاب‌شده: {len(selected_ids)})."
        )

    today = datetime.now(timezone.utc).date()
    for sid in selected_ids:
        r = await db.execute(
            select(TherapySession).where(
                TherapySession.id == sid,
                TherapySession.student_id == instance.student_id,
            )
        )
        ts = r.scalars().first()
        if not ts:
            return "یکی از جلسات انتخاب‌شده یافت نشد یا متعلق به شما نیست."
        if ts.is_extra:
            return "جلسات فوق‌العاده را نمی‌توان از این مسیر لغو کرد."
        if ts.status != "scheduled":
            return f"فقط جلسات «برنامه‌ریزی‌شده» قابل انتخاب هستند ({ts.session_date})."
        if ts.session_date < today:
            return "جلسات گذشته را نمی‌توان انتخاب کرد."

    return None


async def validate_supervision_reduction_preflight(
    db: AsyncSession,
    instance: ProcessInstance,
    payload: dict,
    student: Student,
) -> Optional[str]:
    """
    اعتبارسنجی payload قبل از ترنزیشن sessions_selected (فرایند ۲۴).
    برمی‌گرداند رشتهٔ خطا یا None.
    """
    merged = {**_as_mapping(instance.context_data), **(payload or {})}
    try:
        weekly = int(merged.get("supervision_weekly_sessions") or 1)
    except (TypeError, ValueError):
        weekly = 1
    if weekly < 2:
        return "این مسیر فقط برای دانشجویان با ۲ جلسه یا بیشتر سوپرویژن در هفته است."

    selected = _parse_supervision_reduction_selected_list(merged.get("selected_sessions"))
    if not selected:
        return "حداقل یک جلسهٔ سوپرویژن برای حذف انتخاب کنید."

    remaining = weekly - len(selected)
    if remaining < 1:
        return "حداقل یک جلسهٔ سوپرویژن در هفته باید باقی بماند."

    max_remove = weekly - 1
    if len(selected) > max_remove:
        return f"حداکثر {max_remove} جلسه را می‌توانید حذف کنید (انتخاب‌شده: {len(selected)})."

    return None


def _parse_supervision_reduction_selected_list(raw) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x is not None and str(x).strip()]
            except (json.JSONDecodeError, TypeError):
                return []
        return [p for p in re.split(r"[,،\s]+", s) if p]
    return [str(raw).strip()]


def _as_mapping(val) -> dict:
    """JSONB یا رشتهٔ JSON قدیمی — مثل StateMachineEngine._as_mapping؛ جلوگیری از dict(str) و خطای length 1."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return dict(val)
    if isinstance(val, str):
        s = val.strip()
        if not s or s.lower() in ("null", "none"):
            return {}
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _parse_iso_date_only(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def _combine_date_time_tehran(d: date, time_str: Optional[str]) -> Optional[datetime]:
    if d is None:
        return None
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Tehran")
        ts = (time_str or "").strip()
        if not ts:
            return datetime(d.year, d.month, d.day, 9, 0, tzinfo=tz)
        parts = ts.replace(":", " ").split()
        h = int(parts[0]) if parts else 9
        m = int(parts[1]) if len(parts) > 1 else 0
        sec = int(parts[2]) if len(parts) > 2 else 0
        return datetime(d.year, d.month, d.day, h, m, sec, tzinfo=tz)
    except Exception:
        return None


def _resolve_therapy_session_increase_schedule(ctx: dict) -> tuple[date, Optional[datetime]]:
    """تاریخ/زمان جلسهٔ جدید برای فرایند افزایش جلسات هفتگی درمان."""
    alt_d = _parse_iso_date_only(ctx.get("therapist_alternative_date"))
    alt_t = (ctx.get("therapist_alternative_time_hhmm") or "").strip()
    std_d = _parse_iso_date_only(ctx.get("first_session_date"))
    std_t = (ctx.get("preferred_time_hhmm") or "").strip()
    if alt_d and alt_t:
        st = _combine_date_time_tehran(alt_d, alt_t)
        return alt_d, st.astimezone(timezone.utc) if st else None and alt_d
    if alt_d and not alt_t:
        st = _combine_date_time_tehran(alt_d, std_t or None)
        d = alt_d
    elif std_d:
        d = std_d
        st = _combine_date_time_tehran(std_d, std_t or None)
    else:
        d = datetime.now(timezone.utc).date()
        st = _combine_date_time_tehran(d, std_t or None)
    st_utc = st.astimezone(timezone.utc) if st else None
    return d, st_utc


def _resolve_extra_session_datetime(ctx: dict) -> tuple[date, Optional[datetime]]:
    """تاریخ/زمان توافق‌شده برای جلسه اضافی از فیلدهای فرم و payload."""
    merged = dict(ctx)
    date_keys = (
        "agreed_session_date",
        "confirmed_alternative_date",
        "new_preferred_date",
        "agreed_date",
        "alternative_date",
        "preferred_date",
    )
    time_keys = (
        "agreed_session_time",
        "confirmed_alternative_time",
        "new_preferred_time",
        "agreed_time",
        "alternative_time",
        "preferred_time",
    )
    d: Optional[date] = None
    for k in date_keys:
        d = _parse_iso_date_only(merged.get(k))
        if d:
            break
    if not d:
        d = datetime.now(timezone.utc).date()
    tstr = None
    for k in time_keys:
        v = merged.get(k)
        if v is not None and str(v).strip():
            tstr = str(v).strip()
            break
    st = _combine_date_time_tehran(d, tstr)
    return d, st
