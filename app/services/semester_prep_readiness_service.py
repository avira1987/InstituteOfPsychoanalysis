"""سنجش آمادگی پیش‌نیازهای نرم برای فرایندهای آماده‌سازی ترم (۲۹/۳۰)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_roles import user_matches_role_sql
from app.models.operational_models import ProcessInstance, User
from app.services.course_committee_roster_service import (
    list_course_catalog_options,
    list_track_options,
    list_track_roster_detail,
)
from app.services.institute_activity_license_service import get_activity_license_number
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_service import (
    FALL_PREP,
    WINTER_PREP,
    _ctx,
    get_active_prep_instance,
    get_completed_fall_prep_instance,
)


def _readiness_item(
    *,
    key: str,
    title_fa: str,
    complete: bool,
    count: int,
    message_fa: str,
    action_route: str,
    action_anchor: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "title_fa": title_fa,
        "complete": complete,
        "count": count,
        "message_fa": message_fa,
        "action_route": action_route,
        "action_anchor": action_anchor,
    }


async def _license_reviewed_in_context(db: AsyncSession) -> tuple[bool, str | None]:
    """آیا وضعیت پروانه حداقل یک‌بار در نمونهٔ آماده‌سازی ثبت شده است."""
    anchor = await ensure_institute_operational_student(db)
    instances: list[ProcessInstance | None] = [
        await get_active_prep_instance(db, FALL_PREP, student_id=anchor.id),
        await get_active_prep_instance(db, WINTER_PREP, student_id=anchor.id),
        await get_completed_fall_prep_instance(db, student_id=anchor.id),
    ]
    for inst in instances:
        if inst is None:
            continue
        ctx = _ctx(inst)
        status = str(ctx.get("license_status") or "").strip()
        if status:
            return True, status
        if str(ctx.get("new_license_number") or "").strip():
            return True, "تغییر کرده"
    return False, None


async def compute_semester_prep_readiness(db: AsyncSession) -> dict[str, Any]:
    """چک‌لیست آمادگی پیش‌نیازها — هشدار نرم؛ مسدودکننده نیست."""
    courses = list_course_catalog_options()
    tracks = list_track_options()
    course_count = len(courses)
    track_count = len(tracks)

    instructor_count = 0
    ta_count = 0
    tracks_with_instructor = 0
    for track_opt in tracks:
        code = str(track_opt.get("value") or "").strip()
        if not code:
            continue
        detail = await list_track_roster_detail(db, track=code)
        inst_n = len(detail.get("instructors") or [])
        ta_n = len(detail.get("teaching_assistants") or [])
        instructor_count += inst_n
        ta_count += ta_n
        if inst_n > 0:
            tracks_with_instructor += 1

    interviewer_stmt = select(func.count()).select_from(User).where(
        User.is_active.is_(True),
        user_matches_role_sql("interviewer"),
    )
    interviewer_count = int((await db.execute(interviewer_stmt)).scalar() or 0)

    license_ok, license_status = await _license_reviewed_in_context(db)
    stored_license = await get_activity_license_number(db)

    catalog_complete = course_count > 0
    roster_complete = track_count > 0 and tracks_with_instructor > 0
    interviewers_complete = interviewer_count > 0

    items: list[dict[str, Any]] = [
        _readiness_item(
            key="course_catalog",
            title_fa="کاتالوگ دروس",
            complete=catalog_complete,
            count=course_count,
            message_fa=(
                f"{course_count} درس در کاتالوگ ثبت شده است."
                if catalog_complete
                else "هنوز درسی در کاتالوگ ثبت نشده — برای انتخاب در فرم لیست دروس، حداقل چند درس اضافه کنید."
            ),
            action_route="/panel/semester-prep/readiness",
            action_anchor="courses",
        ),
        _readiness_item(
            key="course_roster",
            title_fa="رسته‌ها و روستر مدرسین",
            complete=roster_complete,
            count=instructor_count + ta_count,
            message_fa=(
                f"{track_count} رسته؛ {instructor_count} مدرس و {ta_count} کمک‌مدرس."
                if roster_complete
                else (
                    "رسته یا مدرس ثبت نشده — برای تکمیل لیست دروس، رسته‌ها و حداقل یک مدرس تعریف کنید."
                    if track_count == 0
                    else "رسته‌ها تعریف شده‌اند اما هنوز مدرسی ثبت نشده است."
                )
            ),
            action_route="/panel/semester-prep/readiness",
            action_anchor="roster",
        ),
        _readiness_item(
            key="interviewers",
            title_fa="مصاحبه‌کنندگان فعال",
            complete=interviewers_complete,
            count=interviewer_count,
            message_fa=(
                f"{interviewer_count} مصاحبه‌کنندهٔ فعال."
                if interviewers_complete
                else "هنوز مصاحبه‌کنندهٔ فعالی ثبت نشده — در مرحلهٔ تعیین مصاحبه‌گران به فهرست نیاز دارید."
            ),
            action_route="/panel/semester-prep/readiness",
            action_anchor="interviewers",
        ),
        _readiness_item(
            key="license",
            title_fa="بررسی پروانه فعالیت",
            complete=license_ok,
            count=1 if license_ok else 0,
            message_fa=(
                (
                    f"وضعیت پروانه ثبت شده: {license_status}"
                    + (f" — شماره: {stored_license}" if stored_license else "")
                )
                if license_ok
                else "هنوز وضعیت پروانه در فرایند آماده‌سازی ثبت نشده — در مرحلهٔ «بررسی پروانه» ثبت کنید."
            ),
            action_route="/panel/semester-prep/readiness",
            action_anchor="license",
        ),
    ]

    incomplete = [i for i in items if not i["complete"]]
    return {
        "ready": len(incomplete) == 0,
        "incomplete_count": len(incomplete),
        "items": items,
    }
