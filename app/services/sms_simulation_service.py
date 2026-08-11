"""ذخیره و خواندن پیامک‌های شبیه‌سازی‌شده (SMS_PROVIDER=log) برای پاپ‌آپ تست پنل."""

from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models.operational_models import SmsSimulationDismissal, SmsSimulationOutbox, User
from app.services.sms_gateway import normalize_ir_mobile

logger = logging.getLogger(__name__)

VALID_KINDS = frozenset({"otp", "notification", "pattern", "free_text"})
STUDENT_SMS_HISTORY_EXCLUDED_TEMPLATE_KEYS = frozenset(
    {"student_portal_welcome_credentials", "otp_login"}
)
_MOBILE_IR = re.compile(r"^09\d{9}$")

# جمع‌آوری پیامک‌های یک درخواست HTTP (مثلاً trigger فرایند) برای برگرداندن فوری به UI
_capture_batch: ContextVar[list[dict] | None] = ContextVar("sms_sim_capture_batch", default=None)


def entry_dict(
    *,
    sms_id: str,
    phone: str,
    message: str,
    kind: str,
    template_key: str | None = None,
    created_at: datetime | None = None,
) -> dict:
    ts = created_at or datetime.now(timezone.utc)
    return {
        "id": str(sms_id),
        "phone": phone,
        "message": message or "",
        "kind": kind,
        "template_key": template_key,
        "created_at": ts.isoformat() if ts else None,
    }


def begin_capture() -> None:
    """شروع جمع‌آوری simulated_sms در scope همین درخواست."""
    _capture_batch.set([])


def drain_capture() -> list[dict]:
    """خواندن و پاک‌کردن batch جمع‌شده."""
    batch = _capture_batch.get(None)
    _capture_batch.set(None)
    return list(batch) if batch else []


def _emit_capture(entry: dict) -> None:
    batch = _capture_batch.get(None)
    if batch is not None and entry.get("message"):
        batch.append(entry)


def inbox_mobile_for_user(user: User) -> str:
    """شناسه موبایل برای inbox پاپ‌آپ: ستون phone؛ اگر خالی باشد نام کاربری=موبایل (مثل دانشجو)."""
    cand = normalize_ir_mobile((getattr(user, "phone", None) or "").strip())
    if _MOBILE_IR.fullmatch(cand):
        return cand
    cand2 = normalize_ir_mobile((getattr(user, "username", None) or "").strip())
    if _MOBILE_IR.fullmatch(cand2):
        return cand2
    return ""


def simulation_recording_enabled() -> bool:
    s = get_settings()
    return (getattr(s, "SMS_SIMULATION_UI", False) and (s.SMS_PROVIDER or "log").lower() == "log")


def simulation_popup_enabled() -> bool:
    """پاپ‌آپ و polling فعال — حالت log یا mirror پس از ارسال واقعی."""
    return simulation_recording_enabled() or simulation_mirror_real_sends()


def simulation_mirror_real_sends() -> bool:
    """ثبت در outbox برای پاپ‌آپ حتی وقتی ارسال واقعی ملی‌پیامک است."""
    s = get_settings()
    if not getattr(s, "SMS_SIMULATION_UI", False):
        return False
    if (s.SMS_PROVIDER or "log").lower() == "log":
        return False
    return bool(getattr(s, "SMS_SIMULATION_MIRROR_REAL_SEND", False))


def _popup_watcher_role_set(settings) -> set[str] | None:
    raw = (getattr(settings, "SMS_SIMULATION_POPUP_WATCHER_ROLES", "") or "").strip()
    if not raw:
        return None
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def user_sees_global_sms_popup_feed(user: User) -> bool:
    """فید یکپارچهٔ همهٔ پیامک‌های شبیه‌سازی‌شده — برای نقش دانشجو همیشه غیرفعال."""
    if not simulation_popup_enabled():
        return False
    settings = get_settings()
    if not getattr(settings, "SMS_SIMULATION_POPUP_SHOW_ALL", False):
        return False
    role = (user.role or "").strip().lower()
    if role == "student":
        return False
    watchers = _popup_watcher_role_set(settings)
    if watchers is None:
        return True
    return role in watchers


def simulation_popup_show_all_setting() -> bool:
    """مقدار تنظیمات برای پاسخ API (UI)."""
    return bool(getattr(get_settings(), "SMS_SIMULATION_POPUP_SHOW_ALL", False))


def student_sms_history_available() -> bool:
    """تاریخچهٔ inline در پنل دانشجو — log یا mirror پس از ارسال واقعی."""
    return simulation_recording_enabled() or simulation_mirror_real_sends()


def _student_sms_history_row_filters():
    """بدون کد ورود و بدون پیامک نام کاربری/رمز پورتال."""
    excluded = list(STUDENT_SMS_HISTORY_EXCLUDED_TEMPLATE_KEYS)
    return (
        SmsSimulationOutbox.kind != "otp",
        or_(
            SmsSimulationOutbox.template_key.is_(None),
            SmsSimulationOutbox.template_key.not_in(excluded),
        ),
    )


async def record_simulated_sms_in_request_session(
    db: AsyncSession,
    phone: str,
    message: str,
    *,
    kind: str,
    template_key: str | None = None,
) -> str | None:
    """ثبت outbox روی همان session درخواست (مثلاً تراکنش request_otp) بدون commit مستقل."""
    if not simulation_recording_enabled():
        return None
    kind_norm = (kind or "free_text").strip()
    if kind_norm not in VALID_KINDS:
        kind_norm = "free_text"
    to = normalize_ir_mobile(phone)
    if not to or not _MOBILE_IR.fullmatch(to):
        return None
    row = SmsSimulationOutbox(
        id=uuid.uuid4(),
        phone=to,
        message=message or "",
        kind=kind_norm,
        template_key=(template_key or "").strip() or None,
        created_at=datetime.now(timezone.utc),
    )
    sid = str(row.id)
    entry = entry_dict(
        sms_id=sid,
        phone=to,
        message=message or "",
        kind=kind_norm,
        template_key=row.template_key,
        created_at=row.created_at,
    )
    try:
        db.add(row)
        await db.flush()
    except Exception:
        logger.warning("sms_simulation: failed record in request session", exc_info=True)
    _emit_capture(entry)
    return sid


async def mirror_sms_for_popup(
    phone: str,
    message: str,
    *,
    kind: str = "notification",
    template_key: str | None = None,
) -> str | None:
    """پاپ‌آپ تست: ذخیرهٔ متن پیامک پس از ارسال واقعی (mellipayamak)."""
    if not simulation_mirror_real_sends():
        return None
    return await record_simulated_sms(
        phone, message, kind=kind, template_key=template_key
    )


async def record_simulated_sms(
    phone: str,
    message: str,
    *,
    kind: str,
    template_key: str | None = None,
) -> str | None:
    """یک رکورد outbox می‌سازد و شناسهٔ UUID (رشته) برمی‌گرداند؛ در صورت خطا None."""
    if not simulation_recording_enabled() and not simulation_mirror_real_sends():
        return None
    kind_norm = (kind or "free_text").strip()
    if kind_norm not in VALID_KINDS:
        kind_norm = "free_text"
    to = normalize_ir_mobile(phone)
    if not to or not _MOBILE_IR.fullmatch(to):
        logger.warning("sms_simulation: skipped record (invalid phone)")
        return None
    row = SmsSimulationOutbox(
        id=uuid.uuid4(),
        phone=to,
        message=message or "",
        kind=kind_norm,
        template_key=(template_key or "").strip() or None,
        created_at=datetime.now(timezone.utc),
    )
    sid = str(row.id)
    entry = entry_dict(
        sms_id=sid,
        phone=to,
        message=message or "",
        kind=kind_norm,
        template_key=row.template_key,
        created_at=row.created_at,
    )
    try:
        async with async_session_factory() as db:
            db.add(row)
            await db.commit()
    except Exception:
        logger.warning("sms_simulation: failed to record outbox row", exc_info=True)
    _emit_capture(entry)
    return sid


async def list_pending_for_user(
    db: AsyncSession,
    user: User,
    *,
    since: datetime | None = None,
    limit: int = 20,
) -> list[dict]:
    """پیامک‌های شبیه‌سازی‌شده؛ برای ناظر (global فید): همه به‌جز dismiss شده؛ برای بقیه: فقط خط گیرنده=شماره کاربر."""
    if not simulation_recording_enabled():
        return []

    lim = max(1, min(int(limit or 20), 50))
    dismissed = select(SmsSimulationDismissal.sms_id).where(SmsSimulationDismissal.user_id == user.id)

    if user_sees_global_sms_popup_feed(user):
        stmt = (
            select(SmsSimulationOutbox)
            .where(SmsSimulationOutbox.id.not_in(dismissed))
            .order_by(SmsSimulationOutbox.created_at.asc())
            .limit(lim)
        )
    else:
        me = inbox_mobile_for_user(user)
        if not me:
            return []
        stmt = (
            select(SmsSimulationOutbox)
            .where(SmsSimulationOutbox.phone == me)
            .where(SmsSimulationOutbox.id.not_in(dismissed))
            .order_by(SmsSimulationOutbox.created_at.asc())
            .limit(lim)
        )
    if since is not None:
        stmt = stmt.where(SmsSimulationOutbox.created_at > since)

    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": str(r.id),
            "phone": r.phone,
            "message": r.message,
            "kind": r.kind,
            "template_key": r.template_key,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def _outbox_row_to_dict(r: SmsSimulationOutbox) -> dict:
    return {
        "id": str(r.id),
        "phone": r.phone,
        "message": r.message,
        "kind": r.kind,
        "template_key": r.template_key,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


async def list_student_sms_history(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 10,
) -> list[dict]:
    """پیامک‌های ارسالی به خط دانشجو (بدون OTP و بدون welcome credentials) — شامل dismiss‌شده‌ها."""
    if not student_sms_history_available():
        return []

    me = inbox_mobile_for_user(user)
    if not me:
        return []

    lim = max(1, min(int(limit or 10), 30))
    stmt = (
        select(SmsSimulationOutbox)
        .where(SmsSimulationOutbox.phone == me)
        .where(*_student_sms_history_row_filters())
        .order_by(SmsSimulationOutbox.created_at.desc())
        .limit(lim)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_outbox_row_to_dict(r) for r in rows]


async def dismiss(db: AsyncSession, user: User, sms_id: uuid.UUID) -> bool:
    """Dismiss پاپ‌آپ برای این کاربر؛ ناظر سراسری هر ردیفی را می‌تواند ببندد، بقیه فقط پیام به شمارهٔ خود."""
    if not simulation_recording_enabled():
        return False
    row = await db.get(SmsSimulationOutbox, sms_id)
    if row is None:
        return False
    if user_sees_global_sms_popup_feed(user):
        pass
    else:
        me = inbox_mobile_for_user(user)
        if not me or row.phone != me:
            return False
    ex = (
        await db.execute(
            select(SmsSimulationDismissal).where(
                SmsSimulationDismissal.sms_id == sms_id,
                SmsSimulationDismissal.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if ex is not None:
        return True
    db.add(
        SmsSimulationDismissal(
            sms_id=sms_id,
            user_id=user.id,
            dismissed_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()
    return True
