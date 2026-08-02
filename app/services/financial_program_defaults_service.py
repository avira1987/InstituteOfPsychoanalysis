"""پیش‌فرض‌های مالی برنامهٔ آموزشی (ثبت‌نام، درمان جلسه‌ای، کلاس، دوره) — ذخیره در site_settings.

شهریه و هزینهٔ مصاحبهٔ ترم (چهار فیلد آماده‌سازی پاییز) با همین کلید ذخیره می‌شوند تا
داشبورد مالی و فرایند آماده‌سازی ترم یک منبع حقیقت داشته باشند.
"""

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

# فیلدهای مشترک با فرم tuition_entry آماده‌سازی ترم پاییز (ریال)
TERM_TUITION_KEYS = (
    "per_unit_cost_introductory",
    "per_unit_cost_comprehensive",
    "interview_fee_introductory",
    "interview_fee_comprehensive",
)

# سایر پیش‌فرض‌های پرداخت (همان بخش داشبورد مالی) — مشترک با آماده‌سازی ترم
OTHER_PAYMENT_DEFAULT_KEYS = (
    "registration_interview_fee_rial",
    "registration_tuition_invoice_toman",
    "start_therapy_first_session_fee_rial",
    "extra_session_fee_rial",
    "default_therapy_session_fee_toman",
    "class_session_fee_toman",
    "course_session_fee_toman",
)

PREP_FINANCIAL_FORM_KEYS = TERM_TUITION_KEYS + OTHER_PAYMENT_DEFAULT_KEYS

_RIAL_PREP_KEYS = frozenset(
    {
        "per_unit_cost_introductory",
        "per_unit_cost_comprehensive",
        "interview_fee_introductory",
        "interview_fee_comprehensive",
        "registration_interview_fee_rial",
        "start_therapy_first_session_fee_rial",
        "extra_session_fee_rial",
    }
)
_TOMAN_PREP_KEYS = frozenset(
    {
        "registration_tuition_invoice_toman",
        "default_therapy_session_fee_toman",
        "class_session_fee_toman",
        "course_session_fee_toman",
    }
)
_OPTIONAL_ZERO_TOMAN_KEYS = frozenset({"class_session_fee_toman", "course_session_fee_toman"})


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
        # شهریهٔ ترم — صفر یعنی هنوز از آماده‌سازی/داشبورد ثبت نشده
        "per_unit_cost_introductory": 0,
        "per_unit_cost_comprehensive": 0,
        "interview_fee_introductory": 0,
        "interview_fee_comprehensive": 0,
    }


def _clamp_rial(v: Any, *, lo: int = 1_000, hi: int = 999_999_999_999_999) -> int:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def _clamp_rial_allow_zero(v: Any, *, hi: int = 999_999_999_999_999) -> int:
    """۰ = ثبت‌نشده؛ در غیر این صورت حداقل ۱۰۰۰."""
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return 0
    if n <= 0:
        return 0
    return max(1_000, min(hi, n))


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

    for key in TERM_TUITION_KEYS:
        if key in raw and raw[key] is not None and str(raw[key]).strip() != "":
            out[key] = _clamp_rial_allow_zero(raw[key])
        else:
            out[key] = _clamp_rial_allow_zero(raw.get(key, base.get(key, 0)))

    return out


def extract_term_tuition_patch_from_context(ctx: dict[str, Any] | None) -> dict[str, Any]:
    """از context آماده‌سازی ترم فیلدهای شهریه و سایر پیش‌فرض‌های پرداخت را بردار."""
    if not isinstance(ctx, dict):
        return {}
    patch: dict[str, Any] = {}
    for key in TERM_TUITION_KEYS:
        val = ctx.get(key)
        if val is None or str(val).strip() == "":
            continue
        try:
            n = int(round(float(val)))
        except (TypeError, ValueError):
            continue
        if n >= 1000:
            patch[key] = n

    for key in OTHER_PAYMENT_DEFAULT_KEYS:
        val = ctx.get(key)
        if val is None or str(val).strip() == "":
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        if key in _OPTIONAL_ZERO_TOMAN_KEYS:
            if num < 0:
                continue
            patch[key] = float(num)
            continue
        if key in _RIAL_PREP_KEYS:
            n = int(round(num))
            if n >= 1000:
                patch[key] = n
            continue
        if key in _TOMAN_PREP_KEYS:
            if num > 0:
                patch[key] = float(num)

    if "interview_fee_introductory" in patch and "registration_interview_fee_rial" not in patch:
        patch["registration_interview_fee_rial"] = patch["interview_fee_introductory"]
    return patch


async def _mirror_term_tuition_to_active_calendar(db: AsyncSession, normalized: dict[str, Any]) -> None:
    """آینهٔ فیلدهای ترم روی تقویم فعال تا resolve_registration_fees همان اعداد را ببیند."""
    try:
        from app.services.institute_calendar_service import get_active_calendar
    except Exception:
        return
    try:
        cal = await get_active_calendar(db)
    except Exception:
        return
    if cal is None:
        return
    extra = dict(cal.extra_data or {})
    tuition = dict(extra.get("tuition") or {})
    changed = False
    for key in TERM_TUITION_KEYS:
        val = normalized.get(key)
        try:
            n = int(val) if val is not None else 0
        except (TypeError, ValueError):
            n = 0
        if n >= 1000 and tuition.get(key) != n:
            tuition[key] = n
            changed = True
    if not changed:
        return
    tuition["published_at"] = datetime.now(timezone.utc).isoformat()
    tuition["synced_from"] = "financial_program_defaults"
    extra["tuition"] = tuition
    cal.extra_data = extra
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(cal, "extra_data")


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
            "شهریه، هزینهٔ مصاحبه و سایر پیش‌فرض‌های پرداخت با فرم «آماده‌سازی ترم پاییز» "
            "یک منبع دارند. پس از ثبت در آماده‌سازی، ویرایش بعدی از همین داشبورد مالی نیز ممکن است."
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
        *TERM_TUITION_KEYS,
    )
    merged = {k: current[k] for k in payload_keys}
    raw_patch = {k: patch[k] for k in payload_keys if k in patch and patch[k] is not None}
    for k, v in raw_patch.items():
        merged[k] = v

    # اگر فقط مصاحبهٔ آشنایی آمده، registration_interview را هم‌تراز کن
    if "interview_fee_introductory" in raw_patch and "registration_interview_fee_rial" not in raw_patch:
        try:
            iv = int(round(float(raw_patch["interview_fee_introductory"])))
            if iv >= 1000:
                merged["registration_interview_fee_rial"] = iv
                raw_patch["registration_interview_fee_rial"] = iv
        except (TypeError, ValueError):
            pass
    # اگر فقط مصاحبهٔ عمومی آمده و آشنایی خالی است، آشنایی را پر کن
    if "registration_interview_fee_rial" in raw_patch and "interview_fee_introductory" not in raw_patch:
        try:
            iv = int(round(float(raw_patch["registration_interview_fee_rial"])))
            if iv >= 1000 and int(merged.get("interview_fee_introductory") or 0) < 1000:
                merged["interview_fee_introductory"] = iv
                raw_patch["interview_fee_introductory"] = iv
        except (TypeError, ValueError):
            pass

    normalized = normalize_financial_program_payload({**merged, **raw_patch})

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
            *TERM_TUITION_KEYS,
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

    if any(k in raw_patch for k in TERM_TUITION_KEYS) or "registration_interview_fee_rial" in raw_patch:
        await _mirror_term_tuition_to_active_calendar(db, normalized)

    return await get_effective_financial_program_defaults(db)


async def sync_term_tuition_from_prep_context(db: AsyncSession, ctx: dict[str, Any] | None) -> dict[str, Any]:
    """ثبت شهریهٔ آماده‌سازی ترم در پیش‌فرض‌های مالی (منبع مشترک با داشبورد)."""
    patch = extract_term_tuition_patch_from_context(ctx)
    if not patch:
        return await get_effective_financial_program_defaults(db)
    return await update_financial_program_defaults(db, patch)
