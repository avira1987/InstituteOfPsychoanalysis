"""Gate for introductory course registration — requires published fall prep + active calendar."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.meta.course_selection_validation import INTRO_TERM1_COURSE_LABELS_FA
from app.services.institute_calendar_service import get_active_calendar
from app.services.semester_prep_service import (
    FALL_PREP,
    get_completed_fall_prep_instance,
    load_fall_prep_context_field,
)

INTRO_REGISTRATION_PROCESS = "introductory_course_registration"

# Persian course names in fall prep → intro term1 codes
_COURSE_NAME_TO_CODE: dict[str, str] = {
    v.lower(): k for k, v in INTRO_TERM1_COURSE_LABELS_FA.items()
}
# Aliases without «ی»/spacing variants
for code, label in INTRO_TERM1_COURSE_LABELS_FA.items():
    _COURSE_NAME_TO_CODE[label.replace("ی", "ي").lower()] = code
    m = re.match(r"تئوری روانکاوی\s*(\d+)", label)
    if m:
        _COURSE_NAME_TO_CODE[f"theory {m.group(1)}"] = code
        _COURSE_NAME_TO_CODE[f"theory_{m.group(1)}"] = code


@dataclass(frozen=True)
class IntroRegistrationGateResult:
    allowed: bool
    reason_fa: str
    prep_published: bool = False
    calendar_active: bool = False
    in_registration_window: bool = False
    prep_published_at: Optional[str] = None
    registration_open_at: Optional[str] = None
    registration_deadline_at: Optional[str] = None
    term_code: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason_fa": self.reason_fa,
            "prep_published": self.prep_published,
            "calendar_active": self.calendar_active,
            "in_registration_window": self.in_registration_window,
            "prep_published_at": self.prep_published_at,
            "registration_open_at": self.registration_open_at,
            "registration_deadline_at": self.registration_deadline_at,
            "term_code": self.term_code,
        }


def _normalize_course_name(name: str) -> str:
    return (name or "").strip().lower().replace("ي", "ی")


def map_prep_course_name_to_code(course_name: str) -> Optional[str]:
    """Map a fall-prep course_name row to theory_1..theory_5 if possible."""
    raw = (course_name or "").strip()
    if not raw:
        return None
    if raw in INTRO_TERM1_COURSE_LABELS_FA:
        return raw
    norm = _normalize_course_name(raw)
    if norm in _COURSE_NAME_TO_CODE:
        return _COURSE_NAME_TO_CODE[norm]
    for label, code in INTRO_TERM1_COURSE_LABELS_FA.items():
        if _normalize_course_name(label) == norm:
            return code
    return None


def prep_courses_rows_to_codes(rows: Any) -> list[str]:
    """Extract theory_* codes from fall prep ``courses`` table rows."""
    if not isinstance(rows, list):
        return []
    codes: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("course_name") or row.get("name") or row.get("label_fa") or ""
        code = map_prep_course_name_to_code(str(name))
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


async def load_intro_term1_offered_course_codes(db: AsyncSession) -> list[str]:
    """Published fall prep course list mapped to intro term1 codes."""
    raw = await load_fall_prep_context_field(db, "courses_fall")
    if raw in (None, "", []):
        raw = await load_fall_prep_context_field(db, "courses")
    mapped = prep_courses_rows_to_codes(raw)
    if mapped:
        return mapped
    # Fallback to full catalog only when prep published but table empty
    gate = await check_intro_registration_gate(db)
    if gate.allowed:
        return list(INTRO_TERM1_COURSE_LABELS_FA.keys())
    return []


async def check_intro_registration_gate(db: AsyncSession) -> IntroRegistrationGateResult:
    """
    Introductory registration is allowed only when:
    - fall_semester_preparation completed in state ``published``
    - an active InstituteCalendar exists
    - current time is within registration window (if bounds are set)
    """
    now = datetime.now(timezone.utc)
    fall = await get_completed_fall_prep_instance(db)
    prep_published = fall is not None
    prep_at = (
        fall.completed_at.isoformat()
        if fall and fall.completed_at
        else None
    )

    if not prep_published:
        return IntroRegistrationGateResult(
            allowed=False,
            reason_fa=(
                "ثبت‌نام دورهٔ آشنایی پس از اتمام «آماده‌سازی ترم پاییز» و انتشار تقویم آموزشی "
                "در دسترس خواهد بود. لطفاً بعداً مراجعه کنید."
            ),
            prep_published=False,
        )

    cal = await get_active_calendar(db)
    if cal is None or not cal.is_active:
        return IntroRegistrationGateResult(
            allowed=False,
            reason_fa=(
                "تقویم آموزشی هنوز در سامانه فعال نشده است. پس از انتشار رسمی تقویم، "
                "ثبت‌نام دورهٔ آشنایی باز می‌شود."
            ),
            prep_published=True,
            prep_published_at=prep_at,
            calendar_active=False,
        )

    reg_open = cal.registration_open_at
    reg_deadline = cal.registration_deadline_at
    in_window = True
    if reg_open is not None and now < reg_open:
        in_window = False
    if reg_deadline is not None and now > reg_deadline:
        in_window = False

    open_iso = reg_open.isoformat() if reg_open else None
    deadline_iso = reg_deadline.isoformat() if reg_deadline else None

    if not in_window:
        if reg_open is not None and now < reg_open:
            reason = (
                "پنجرهٔ ثبت‌نام هنوز باز نشده است. پس از شروع مهلت ثبت‌نام طبق تقویم "
                "آموزشی می‌توانید ادامه دهید."
            )
        else:
            reason = (
                "مهلت ثبت‌نام این ترم به پایان رسیده است. برای ادامه با واحد پذیرش "
                "هماهنگ کنید."
            )
        return IntroRegistrationGateResult(
            allowed=False,
            reason_fa=reason,
            prep_published=True,
            calendar_active=True,
            in_registration_window=False,
            prep_published_at=prep_at,
            registration_open_at=open_iso,
            registration_deadline_at=deadline_iso,
            term_code=cal.term_code,
        )

    return IntroRegistrationGateResult(
        allowed=True,
        reason_fa="",
        prep_published=True,
        calendar_active=True,
        in_registration_window=True,
        prep_published_at=prep_at,
        registration_open_at=open_iso,
        registration_deadline_at=deadline_iso,
        term_code=cal.term_code,
    )


async def merge_prep_courses_into_instance_context(
    db: AsyncSession,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Attach ``available_courses`` and lms snapshot from published fall prep."""
    codes = await load_intro_term1_offered_course_codes(db)
    out = dict(ctx or {})
    if codes:
        out["available_courses"] = codes
        lms = dict(out.get("lms") or {})
        lms["available_courses"] = codes
        lms["available_loaded_at"] = datetime.now(timezone.utc).isoformat()
        out["lms"] = lms
    out["prep_source_process"] = FALL_PREP
    return out


async def unlock_intro_students_after_calendar_publish(db: AsyncSession) -> int:
    """Start deferred intro registration processes for students without an active instance."""
    from sqlalchemy import select

    from app.models.operational_models import ProcessInstance, Student, User
    from app.services.student_service import StudentService

    gate = await check_intro_registration_gate(db)
    if not gate.allowed:
        return 0

    stmt = select(Student).where(
        Student.course_type == "introductory",
        Student.is_sample_data.is_(False),
    )
    students = list((await db.execute(stmt)).scalars().all())
    service = StudentService(db)
    n = 0
    for st in students:
        active_stmt = (
            select(ProcessInstance.id)
            .where(
                ProcessInstance.student_id == st.id,
                ProcessInstance.process_code == INTRO_REGISTRATION_PROCESS,
                ProcessInstance.is_completed.is_(False),
                ProcessInstance.is_cancelled.is_(False),
            )
            .limit(1)
        )
        if (await db.execute(active_stmt)).scalar_one_or_none():
            continue
        user = await db.get(User, st.user_id) if st.user_id else None
        if not user:
            continue
        if await service.ensure_primary_registration_path(st, user):
            n += 1
    return n
