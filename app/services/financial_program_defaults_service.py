"""پیش‌فرض‌های مالی برنامهٔ آموزشی (ثبت‌نام، درمان جلسه‌ای، کلاس، دوره) — ذخیره در site_settings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.operational_models import SiteSetting
from app.services.payment_service import PaymentService

FINANCIAL_PROGRAM_DEFAULTS_KEY = "financial_program_defaults"


def _base_from_app_settings() -> dict[str, Any]:
    st = get_settings()
    therapy_toman = float(getattr(PaymentService, "DEFAULT_SESSION_FEE", 500_000) or 500_000)
    return {
        "registration_interview_fee_rial": int(getattr(st, "REGISTRATION_INTERVIEW_FEE_RIAL", 5_000_000)),
        "registration_tuition_invoice_toman": float(getattr(st, "REGISTRATION_TUITION_INVOICE_TOMAN", 120_000_000)),
        "start_therapy_first_session_fee_rial": int(getattr(st, "START_THERAPY_FIRST_SESSION_FEE_RIAL", 10_000_000)),
        "extra_session_fee_rial": int(getattr(st, "EXTRA_SESSION_FEE_RIAL", 7_500_000)),
        "default_therapy_session_fee_toman": therapy_toman,
        # مرجع UI برای کلاس‌ها و دوره‌های جلسه‌ای (نه درمان) — عدد صفر یعنی «تعریف نشده»
        "class_session_fee_toman": 0.0,
        "course_session_fee_toman": 0.0,
    }


def _clamp_rial(v: Any, *, lo: int = 1_000, hi: int = 999_999_999_999_999) -> int:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def _clamp_toman_nonneg(v: Any, *, hi: float = 1e15) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    if x <= 0:
        return 0.0
    return max(0.0, min(hi, x))


def normalize_financial_program_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    """اعتبارسنجی و هم‌ترازی با پیش‌فرض اپلیکیشن."""
    base = _base_from_app_settings()
    if not isinstance(raw, dict):
        return dict(base)
    out = dict(base)
    out["registration_interview_fee_rial"] = _clamp_rial(
        raw.get("registration_interview_fee_rial", base["registration_interview_fee_rial"])
    )
    try:
        tuit = float(raw.get("registration_tuition_invoice_toman", base["registration_tuition_invoice_toman"]))
    except (TypeError, ValueError):
        tuit = float(base["registration_tuition_invoice_toman"])
    if tuit <= 0:
        tuit = float(base["registration_tuition_invoice_toman"])
    out["registration_tuition_invoice_toman"] = min(tuit, 1e15)

    out["start_therapy_first_session_fee_rial"] = _clamp_rial(
        raw.get("start_therapy_first_session_fee_rial", base["start_therapy_first_session_fee_rial"])
    )
    out["extra_session_fee_rial"] = _clamp_rial(
        raw.get("extra_session_fee_rial", base["extra_session_fee_rial"])
    )
    dtf = raw.get("default_therapy_session_fee_toman", base["default_therapy_session_fee_toman"])
    out["default_therapy_session_fee_toman"] = _clamp_toman_nonneg(dtf, hi=float(base["default_therapy_session_fee_toman"]) * 100 + 1e12) or float(
        base["default_therapy_session_fee_toman"]
    )

    clf = raw.get("class_session_fee_toman")
    crs = raw.get("course_session_fee_toman")
    out["class_session_fee_toman"] = _clamp_toman_nonneg(clf) if clf is not None else float(base["class_session_fee_toman"])
    out["course_session_fee_toman"] = _clamp_toman_nonneg(crs) if crs is not None else float(base["course_session_fee_toman"])

    return out


async def get_effective_financial_program_defaults(db: AsyncSession) -> dict[str, Any]:
    row = None
    try:
        stmt = select(SiteSetting).where(SiteSetting.key == FINANCIAL_PROGRAM_DEFAULTS_KEY)
        r = await db.execute(stmt)
        row = r.scalars().first()
    except (ProgrammingError, DBAPIError):
        row = None

    merged: dict[str, Any] = {}
    updated_at: str | None = None
    if row and isinstance(row.value_json, dict):
        merged.update(row.value_json)
        if row.updated_at:
            updated_at = row.updated_at.isoformat()

    normalized = normalize_financial_program_payload(merged)

    extra_toman_rounded = round(normalized["extra_session_fee_rial"] / 10.0, 6)
    return {
        **normalized,
        "extra_session_fee_toman": float(extra_toman_rounded),
        "updated_at": updated_at,
        "sources_note": (
            "پس از ذخیره در این فرم، مقادیر برای پرداخت‌های پیش‌فرض استفاده می‌شوند؛ "
            "تا قبل از اولین ذخیره از تنظیمات سرور (متغیرهای env یا مقادیر پیش‌فرض کد) خوانده می‌شود."
        ),
    }


async def update_financial_program_defaults(db: AsyncSession, patch: dict[str, Any]) -> dict[str, Any]:
    current = await get_effective_financial_program_defaults(db)
    payload_keys = (
        "registration_interview_fee_rial",
        "registration_tuition_invoice_toman",
        "start_therapy_first_session_fee_rial",
        "extra_session_fee_rial",
        "default_therapy_session_fee_toman",
        "class_session_fee_toman",
        "course_session_fee_toman",
    )
    merged = {k: current[k] for k in payload_keys}
    for k in payload_keys:
        if k not in patch:
            continue
        if patch[k] is None:
            continue
        merged[k] = patch[k]
    normalized = normalize_financial_program_payload(merged)

    stmt = select(SiteSetting).where(SiteSetting.key == FINANCIAL_PROGRAM_DEFAULTS_KEY)
    r = await db.execute(stmt)
    row = r.scalars().first()
    now = datetime.now(timezone.utc)

    store = {
        k: normalized[k]
        for k in (
            "registration_interview_fee_rial",
            "registration_tuition_invoice_toman",
            "start_therapy_first_session_fee_rial",
            "extra_session_fee_rial",
            "default_therapy_session_fee_toman",
            "class_session_fee_toman",
            "course_session_fee_toman",
        )
    }

    if row:
        row.value_json = store
        row.updated_at = now
    else:
        db.add(
            SiteSetting(
                key=FINANCIAL_PROGRAM_DEFAULTS_KEY,
                value_json=store,
                updated_at=now,
            )
        )
    await db.flush()
    return await get_effective_financial_program_defaults(db)
