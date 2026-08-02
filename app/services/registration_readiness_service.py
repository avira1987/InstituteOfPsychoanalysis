"""Gate for introductory course registration — requires published fall prep + active calendar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.institute_calendar_service import get_active_calendar, resolve_registration_window
from app.services.semester_prep_service import (
    FALL_PREP,
    get_completed_fall_prep_instance,
)
from app.services.term_course_offering_service import (
    NO_OFFERINGS_REASON_FA,
    has_published_offerings,
    merge_offerings_into_instance_context,
)

INTRO_REGISTRATION_PROCESS = "introductory_course_registration"


@dataclass(frozen=True)
class IntroRegistrationGateResult:
    allowed: bool
    reason_fa: str
    prep_published: bool = False
    calendar_active: bool = False
    in_registration_window: bool = False
    offerings_published: bool = False
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
            "offerings_published": self.offerings_published,
            "prep_published_at": self.prep_published_at,
            "registration_open_at": self.registration_open_at,
            "registration_deadline_at": self.registration_deadline_at,
            "term_code": self.term_code,
        }


async def check_intro_registration_gate(db: AsyncSession) -> IntroRegistrationGateResult:
    """
    Introductory registration is allowed only when:
    - fall_semester_preparation completed in state ``published``
    - an active InstituteCalendar exists
    - current time is within registration window (if bounds are set)
    - term course offerings are published for introductory term 1
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

    offerings_ok = await has_published_offerings(
        db, program_kind="introductory", term_number=1, term_code=cal.term_code
    )
    if not offerings_ok:
        return IntroRegistrationGateResult(
            allowed=False,
            reason_fa=NO_OFFERINGS_REASON_FA,
            prep_published=True,
            prep_published_at=prep_at,
            calendar_active=True,
            in_registration_window=False,
            offerings_published=False,
            term_code=cal.term_code,
        )

    reg_open, reg_deadline = resolve_registration_window(cal)
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
            offerings_published=True,
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
        offerings_published=True,
        prep_published_at=prep_at,
        registration_open_at=open_iso,
        registration_deadline_at=deadline_iso,
        term_code=cal.term_code,
    )


async def merge_prep_courses_into_instance_context(
    db: AsyncSession,
    ctx: dict[str, Any],
    *,
    process_code: str = INTRO_REGISTRATION_PROCESS,
    student: Any = None,
) -> dict[str, Any]:
    """Attach available courses from published term offerings."""
    return await merge_offerings_into_instance_context(
        db,
        process_code,
        ctx,
        student=student,
    )


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
