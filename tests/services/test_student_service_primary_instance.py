import uuid
import pytest
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance, Student, User
from app.services.student_service import StudentService


@pytest.mark.asyncio
async def test_set_primary_instance_for_student(db_session: AsyncSession):
    """StudentService.set_primary_instance_for_student should store instance id in extra_data."""
    user = User(
        id=uuid.uuid4(),
        username="student_primary_test",
        hashed_password="x",
        role="student",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code="STU-PRIMARY-1",
        course_type="introductory",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=1,
    )
    db_session.add_all([user, student])
    await db_session.commit()

    service = StudentService(db_session)
    instance_id = uuid.uuid4()

    await service.set_primary_instance_for_student(student, instance_id)
    await db_session.commit()
    await db_session.refresh(student)

    assert isinstance(student.extra_data, dict)
    assert student.extra_data.get("primary_instance_id") == str(instance_id)


@pytest.mark.asyncio
async def test_ensure_primary_links_existing_instance_without_metadata_engine(db_session: AsyncSession):
    """اگر اینستنس ثبت‌نام در DB هست ولی primary خالی است، همان وصل شود (بدون استارت مجدد)."""
    user = User(
        id=uuid.uuid4(),
        username="stu_ensure_1",
        hashed_password="x",
        role="student",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code="STU-ENSURE-1",
        course_type="comprehensive",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=1,
        extra_data={},
    )
    iid = uuid.uuid4()
    instance = ProcessInstance(
        id=iid,
        process_code="comprehensive_course_registration",
        student_id=student.id,
        current_state_code="application_submitted",
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add_all([user, student, instance])
    await db_session.commit()

    service = StudentService(db_session)
    changed = await service.ensure_primary_registration_path(student, user)
    assert changed is True
    await db_session.commit()
    await db_session.refresh(student)
    assert student.extra_data.get("primary_instance_id") == str(iid)


@pytest.mark.asyncio
async def test_ensure_primary_replaces_invalid_uuid(db_session: AsyncSession):
    """primary_instance_id نامعتبر حذف و به اینستنس واقعی وصل می‌شود."""
    user = User(
        id=uuid.uuid4(),
        username="stu_ensure_2",
        hashed_password="x",
        role="student",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code="STU-ENSURE-2",
        course_type="introductory",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=1,
        extra_data={"primary_instance_id": str(uuid.uuid4())},
    )
    iid = uuid.uuid4()
    instance = ProcessInstance(
        id=iid,
        process_code="introductory_course_registration",
        student_id=student.id,
        current_state_code="application_submitted",
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add_all([user, student, instance])
    await db_session.commit()

    service = StudentService(db_session)
    changed = await service.ensure_primary_registration_path(student, user)
    assert changed is True
    await db_session.commit()
    await db_session.refresh(student)
    assert student.extra_data.get("primary_instance_id") == str(iid)


@pytest.mark.asyncio
async def test_maybe_start_session_payment_reuses_active_instance(db_session: AsyncSession):
    """اگر session_payment فعال وجود دارد، نمونهٔ جدید نسازد؛ primary همان است."""
    user = User(
        id=uuid.uuid4(),
        username="stu_pay_reuse",
        hashed_password="x",
        role="admin",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code="STU-PAY-REUSE",
        course_type="comprehensive",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=2,
        extra_data={},
    )
    existing_pay = ProcessInstance(
        id=uuid.uuid4(),
        process_code="session_payment",
        student_id=student.id,
        current_state_code="payment_due",
        is_completed=False,
        is_cancelled=False,
    )
    therapy_done = ProcessInstance(
        id=uuid.uuid4(),
        process_code="start_therapy",
        student_id=student.id,
        current_state_code="therapy_active",
        is_completed=True,
        is_cancelled=False,
    )
    db_session.add_all([user, student, existing_pay, therapy_done])
    await db_session.commit()

    service = StudentService(db_session)
    await service.maybe_start_session_payment_after_start_therapy(therapy_done)
    await db_session.commit()
    await db_session.refresh(student)

    rows = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.student_id == student.id))).scalars().all()
    assert len([r for r in rows if r.process_code == "session_payment"]) == 1
    assert student.extra_data.get("primary_instance_id") == str(existing_pay.id)


@pytest.mark.asyncio
async def test_maybe_start_session_payment_creates_when_none(db_session: AsyncSession):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()
    user = User(
        id=uuid.uuid4(),
        username="stu_pay_create",
        hashed_password="x",
        role="admin",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code="STU-PAY-NEW",
        course_type="comprehensive",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=2,
        extra_data={},
    )
    therapy_done = ProcessInstance(
        id=uuid.uuid4(),
        process_code="start_therapy",
        student_id=student.id,
        current_state_code="therapy_active",
        is_completed=True,
        is_cancelled=False,
        context_data={"therapist_id": str(uuid.uuid4()), "weekly_sessions": 2},
    )
    db_session.add_all([user, student, therapy_done])
    await db_session.commit()

    service = StudentService(db_session)
    await service.maybe_start_session_payment_after_start_therapy(therapy_done)
    await db_session.commit()
    await db_session.refresh(student)

    rows = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.student_id == student.id))).scalars().all()
    pay = [r for r in rows if r.process_code == "session_payment"]
    assert len(pay) == 1
    assert pay[0].context_data.get("source") == "after_start_therapy_complete"
    assert student.extra_data.get("primary_instance_id") == str(pay[0].id)


@pytest.mark.asyncio
async def test_repoint_primary_after_session_payment_prefers_active_process(db_session: AsyncSession):
    """پس از تکمیل session_payment، primary به نمونهٔ فعال دیگر (مثلاً مرخصی) منتقل شود."""
    user = User(
        id=uuid.uuid4(),
        username="stu_repoint",
        hashed_password="x",
        role="student",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code="STU-REPOINT",
        course_type="comprehensive",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=2,
        extra_data={},
    )
    pay_done = ProcessInstance(
        id=uuid.uuid4(),
        process_code="session_payment",
        student_id=student.id,
        current_state_code="payment_confirmed",
        is_completed=True,
        is_cancelled=False,
    )
    leave_active = ProcessInstance(
        id=uuid.uuid4(),
        process_code="educational_leave",
        student_id=student.id,
        current_state_code="on_leave",
        is_completed=False,
        is_cancelled=False,
    )
    student.extra_data = {"primary_instance_id": str(pay_done.id)}
    db_session.add_all([user, student, pay_done, leave_active])
    await db_session.commit()

    service = StudentService(db_session)
    await service.repoint_primary_after_session_payment_completed(pay_done)
    await db_session.commit()
    await db_session.refresh(student)

    assert student.extra_data.get("primary_instance_id") == str(leave_active.id)
    assert "dashboard_therapy_hint_fa" not in (student.extra_data or {})


@pytest.mark.asyncio
async def test_repoint_primary_after_session_payment_sets_hint_when_no_active(db_session: AsyncSession):
    """اگر نمونهٔ فعال دیگری نباشد، primary خالی و راهنمای داشبورد ثبت شود."""
    user = User(
        id=uuid.uuid4(),
        username="stu_repoint2",
        hashed_password="x",
        role="student",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code="STU-REPOINT2",
        course_type="comprehensive",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=2,
        extra_data={},
    )
    pay_done = ProcessInstance(
        id=uuid.uuid4(),
        process_code="session_payment",
        student_id=student.id,
        current_state_code="payment_confirmed",
        is_completed=True,
        is_cancelled=False,
    )
    student.extra_data = {"primary_instance_id": str(pay_done.id)}
    db_session.add_all([user, student, pay_done])
    await db_session.commit()

    service = StudentService(db_session)
    await service.repoint_primary_after_session_payment_completed(pay_done)
    await db_session.commit()
    await db_session.refresh(student)

    assert student.extra_data.get("primary_instance_id") is None
    assert student.extra_data.get("dashboard_therapy_hint_fa")

