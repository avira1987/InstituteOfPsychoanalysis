"""قفل دسترسی دانشجو هنگام قسط معوق شهریه."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

from fastapi import HTTPException

INSTALLMENT_LOCK_DETAIL = "قسط معوق — فقط از همین سامانه می‌توانید بپردازید."


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def student_installment_lock_active(student: Any) -> bool:
    """آیا پنل دانشجو به‌خاطر قسط معوق قفل است؟"""
    if student is None:
        return False
    extra = _as_mapping(getattr(student, "extra_data", None))
    flag = extra.get("installment_portal_lock")
    if isinstance(flag, dict):
        return bool(flag.get("active"))
    return bool(flag)


def raise_if_student_installment_locked(student: Any) -> None:
    if student_installment_lock_active(student):
        raise HTTPException(status_code=403, detail=INSTALLMENT_LOCK_DETAIL)


def course_join_path(course_code: str) -> str:
    code = quote(str(course_code or "").strip(), safe="")
    return f"/api/panel/courses/{code}/join"


def student_course_join_fields(*, course_code: str, has_external_url: bool) -> dict[str, Any]:
    """لینک خام کلاس به دانشجو برنمی‌گردد؛ فقط مسیر داخلی join."""
    code = str(course_code or "").strip()
    ready = bool(has_external_url and code)
    path = course_join_path(code) if ready else None
    return {
        "meeting_link": None,
        "join_path": path,
        "meeting_link_ready": ready,
        "meeting_link_is_visible": ready,
    }
