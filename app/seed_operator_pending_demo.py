"""
دادهٔ دمو: چند دانشجو در وضعیت‌های آموزشی مختلف که منتظر اقدام اپراتورها هستند.

پیشوند کد دانشجویی: DEMO-OP-*

سناریوها:
  - DEMO-OP-INTV: ثبت‌نام آشنایی — مصاحبه انجام شده، منتظر ثبت نتیجه (مصاحبه‌گر)
  - DEMO-OP-ADM: ثبت‌نام آشنایی — مدارک ارسال شده، منتظر بررسی پذیرش
  - DEMO-OP-SITE: آماده‌سازی ترم پاییز — زمان‌بندی دقیق مصاحبه‌ها (مسئول سایت)
  - DEMO-OP-ASGN: تکلیف ارسال شده بدون نمره (کارمند/تصحیح)
  - DEMO-OP-EXTRA: جلسه اضافی — منتظر تصمیم درمانگر

از app.demo_process_walker برای ایجاد دانشجو و ترنزیشن‌ها استفاده می‌شود.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.demo_process_walker import (
    apply_demo_attendance_patches,
    create_demo_student,
    ensure_admin_for_matrix_seed,
    list_process_json_files,
    restore_demo_attendance_patches,
)
from app.demo_role_users import build_demo_actors, ensure_demo_role_users
from app.models.operational_models import (
    Assignment,
    AssignmentSubmission,
    FinancialRecord,
    ProcessInstance,
    Student,
    TherapySession,
    User,
)

logger = logging.getLogger(__name__)

DEMO_PREFIX = "DEMO-OP-"

FALL_SEMESTER_TRIGGERS: list[tuple[str, str]] = [
    ("calendar_submitted", "admin"),
    ("tuition_submitted", "admin"),
    ("license_reviewed", "admin"),
    ("course_list_submitted", "admin"),
    ("courses_finalized", "admin"),
    ("marketing_started", "admin"),
    ("interviewers_assigned", "admin"),
]


async def _exec(
    engine: StateMachineEngine,
    db: AsyncSession,
    instance_id: uuid.UUID,
    trigger: str,
    actor_id: uuid.UUID,
    actor_role: str,
    payload: dict[str, Any] | None = None,
) -> None:
    r = await engine.execute_transition(
        instance_id=instance_id,
        trigger_event=trigger,
        actor_id=actor_id,
        actor_role=actor_role,
        payload=payload,
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"transition {trigger} failed: {r.error}")


async def delete_operator_pending_demo_seed(
    db: AsyncSession,
    prefix: str = DEMO_PREFIX,
) -> int:
    """حذف دانشجوهای دمو DEMO-OP-* و وابستگی‌ها."""
    stmt = select(Student).where(Student.student_code.startswith(prefix))
    r = await db.execute(stmt)
    rows = list(r.scalars().all())
    n = 0
    for st in rows:
        await db.execute(delete(AssignmentSubmission).where(AssignmentSubmission.student_id == st.id))
        await db.execute(delete(Assignment).where(Assignment.student_id == st.id))
        await db.execute(delete(TherapySession).where(TherapySession.student_id == st.id))
        await db.execute(delete(ProcessInstance).where(ProcessInstance.student_id == st.id))
        await db.execute(delete(FinancialRecord).where(FinancialRecord.student_id == st.id))
        uid = st.user_id
        await db.delete(st)
        ur = await db.execute(select(User).where(User.id == uid))
        u = ur.scalars().first()
        if u:
            await db.delete(u)
        n += 1
    await db.commit()
    return n


async def _seed_interviewer_pending(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: Any,
    student_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> str:
    reg = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=student_id,
        actor_id=actors.applicant_id,
        actor_role="applicant",
    )
    await db.commit()
    for trigger, role, uid, payload in [
        ("timeslot_selected", "applicant", actors.applicant_id, {"selected_timeslot": "2026-05-15T10:00:00"}),
        ("proceed_to_payment", "applicant", actors.applicant_id, None),
        ("payment_success", "admin", actors.admin_id, None),
        ("interview_time_reached", "admin", actors.admin_id, None),
    ]:
        await _exec(engine, db, reg.id, trigger, uid, role, payload)
    inst = await engine.get_process_instance(reg.id)
    assert inst.current_state_code == "interview_completed"
    return "introductory_course_registration @ interview_completed (مصاحبه‌گر)"


async def _seed_admissions_pending(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: Any,
    student_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> str:
    reg = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=student_id,
        actor_id=actors.applicant_id,
        actor_role="applicant",
    )
    await db.commit()
    for trigger, role, uid, payload in [
        ("timeslot_selected", "applicant", actors.applicant_id, {"selected_timeslot": "2026-05-16T14:00:00"}),
        ("proceed_to_payment", "applicant", actors.applicant_id, None),
        ("payment_success", "admin", actors.admin_id, None),
        ("interview_time_reached", "admin", actors.admin_id, None),
    ]:
        await _exec(engine, db, reg.id, trigger, uid, role, payload)

    await _exec(
        engine,
        db,
        reg.id,
        "interview_result_submitted",
        actors.interviewer_id,
        "interviewer",
        {
            "interview_result": "full_admission",
            "to_state": "result_full_admission",
            "allowed_course_count": 5,
        },
    )
    await _exec(engine, db, reg.id, "proceed_to_documents", actors.admin_id, "admin", None)
    await _exec(
        engine,
        db,
        reg.id,
        "documents_submitted",
        actors.applicant_id,
        "applicant",
        {"documents_complete": True},
    )
    inst = await engine.get_process_instance(reg.id)
    assert inst.current_state_code == "documents_review"
    return "introductory_course_registration @ documents_review (مسئول پذیرش)"


async def _seed_site_manager_pending(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: Any,
    student_id: uuid.UUID,
) -> str:
    inst = await engine.start_process(
        process_code="fall_semester_preparation",
        student_id=student_id,
        actor_id=actors.admin_id,
        actor_role="admin",
    )
    await db.commit()
    for trigger, role in FALL_SEMESTER_TRIGGERS:
        await _exec(engine, db, inst.id, trigger, actors.admin_id, role, None)
    cur = await engine.get_process_instance(inst.id)
    assert cur.current_state_code == "interview_scheduling"
    return "fall_semester_preparation @ interview_scheduling (مدیر داخلی — زمان‌بندی مصاحبه‌ها)"


async def _seed_assignment_grading_pending(
    db: AsyncSession,
    admin_id: uuid.UUID,
    student_id: uuid.UUID,
) -> str:
    aid = uuid.uuid4()
    sid = uuid.uuid4()
    db.add(
        Assignment(
            id=aid,
            student_id=student_id,
            title_fa="تکلیف دمو: گزارش مطالعه موردی",
            description="دادهٔ نمونه برای صف تصحیح اپراتور",
            created_by=admin_id,
        )
    )
    db.add(
        AssignmentSubmission(
            id=sid,
            assignment_id=aid,
            student_id=student_id,
            body_text="متن ارسال‌شدهٔ دانشجو برای تصحیح (دمو).",
            score=None,
        )
    )
    await db.commit()
    return "assignment_submission بدون نمره (کارمند / تصحیح)"


async def _seed_therapist_pending(
    engine: StateMachineEngine,
    db: AsyncSession,
    student_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> str:
    inst = await engine.start_process(
        process_code="extra_session",
        student_id=student_id,
        actor_id=student_user_id,
        actor_role="student",
    )
    await db.commit()
    await _exec(engine, db, inst.id, "extra_requested", student_user_id, "student", None)
    cur = await engine.get_process_instance(inst.id)
    assert cur.current_state_code == "therapist_review"
    return "extra_session @ therapist_review (درمانگر)"


async def seed_operator_pending_demo(
    db: AsyncSession,
    demo_password: str,
    *,
    replace: bool = False,
) -> dict[str, Any]:
    """
    ایجاد پنج دانشجوی دمو با وضعیت‌های منتظر اپراتور.

    replace=True: ابتدا DEMO-OP-* قبلی حذف می‌شود.
    """
    from app.meta.seed import load_process, load_rules

    apply_demo_attendance_patches()
    try:
        await load_rules(db)
        for pf in list_process_json_files():
            await load_process(db, pf)
        await db.commit()

        await ensure_demo_role_users(db)
        actors = await build_demo_actors(db)
        await ensure_admin_for_matrix_seed(db)
        engine = StateMachineEngine(db)

        if replace:
            n = await delete_operator_pending_demo_seed(db)
            if n:
                logger.info("Removed %s prior DEMO-OP-* seed rows", n)

        report: dict[str, Any] = {}

        u1, s1 = await create_demo_student(
            db,
            student_code=f"{DEMO_PREFIX}INTV",
            username="demo_op_intv",
            full_name_fa="دمو: منتظر ثبت نتیجه مصاحبه",
            password=demo_password,
            course_type="introductory",
        )
        report["DEMO-OP-INTV"] = await _seed_interviewer_pending(engine, db, actors, u1.id, s1.id)

        u2, s2 = await create_demo_student(
            db,
            student_code=f"{DEMO_PREFIX}ADM",
            username="demo_op_adm",
            full_name_fa="دمو: مدارک در بررسی پذیرش",
            password=demo_password,
            course_type="introductory",
        )
        report["DEMO-OP-ADM"] = await _seed_admissions_pending(engine, db, actors, u2.id, s2.id)

        u3, s3 = await create_demo_student(
            db,
            student_code=f"{DEMO_PREFIX}SITE",
            username="demo_op_site",
            full_name_fa="دمو: زمان‌بندی مصاحبه‌ها (ترم پاییز)",
            password=demo_password,
            course_type="comprehensive",
            term_count=8,
            current_term=2,
        )
        report["DEMO-OP-SITE"] = await _seed_site_manager_pending(engine, db, actors, s3.id)

        u4, s4 = await create_demo_student(
            db,
            student_code=f"{DEMO_PREFIX}ASGN",
            username="demo_op_asgn",
            full_name_fa="دمو: تکلیف بدون تصحیح",
            password=demo_password,
            course_type="introductory",
        )
        report["DEMO-OP-ASGN"] = await _seed_assignment_grading_pending(db, actors.admin_id, s4.id)

        u5, s5 = await create_demo_student(
            db,
            student_code=f"{DEMO_PREFIX}EXTRA",
            username="demo_op_extra",
            full_name_fa="دمو: جلسه اضافی — منتظر درمانگر",
            password=demo_password,
            course_type="comprehensive",
            therapy_started=True,
            term_count=8,
            current_term=4,
            weekly_sessions=2,
        )
        report["DEMO-OP-EXTRA"] = await _seed_therapist_pending(engine, db, u5.id, s5.id)

        report["_password_hint"] = demo_password
        report["_note"] = (
            "ورود ادمین: admin / admin123 — دانشجویان دمو با همین رمز demo_password "
            "(مگر در env دیگر تعیین شده باشد)"
        )
        return report
    finally:
        restore_demo_attendance_patches()
