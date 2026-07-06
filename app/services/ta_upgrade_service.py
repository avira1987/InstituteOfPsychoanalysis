"""Business logic for process 47 — upgrade_to_ta."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student, User
from app.services.attendance_service import AttendanceService

logger = logging.getLogger(__name__)

TA_THERAPY_HOURS_TARGET = 50.0
GPA_MIN_B = 14.0


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _float_from(extra: dict, lms: dict, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        v = extra.get(k)
        if v is None:
            v = lms.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return default


def _bool_flag(extra: dict, lms: dict, *keys: str) -> bool:
    for k in keys:
        v = extra.get(k)
        if v is None:
            v = lms.get(k)
        if v is True:
            return True
    return False


def _build_conditions_preview(
    term2_met: bool,
    gpa_met: bool,
    therapy_met: bool,
    intern_met: bool,
    *,
    cumulative_gpa: float,
    therapy_hours: float,
) -> list[dict[str, Any]]:
    return [
        {
            "key": "term2_courses",
            "label_fa": "پاس شدن دروس ترم دوم دوره جامع",
            "met": term2_met,
        },
        {
            "key": "gpa_b",
            "label_fa": f"معدل حداقل B (فعلی: {cumulative_gpa:g})",
            "met": gpa_met,
        },
        {
            "key": "therapy_50h",
            "label_fa": f"حداقل ۵۰ ساعت درمان آموزشی (فعلی: {therapy_hours:g})",
            "met": therapy_met,
        },
        {
            "key": "internship_started",
            "label_fa": "شروع دوره انترنی",
            "met": intern_met,
        },
    ]


async def build_ta_upgrade_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Populate instance context fields for rules and UI."""
    stmt = select(Student).where(Student.id == student_id)
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        return {}

    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))

    cumulative_gpa = _float_from(extra, lms, "cumulative_gpa", "cumulativeGPA", "gpa")
    analytic_rank = str(extra.get("analytic_rank") or extra.get("gpa_rank") or "").upper()

    attendance = AttendanceService(db)
    therapy_metrics = await attendance.get_therapy_completion_metrics(student_id)
    therapy_hours = _safe_float(therapy_metrics.get("therapy_hours_2x"))

    term2_met = (
        _bool_flag(
            extra,
            lms,
            "comprehensive_term2_courses_passed",
            "comprehensive_term2_passed",
            "ta_eligibility_term2_ok",
        )
        or extra.get("comprehensive_term2_completed") is True
    )
    gpa_met = (
        cumulative_gpa >= GPA_MIN_B
        or analytic_rank in ("B", "B+", "A", "A+")
        or extra.get("ta_eligibility_gpa_ok") is True
    )
    therapy_met = therapy_hours >= TA_THERAPY_HOURS_TARGET or extra.get("ta_eligibility_therapy_ok") is True
    intern_met = (
        bool(student.is_intern)
        or _bool_flag(extra, lms, "internship_started", "ta_eligibility_intern_ok")
    )

    eligibility_met = term2_met and gpa_met and therapy_met and intern_met
    preview = _build_conditions_preview(
        term2_met,
        gpa_met,
        therapy_met,
        intern_met,
        cumulative_gpa=cumulative_gpa,
        therapy_hours=therapy_hours,
    )
    summary_fa = "؛ ".join(
        f"{row['label_fa'].split('(')[0].strip()}: {'✓' if row['met'] else '✗'}"
        for row in preview
    )

    ctx = {
        "ta_eligibility_met": eligibility_met,
        "ta_eligibility_summary_fa": summary_fa,
        "ta_conditions_preview": preview,
        "ta_cumulative_gpa": cumulative_gpa,
        "ta_therapy_hours_completed": therapy_hours,
        "ta_therapy_hours_target": TA_THERAPY_HOURS_TARGET,
        "ta_term2_courses_met": term2_met,
        "ta_gpa_met": gpa_met,
        "ta_therapy_met": therapy_met,
        "ta_intern_met": intern_met,
    }

    merged = {**_as_mapping(existing), **ctx}
    return merged


def validate_conditions_met_trigger(ctx: dict[str, Any]) -> Optional[str]:
    """Return Persian error if student cannot fire conditions_met."""
    if ctx.get("ta_eligibility_met") is True:
        return None
    return (
        "شرایط ارتقا به کمک‌مدرس احراز نشده است. "
        "چهار شرط (دروس ترم دوم جامع، معدل B، ۵۰ ساعت درمان، شروع انترنی) را در پنل بررسی کنید."
    )


def _normalize_tracks(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if raw is not None and str(raw).strip():
        return [str(raw).strip()]
    return []


def _resolve_member_name(student: Student, user: User | None) -> str:
    if user and (user.full_name_fa or "").strip():
        return str(user.full_name_fa).strip()
    return (student.student_code or "").strip()


def _normalize_courses(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if raw is not None and str(raw).strip():
        return [str(raw).strip()]
    return []


async def apply_ta_registration(
    db: AsyncSession,
    student: Student,
    *,
    tracks: list[str],
    courses: list[str] | None = None,
    user: User | None = None,
) -> None:
    """پس از اتمام موفق فرایند ۴۷ — ثبت کمک‌مدرس در پرونده و چارت کمیته دروس."""
    from app.services.course_committee_roster_service import (
        merge_course_grants,
        register_teaching_assistant_on_roster,
    )

    selected = _normalize_tracks(tracks)
    if not selected:
        logger.warning("apply_ta_registration: no tracks for student=%s", student.id)
        return

    name_fa = _resolve_member_name(student, user)
    if not name_fa:
        logger.warning("apply_ta_registration: no display name for student=%s", student.id)
        return

    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    lms["ta_active_tracks"] = list(dict.fromkeys(_normalize_tracks(lms.get("ta_active_tracks")) + selected))
    extra["lms"] = lms
    extra["ta_active_tracks"] = lms["ta_active_tracks"]
    extra["ta_registered"] = True
    extra["is_teaching_assistant"] = True
    extra["ta_registered_at"] = datetime.now(timezone.utc).isoformat()
    student.extra_data = extra
    flag_modified(student, "extra_data")

    authorized_courses = _normalize_courses(courses)
    if not authorized_courses:
        logger.warning(
            "apply_ta_registration: no authorized courses for student=%s tracks=%s",
            student.id,
            selected,
        )

    if user:
        user.role = "teaching_assistant"
        user.is_active = True
        meta = dict(user.profile_meta or {})
        roster_tracks = list(meta.get("course_committee_tracks") or [])
        for t in selected:
            if t not in roster_tracks:
                roster_tracks.append(t)
        meta["course_committee_tracks"] = roster_tracks
        meta["member_kind"] = "teaching_assistant"
        if authorized_courses:
            merge_course_grants(meta, "teaching_assistant", authorized_courses)
        user.profile_meta = meta
        flag_modified(user, "profile_meta")

    for track_code in selected:
        await register_teaching_assistant_on_roster(
            db,
            track=track_code,
            name_fa=name_fa,
            user=user,
        )
    await db.flush()


async def chain_after_transition(
    db: AsyncSession,
    instance: ProcessInstance,
    to_state: str,
) -> None:
    """پس از رسیدن به ta_registered — اضافه شدن به لیست کمک‌مدرسین."""
    if instance.process_code != "upgrade_to_ta":
        return
    if to_state != "ta_registered":
        return

    stmt = select(Student).where(Student.id == instance.student_id)
    student = (await db.execute(stmt)).scalars().first()
    if not student:
        return

    ctx = _as_mapping(instance.context_data)
    tracks = _normalize_tracks(ctx.get("tracks"))
    courses = _normalize_courses(ctx.get("courses") or ctx.get("ta_authorized_courses"))
    user: User | None = None
    if student.user_id:
        user = (await db.execute(select(User).where(User.id == student.user_id))).scalars().first()

    await apply_ta_registration(db, student, tracks=tracks, courses=courses, user=user)
