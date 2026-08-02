"""
دادهٔ دمو: آماده‌سازی ترم پاییز (منتشرشده) + زمستان (مرحلهٔ زمان‌بندی اسلات) روی anchor انستیتو INST-OPS.

پس از seed:
  - /panel/semester-prep — وضعیت فرایندها
  - deputy_education / staff / site_manager — inbox پورتال برای تکمیل مراحل باقی‌مانده
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.demo_process_walker import ensure_admin_for_matrix_seed, list_process_json_files
from app.demo_role_users import build_demo_actors, ensure_demo_role_users
from app.models.operational_models import ProcessInstance, User
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_service import (
    FALL_PREP,
    PREP_PROCESS_CODES,
    WINTER_PREP,
    ensure_winter_prep_started,
    get_or_start_prep_instance,
)

logger = logging.getLogger(__name__)

DEMO_PREP_TAG = "semester_prep_demo_seed"

# تاریخ ثابت برای دمو — با هر اجرای seed یا دیپلوی جابه‌جا نمی‌شود.
_DEMO_CALENDAR_REF = date(2026, 4, 1)

FALL_TRIGGERS: list[tuple[str, str]] = [
    ("calendar_submitted", "course_committee"),
    ("tuition_submitted", "deputy_education"),
    ("license_reviewed", "deputy_education"),
    ("course_list_submitted", "course_committee"),
    ("courses_finalized", "course_committee"),
    ("marketing_started", "staff"),
    ("interviewers_assigned", "deputy_education"),
    ("interview_times_set", "staff"),
]

WINTER_TRIGGERS_TO_SCHEDULING: list[tuple[str, str]] = [
    ("license_reviewed", "deputy_education"),
    ("course_list_reviewed", "course_committee"),
    ("courses_finalized", "course_committee"),
    ("marketing_started", "staff"),
    ("interviewers_assigned", "deputy_education"),
]

_PREP_STAFF_PHONES: dict[str, str] = {
    "deputy_education1": "09121000001",
    "staff1": "09121000002",
    "site_manager1": "09121000003",
    "demo_admissions": "09121000004",
}


def _demo_calendar_context(*, ref: date | None = None) -> dict[str, Any]:
    """تاریخ‌های ثابت/نسبی برای تقویم دو ترم (قابل نمایش در فرم‌ها)."""
    base = ref or _DEMO_CALENDAR_REF
    fall_start = base + timedelta(days=75)
    fall_end = fall_start + timedelta(days=120)
    winter_start = fall_end + timedelta(days=14)
    winter_end = winter_start + timedelta(days=130)
    reg_start = fall_start - timedelta(days=30)
    reg_end = fall_start - timedelta(days=7)
    intern_dl_start = fall_start - timedelta(days=28)
    intern_dl_end = fall_start - timedelta(days=21)
    ta_dl_start = fall_start - timedelta(days=21)
    ta_dl_end = fall_start - timedelta(days=14)
    nowruz_start = winter_end - timedelta(days=45)
    nowruz_end = nowruz_start + timedelta(days=18)

    def iso(d: date) -> str:
        return d.isoformat()

    return {
        "fall_start_date": iso(fall_start),
        "fall_end_date": iso(fall_end),
        "winter_start_date": iso(winter_start),
        "winter_end_date": iso(winter_end),
        "registration_payment_window_start": iso(reg_start),
        "registration_payment_window_end": iso(reg_end),
        "intern_interview_deadline_start": iso(intern_dl_start),
        "intern_interview_deadline_end": iso(intern_dl_end),
        "teaching_assistant_interview_deadline_start": iso(ta_dl_start),
        "teaching_assistant_interview_deadline_end": iso(ta_dl_end),
        "nowruz_holiday_start": iso(nowruz_start),
        "nowruz_holiday_end": iso(nowruz_end),
        "fall_break_periods": [{"start": iso(fall_start + timedelta(days=40)), "end": iso(fall_start + timedelta(days=47))}],
        "winter_break_periods": [],
    }


def _demo_tuition_context() -> dict[str, Any]:
    return {
        "per_unit_cost_introductory": 18_500_000,
        "per_unit_cost_comprehensive": 22_000_000,
        "interview_fee_introductory": 3_500_000,
        "interview_fee_comprehensive": 4_500_000,
        "registration_interview_fee_rial": 3_500_000,
        "registration_tuition_invoice_toman": 120_000_000,
        "start_therapy_first_session_fee_rial": 10_000_000,
        "extra_session_fee_rial": 7_500_000,
        "default_therapy_session_fee_toman": 500_000,
        "class_session_fee_toman": 0,
        "course_session_fee_toman": 0,
    }


def _demo_license_context() -> dict[str, Any]:
    return {
        "license_status": "بدون تغییر",
        "license_notes": "پروانه فعال — دادهٔ دمو",
    }


def _demo_courses() -> list[dict[str, Any]]:
    return [
        {
            "course_name": "تئوری روانکاوی ۱",
            "track": "analytic_psychotherapy",
            "proposed_day": "شنبه",
            "proposed_time": "18:00",
            "instructor": "ادريس صالحي",
            "teaching_assistant": "سارا طراوتي",
        },
        {
            "course_name": "سوپرویژن گروهی",
            "track": "analytic_psychotherapy",
            "proposed_day": "دوشنبه",
            "proposed_time": "17:00",
            "instructor": "اسرا شريفي",
            "teaching_assistant": "زهرا غروي",
        },
    ]


def _demo_courses_winter() -> list[dict[str, Any]]:
    return [
        {
            "course_name": "تئوری روانکاوی ۳",
            "track": "analytic_psychotherapy",
            "proposed_day": "چهارشنبه",
            "proposed_time": "17:30",
            "instructor": "علي علوي",
            "teaching_assistant": "هانيه پور جبار",
        },
    ]


def _demo_marketing_context() -> dict[str, Any]:
    return {
        "marketing_info_sent_to_manager": True,
        "marketing_notes": "کمپین دمو — آماده‌سازی ترم",
    }


def _demo_interviewer_context(interviewer_label: str = "مصاحبه‌گر دمو") -> dict[str, Any]:
    base = _DEMO_CALENDAR_REF + timedelta(days=45)
    end = base + timedelta(days=21)
    return {
        "comprehensive_interviewers": [interviewer_label],
        "comprehensive_date_range_start": base.isoformat(),
        "comprehensive_date_range_end": end.isoformat(),
        "introductory_interviewers": [interviewer_label],
        "introductory_date_range_start": base.isoformat(),
        "introductory_date_range_end": (base + timedelta(days=14)).isoformat(),
    }


def _demo_winter_license_context() -> dict[str, Any]:
    return {
        "license_status": "بدون تغییر",
        "winter_license_notes": "بررسی پروانه زمستان — دمو",
    }


async def _exec(
    engine: StateMachineEngine,
    db: AsyncSession,
    instance_id: uuid.UUID,
    trigger: str,
    actor_id: uuid.UUID,
    actor_role: str,
) -> None:
    r = await engine.execute_transition(
        instance_id=instance_id,
        trigger_event=trigger,
        actor_id=actor_id,
        actor_role=actor_role,
        payload=None,
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"transition {trigger} failed: {r.error}")


async def _merge_context(
    engine: StateMachineEngine,
    db: AsyncSession,
    instance_id: uuid.UUID,
    patch: dict[str, Any],
) -> None:
    inst = await engine.get_process_instance(instance_id)
    ctx = dict(inst.context_data or {})
    ctx.update(patch)
    ctx["_demo_seed"] = DEMO_PREP_TAG
    inst.context_data = ctx
    flag_modified(inst, "context_data")
    await db.commit()


async def clear_institute_prep_instances(db: AsyncSession) -> int:
    """حذف نمونه‌های آماده‌سازی ترم روی anchor انستیتو."""
    anchor = await ensure_institute_operational_student(db)
    r = await db.execute(
        select(ProcessInstance).where(
            ProcessInstance.student_id == anchor.id,
            ProcessInstance.process_code.in_(tuple(PREP_PROCESS_CODES)),
        )
    )
    rows = list(r.scalars().all())
    if not rows:
        return 0
    ids = [row.id for row in rows]
    await db.execute(delete(ProcessInstance).where(ProcessInstance.id.in_(ids)))
    await db.commit()
    return len(rows)


async def _ensure_prep_staff_phones(db: AsyncSession) -> None:
    for username, phone in _PREP_STAFF_PHONES.items():
        r = await db.execute(select(User).where(User.username == username))
        u = r.scalars().first()
        if u:
            u.phone = phone
            u.is_active = True
    await db.commit()


async def seed_semester_prep_demo(
    db: AsyncSession,
    *,
    replace: bool = False,
    winter_stop_state: str = "interview_scheduling",
) -> dict[str, Any]:
    """
    ایجاد دادهٔ دمو آماده‌سازی ترم روی INST-OPS.

    replace=True: نمونه‌های prep قبلی روی anchor حذف می‌شوند.
    winter_stop_state: پیش‌فرض interview_scheduling (یک مرحله قبل از انتشار).
    """
    from app.meta.seed import load_process, load_rules

    await load_rules(db)
    for pf in list_process_json_files():
        await load_process(db, pf)
    await db.commit()

    await ensure_demo_role_users(db)
    await ensure_admin_for_matrix_seed(db)
    await _ensure_prep_staff_phones(db)
    actors = await build_demo_actors(db)
    anchor = await ensure_institute_operational_student(db)
    engine = StateMachineEngine(db)

    removed = 0
    if replace:
        removed = await clear_institute_prep_instances(db)

    cal = _demo_calendar_context()
    courses = _demo_courses()
    courses_winter = _demo_courses_winter()
    interviewer_ctx = _demo_interviewer_context()

    fall_inst, fall_created = await get_or_start_prep_instance(
        db,
        FALL_PREP,
        actor_id=actors.admin_id,
        actor_role="admin",
    )
    await db.commit()

    await _merge_context(
        engine,
        db,
        fall_inst.id,
        {
            **cal,
            **_demo_tuition_context(),
            **_demo_license_context(),
            "courses_fall": courses,
            "courses_winter": courses_winter,
            **_demo_marketing_context(),
            **interviewer_ctx,
            "interview_scheduling_notes": "دمو — منتظر ثبت اسلات توسط مدیر داخلی",
        },
    )

    for trigger, role in FALL_TRIGGERS:
        actor = actors.admin_id
        if role == "staff":
            r = await db.execute(select(User).where(User.username == "staff1"))
            u = r.scalars().first()
            actor = u.id if u else actors.admin_id
        elif role == "site_manager":
            r = await db.execute(select(User).where(User.username == "site_manager1"))
            u = r.scalars().first()
            actor = u.id if u else actors.admin_id
        elif role == "deputy_education":
            r = await db.execute(select(User).where(User.username == "deputy_education1"))
            u = r.scalars().first()
            actor = u.id if u else actors.admin_id
        await _exec(engine, db, fall_inst.id, trigger, actor, role)

    fall_final = await engine.get_process_instance(fall_inst.id)
    assert fall_final.current_state_code == "published"
    assert fall_final.is_completed is True

    from app.services.term_course_offering_service import publish_offerings_from_prep

    await publish_offerings_from_prep(db, fall_final, fall_final.context_data)

    winter_hit = await ensure_winter_prep_started(
        db, actor_id=actors.admin_id, actor_role="admin"
    )
    await db.commit()
    winter_inst = await engine.get_process_instance(uuid.UUID(winter_hit["instance_id"]))

    await _merge_context(
        engine,
        db,
        winter_inst.id,
        {
            **_demo_winter_license_context(),
            "courses": courses_winter,
            **_demo_marketing_context(),
            **interviewer_ctx,
            "interview_scheduling_notes": "دمو زمستان — زمان‌بندی اسلات",
        },
    )

    winter_triggers = list(WINTER_TRIGGERS_TO_SCHEDULING)
    if winter_stop_state == "published":
        winter_triggers.append(("interview_times_set", "staff"))

    for trigger, role in winter_triggers:
        actor = actors.admin_id
        if role == "staff":
            r = await db.execute(select(User).where(User.username == "staff1"))
            u = r.scalars().first()
            actor = u.id if u else actors.admin_id
        elif role == "site_manager":
            r = await db.execute(select(User).where(User.username == "site_manager1"))
            u = r.scalars().first()
            actor = u.id if u else actors.admin_id
        elif role == "deputy_education":
            r = await db.execute(select(User).where(User.username == "deputy_education1"))
            u = r.scalars().first()
            actor = u.id if u else actors.admin_id
        await _exec(engine, db, winter_inst.id, trigger, actor, role)

    winter_final = await engine.get_process_instance(winter_inst.id)
    await publish_offerings_from_prep(db, winter_final, winter_final.context_data)

    return {
        "removed_prior_instances": removed,
        "anchor_student_code": anchor.student_code,
        "anchor_student_id": str(anchor.id),
        "fall": {
            "instance_id": str(fall_final.id),
            "created": fall_created,
            "state": fall_final.current_state_code,
            "completed": fall_final.is_completed,
        },
        "winter": {
            "instance_id": str(winter_final.id),
            "created": winter_hit.get("created"),
            "state": winter_final.current_state_code,
            "completed": winter_final.is_completed,
        },
        "calendar_sample": {
            "fall_start_date": cal["fall_start_date"],
            "winter_start_date": cal["winter_start_date"],
            "registration_payment_window_start": cal["registration_payment_window_start"],
        },
        "login_hints": {
            "admin": "admin / admin123",
            "deputy_education": "deputy_education1 / demo123",
            "staff": "staff1 / demo123",
            "site_manager": "site_manager1 / demo123",
            "semester_prep_page": "/panel/semester-prep",
            "student_tracker": f"/panel/students?student_id={anchor.id}",
        },
        "_note": (
            "پاییز منتشر شده؛ زمستان در مرحلهٔ زمان‌بندی اسلات — "
            "staff1 می‌تواند اسلات بسازد و interview_times_set را بزند."
        ),
    }
