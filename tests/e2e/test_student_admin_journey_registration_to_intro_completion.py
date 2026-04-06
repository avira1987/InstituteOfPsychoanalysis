"""
تست یکپارچه: ثبت‌نام دوره آشنایی (نوبت‌دهی تا ثبت‌نام نهایی) با نقش‌های متناوب
مدیر (مصاحبه‌گر، پذیرش، سیستم) و دانشجو؛ سپس دست‌یابی به فرایند «آغاز درمان»
و در پایان خاتمهٔ دوره آشنایی تا state پایانی.

یادداشت: «فارغ‌التحصیلی» کامل در متادیتا به چند فرایند ترم/جامع تقسیم شده است؛
این تست زنجیرهٔ واقع‌بینانه تا گواهی پایان دوره آشنایی را پوشش می‌دهد.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance, Student, User


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


@pytest_asyncio.fixture
async def journey_admin(db_session: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        username=f"journey_admin_{uuid.uuid4().hex[:8]}",
        email=f"journey_admin_{uuid.uuid4().hex[:8]}@test.local",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="مدیر سفر تست",
        role="admin",
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def journey_student_user(db_session: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        username=f"journey_student_{uuid.uuid4().hex[:8]}",
        email=f"journey_student_{uuid.uuid4().hex[:8]}@test.local",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="دانشجوی سفر تست",
        role="student",
    )
    db_session.add(u)
    await db_session.commit()
    return u


@pytest_asyncio.fixture
async def journey_intro_student(db_session: AsyncSession, journey_student_user: User) -> Student:
    s = Student(
        id=uuid.uuid4(),
        user_id=journey_student_user.id,
        student_code=f"STU-J-{uuid.uuid4().hex[:8].upper()}",
        course_type="introductory",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=1,
        therapy_started=False,
    )
    db_session.add(s)
    await db_session.commit()
    return s


async def _load_journey_metadata(db_session: AsyncSession) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await load_process(db_session, PROCESSES_DIR / "start_therapy.json")
    await load_process(db_session, PROCESSES_DIR / "introductory_course_completion.json")
    await db_session.commit()


@pytest.mark.asyncio
async def test_student_admin_roundtrip_registration_therapy_and_intro_course_completion(
    db_session: AsyncSession,
    journey_admin: User,
    journey_student_user: User,
    journey_intro_student: Student,
) -> None:
    await _load_journey_metadata(db_session)
    engine = StateMachineEngine(db_session)
    admin_id = journey_admin.id
    student_id = journey_intro_student.id
    stu_uid = journey_student_user.id

    # --- متقاضی / مدیر: شروع ثبت‌نام تا مصاحبه ---
    reg = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=student_id,
        actor_id=admin_id,
        actor_role="applicant",
    )
    await db_session.commit()

    for trigger, role, uid, payload in [
        ("timeslot_selected", "applicant", admin_id, {"selected_timeslot": "2026-04-10T10:00:00"}),
        ("proceed_to_payment", "applicant", admin_id, None),
        ("payment_success", "applicant", admin_id, None),
        ("interview_time_reached", "admin", admin_id, None),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=uid,
            actor_role=role,
            payload=payload,
        )
        await db_session.commit()
        assert r.success, f"{trigger}: {getattr(r, 'error', None)}"

    # مصاحبه‌گر: پذیرش کامل
    r = await engine.execute_transition(
        instance_id=reg.id,
        trigger_event="interview_result_submitted",
        actor_id=admin_id,
        actor_role="interviewer",
        payload={
            "interview_result": "full_admission",
            "to_state": "result_full_admission",
            "allowed_course_count": 5,
        },
    )
    await db_session.commit()
    assert r.success, r.error

    r = await engine.execute_transition(
        instance_id=reg.id,
        trigger_event="proceed_to_documents",
        actor_id=admin_id,
        actor_role="admin",
        payload=None,
    )
    await db_session.commit()
    assert r.success, r.error

    r = await engine.execute_transition(
        instance_id=reg.id,
        trigger_event="documents_submitted",
        actor_id=admin_id,
        actor_role="applicant",
        payload={"documents_complete": True},
    )
    await db_session.commit()
    assert r.success, r.error

    # مسئول پذیرش (ادمین)
    r = await engine.execute_transition(
        instance_id=reg.id,
        trigger_event="documents_approved",
        actor_id=admin_id,
        actor_role="admissions_officer",
        payload=None,
    )
    await db_session.commit()
    assert r.success, r.error

    # دانشجو: ورود، انتخاب دروس، پرداخت نهایی
    for trigger, payload in [
        ("student_logged_in", {"lms_login": True}),
        ("courses_selected", {"selected_courses": ["theory_1", "theory_2"], "admission_type": "full"}),
        ("payment_completed", {"payment_method": "cash"}),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=stu_uid,
            actor_role="student",
            payload=payload,
        )
        await db_session.commit()
        assert r.success, f"{trigger}: {r.error}"

    reg = await engine.get_process_instance(reg.id)
    assert reg.current_state_code == "registration_complete"
    assert reg.is_completed is True

    # --- پیگیری خودکار: آغاز درمان + primary_instance ---
    await db_session.refresh(journey_intro_student)
    extra = journey_intro_student.extra_data or {}
    primary_raw = extra.get("primary_instance_id")
    assert primary_raw, "پس از ثبت‌نام، primary_instance_id باید روی start_therapy تنظیم شود"
    therapy_iid = uuid.UUID(str(primary_raw))

    therapy = await engine.get_process_instance(therapy_iid)
    assert therapy.process_code == "start_therapy"
    assert therapy.current_state_code != "eligibility_check"

    # --- خاتمه دوره آشنایی (سیستم + کمیته از طریق ادمین) ---
    completion = await engine.start_process(
        process_code="introductory_course_completion",
        student_id=student_id,
        actor_id=admin_id,
        actor_role="system",
    )
    await db_session.commit()

    for trigger, role in [
        ("all_10_courses_passed", "system"),
        ("generate_certificate_draft", "system"),
        ("draft_ready_for_review", "system"),
        ("committee_approved_certificate", "admin"),
        ("student_notified", "system"),
    ]:
        r = await engine.execute_transition(
            instance_id=completion.id,
            trigger_event=trigger,
            actor_id=admin_id,
            actor_role=role,
            payload=None,
        )
        await db_session.commit()
        assert r.success, f"{trigger}: {r.error}"

    completion = await engine.get_process_instance(completion.id)
    assert completion.current_state_code == "process_complete"
    assert completion.is_completed is True

    # نمونهٔ ثبت‌نام اولیه هنوز در دیتابیس قابل مشاهده است
    row = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == reg.id))).scalars().first()
    assert row is not None
