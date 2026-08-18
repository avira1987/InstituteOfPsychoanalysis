"""شماره پروانه فعالیت انستیتو — منبع مشترک فرم پذیرش و آماده‌سازی ترم.

مقدار روی extra_data پروندهٔ عملیاتی (INST-OPS) ذخیره می‌شود تا به همان
رکوردی وصل باشد که فرایندهای آماده‌سازی پاییز/زمستان روی آن اجرا می‌شوند.
ویرایش بعدی بدون بازگشت فرایند، از صفحهٔ پیش‌نیازها ممکن است.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.services.institute_operational_anchor import ensure_institute_operational_student

LICENSE_NUMBER_KEY = "activity_license_number"
LICENSE_SOURCE_KEY = "activity_license_source"
LICENSE_UPDATED_AT_KEY = "activity_license_updated_at"

LICENSE_STATUS_CHANGED = "تغییر کرده"
LICENSE_STATUS_UNCHANGED = "بدون تغییر"

SOURCE_PREP = "prep"
SOURCE_MANUAL = "manual"


def _extra_map(extra: Any) -> dict[str, Any]:
    if isinstance(extra, Mapping):
        return dict(extra)
    return {}


def _normalize_number(raw: Any) -> str:
    return str(raw or "").strip()


def activity_license_from_extra(extra: Any) -> str | None:
    number = _normalize_number(_extra_map(extra).get(LICENSE_NUMBER_KEY))
    return number or None


def activity_license_public_payload(number: str | None) -> dict[str, Any]:
    return {"activity_license_number": number or None}


async def get_activity_license_record(db: AsyncSession) -> dict[str, Any]:
    """شماره، منبع و زمان به‌روزرسانی برای پنل ادمین."""
    student = await ensure_institute_operational_student(db)
    extra = _extra_map(student.extra_data)
    number = activity_license_from_extra(extra)
    updated_at = str(extra.get(LICENSE_UPDATED_AT_KEY) or "").strip() or None
    source = str(extra.get(LICENSE_SOURCE_KEY) or "").strip() or None
    return {
        "activity_license_number": number,
        "source": source,
        "updated_at": updated_at,
        "student_code": student.student_code,
    }


async def get_activity_license_number(db: AsyncSession) -> str | None:
    rec = await get_activity_license_record(db)
    return rec.get("activity_license_number")


async def set_activity_license_number(
    db: AsyncSession,
    number: Any,
    *,
    source: str = SOURCE_MANUAL,
) -> dict[str, Any]:
    """ذخیرهٔ شماره پروانه روی INST-OPS. رشتهٔ خالی نادیده گرفته می‌شود."""
    normalized = _normalize_number(number)
    if not normalized:
        return await get_activity_license_record(db)

    student = await ensure_institute_operational_student(db)
    extra = _extra_map(student.extra_data)
    extra["institute_operational_anchor"] = True
    extra[LICENSE_NUMBER_KEY] = normalized
    extra[LICENSE_SOURCE_KEY] = (source or SOURCE_MANUAL).strip() or SOURCE_MANUAL
    extra[LICENSE_UPDATED_AT_KEY] = datetime.now(timezone.utc).isoformat()
    student.extra_data = extra
    flag_modified(student, "extra_data")
    await db.flush()
    return await get_activity_license_record(db)


async def sync_activity_license_from_prep_context(
    db: AsyncSession,
    ctx: dict[str, Any] | None,
) -> dict[str, Any]:
    """اگر معاون «تغییر کرده» را بزند، شماره جدید روی انستیتو ذخیره می‌شود."""
    data = ctx if isinstance(ctx, dict) else {}
    status = str(data.get("license_status") or "").strip()
    if status != LICENSE_STATUS_CHANGED:
        return await get_activity_license_record(db)
    new_number = _normalize_number(data.get("new_license_number"))
    if not new_number:
        return await get_activity_license_record(db)
    return await set_activity_license_number(db, new_number, source=SOURCE_PREP)
