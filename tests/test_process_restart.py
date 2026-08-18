"""تست شروع دوباره فرایند (بایگانی + نمونهٔ جدید)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, get_password_hash
from app.core.engine import StateMachineEngine, InvalidTransitionError, UnauthorizedError
from app.database import get_db
from app.main import app
from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance, Student, User


@pytest_asyncio.fixture
async def extra_session_instance(db_session: AsyncSession, sample_student, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "extra_session.json")
    await db_session.commit()
    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="extra_session",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="admin",
        initial_context={"note": "before_restart"},
    )
    await db_session.commit()
    return instance


@pytest_asyncio.fixture
async def test_process_instance(db_session: AsyncSession, sample_process, sample_student, sample_user):
    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="test_process",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await engine.execute_transition(
        instance_id=instance.id,
        trigger_event="submitted",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()
    await db_session.refresh(instance)
    return instance


@pytest_asyncio.fixture
async def session_payment_instance(db_session: AsyncSession, sample_student, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()
    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="session_payment",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()
    return instance


@pytest_asyncio.fixture
async def semester_prep_instance(db_session: AsyncSession, sample_student, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()
    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="fall_semester_preparation",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()
    return instance


@pytest_asyncio.fixture
async def winter_semester_prep_instance(db_session: AsyncSession, sample_student, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()
    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="winter_semester_preparation",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()
    return instance


@pytest_asyncio.fixture
async def other_student(db_session: AsyncSession):
    uid = uuid.uuid4().hex[:12]
    user = User(
        id=uuid.uuid4(),
        username=f"other_student_{uid}",
        email=f"other_{uid}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="دانشجوی دیگر",
        role="student",
    )
    db_session.add(user)
    await db_session.flush()
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code=f"STU-OTH-{uid.upper()}",
        course_type="comprehensive",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=1,
    )
    db_session.add(student)
    await db_session.commit()
    return student


def _client_for_user(db_session: AsyncSession, user: User):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_engine_restart_archives_and_creates_new(
    db_session: AsyncSession,
    sample_user,
    extra_session_instance: ProcessInstance,
):
    engine = StateMachineEngine(db_session)
    old_id = extra_session_instance.id
    result = await engine.restart_process_instance(
        instance_id=old_id,
        actor_id=sample_user.id,
        actor_role="admin",
        reason="تست شروع دوباره",
        is_own_instance=False,
    )
    await db_session.commit()

    assert result.success is True
    assert result.old_instance_id == old_id
    assert result.new_instance_id != old_id
    assert result.current_state == "extra_request"

    old_row = await db_session.get(ProcessInstance, old_id)
    new_row = await db_session.get(ProcessInstance, result.new_instance_id)

    assert old_row.is_cancelled is True
    assert old_row.is_completed is False
    assert old_row.context_data.get("__archived_reason") == "user_restart"

    assert new_row.is_cancelled is False
    assert new_row.current_state_code == "extra_request"
    assert new_row.context_data.get("__restarted_from_instance_id") == str(old_id)


@pytest.mark.asyncio
async def test_engine_restart_completed_instance(
    db_session: AsyncSession,
    sample_user,
    test_process_instance: ProcessInstance,
):
    engine = StateMachineEngine(db_session)
    test_process_instance.is_completed = True
    test_process_instance.completed_at = test_process_instance.started_at
    await db_session.commit()

    result = await engine.restart_process_instance(
        instance_id=test_process_instance.id,
        actor_id=sample_user.id,
        actor_role="deputy_education",
        reason="شروع مجدد پس از تکمیل",
        is_own_instance=False,
    )
    await db_session.commit()

    assert result.success is True
    old_row = await db_session.get(ProcessInstance, test_process_instance.id)
    assert old_row.is_cancelled is True
    assert old_row.is_completed is False


@pytest.mark.asyncio
async def test_engine_restart_staff_forbidden(
    db_session: AsyncSession,
    sample_user,
    extra_session_instance: ProcessInstance,
):
    engine = StateMachineEngine(db_session)
    with pytest.raises(UnauthorizedError, match="مجوز"):
        await engine.restart_process_instance(
            instance_id=extra_session_instance.id,
            actor_id=sample_user.id,
            actor_role="staff",
            reason="تلاش کارمند",
            is_own_instance=False,
        )


@pytest.mark.asyncio
async def test_engine_rollback_staff_forbidden(
    db_session: AsyncSession,
    sample_user,
    test_process_instance: ProcessInstance,
):
    engine = StateMachineEngine(db_session)
    with pytest.raises(UnauthorizedError, match="مجوز"):
        await engine.rollback_to_previous_state(
            instance_id=test_process_instance.id,
            actor_id=sample_user.id,
            actor_role="staff",
            reason="تلاش کارمند",
        )


@pytest.mark.asyncio
async def test_engine_rollback_requires_reason_for_override(
    db_session: AsyncSession,
    sample_user,
    test_process_instance: ProcessInstance,
):
    engine = StateMachineEngine(db_session)
    with pytest.raises(InvalidTransitionError, match="دلیل"):
        await engine.rollback_to_previous_state(
            instance_id=test_process_instance.id,
            actor_id=sample_user.id,
            actor_role="admin",
            reason="  ",
        )


@pytest.mark.asyncio
async def test_engine_restart_blocked_process_raises(
    db_session: AsyncSession,
    sample_user,
    session_payment_instance: ProcessInstance,
):
    engine = StateMachineEngine(db_session)
    with pytest.raises(InvalidTransitionError, match="قابل شروع دوباره نیست"):
        await engine.restart_process_instance(
            instance_id=session_payment_instance.id,
            actor_id=sample_user.id,
            actor_role="admin",
            is_own_instance=False,
        )


@pytest.mark.asyncio
async def test_engine_restart_student_requires_reason(
    db_session: AsyncSession,
    sample_student_user,
    extra_session_instance: ProcessInstance,
):
    engine = StateMachineEngine(db_session)
    with pytest.raises(InvalidTransitionError, match="دلیل"):
        await engine.restart_process_instance(
            instance_id=extra_session_instance.id,
            actor_id=sample_student_user.id,
            actor_role="student",
            reason="",
            is_own_instance=True,
        )


@pytest.mark.asyncio
async def test_engine_restart_student_not_own_raises(
    db_session: AsyncSession,
    sample_student_user,
    extra_session_instance: ProcessInstance,
    other_student: Student,
):
    assert extra_session_instance.student_id != other_student.id
    engine = StateMachineEngine(db_session)
    with pytest.raises(UnauthorizedError):
        await engine.restart_process_instance(
            instance_id=extra_session_instance.id,
            actor_id=sample_student_user.id,
            actor_role="student",
            reason="دلیل تست",
            is_own_instance=False,
        )


@pytest.mark.asyncio
async def test_api_restart_admin_success(
    db_session: AsyncSession,
    sample_user,
    extra_session_instance: ProcessInstance,
):
    try:
        async with _client_for_user(db_session, sample_user) as client:
            r = await client.post(
                f"/api/process/{extra_session_instance.id}/restart",
                json={"reason": "از API مدیر", "confirm": True},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["old_instance_id"] == str(extra_session_instance.id)
        assert body["new_instance_id"] != body["old_instance_id"]
        assert body["current_state"] == "extra_request"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_api_restart_staff_forbidden(
    db_session: AsyncSession,
    sample_user,
    extra_session_instance: ProcessInstance,
):
    sample_user.role = "staff"
    sample_user.roles = ["staff"]
    await db_session.commit()
    try:
        async with _client_for_user(db_session, sample_user) as client:
            r = await client.post(
                f"/api/process/{extra_session_instance.id}/restart",
                json={"reason": "تلاش کارمند", "confirm": True},
            )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_api_rollback_staff_forbidden(
    db_session: AsyncSession,
    sample_user,
    test_process_instance: ProcessInstance,
):
    sample_user.role = "staff"
    sample_user.roles = ["staff"]
    await db_session.commit()
    try:
        async with _client_for_user(db_session, sample_user) as client:
            r = await client.post(
                f"/api/process/{test_process_instance.id}/rollback",
                json={"reason": "تلاش کارمند"},
            )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_api_rollback_deputy_success(
    db_session: AsyncSession,
    sample_user,
    test_process_instance: ProcessInstance,
):
    sample_user.role = "deputy_education"
    sample_user.roles = ["deputy_education"]
    await db_session.commit()
    try:
        async with _client_for_user(db_session, sample_user) as client:
            r = await client.post(
                f"/api/process/{test_process_instance.id}/rollback",
                json={"reason": "اصلاح اشتباه معاون"},
            )
        assert r.status_code == 200
        assert r.json()["success"] is True
        assert r.json()["trigger_event"] == "manual_rollback"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_api_restart_student_success(
    db_session: AsyncSession,
    sample_student_user,
    extra_session_instance: ProcessInstance,
):
    try:
        async with _client_for_user(db_session, sample_student_user) as client:
            r = await client.post(
                f"/api/process/{extra_session_instance.id}/restart",
                json={"reason": "اشتباه در ثبت اطلاعات", "confirm": True},
            )
        assert r.status_code == 200
        assert r.json()["success"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_api_restart_student_other_instance_forbidden(
    db_session: AsyncSession,
    sample_student_user,
    other_student: Student,
    sample_process,
    sample_user,
):
    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="test_process",
        student_id=other_student.id,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()

    try:
        async with _client_for_user(db_session, sample_student_user) as client:
            r = await client.post(
                f"/api/process/{instance.id}/restart",
                json={"reason": "تلاش غیرمجاز", "confirm": True},
            )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_api_restart_blocklist_returns_400(
    db_session: AsyncSession,
    sample_user,
    session_payment_instance: ProcessInstance,
):
    try:
        async with _client_for_user(db_session, sample_user) as client:
            r = await client.post(
                f"/api/process/{session_payment_instance.id}/restart",
                json={"confirm": True},
            )
        assert r.status_code == 400
        assert "قابل شروع دوباره" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_engine_restart_preserves_operational_context(
    db_session: AsyncSession,
    sample_user,
    extra_session_instance: ProcessInstance,
):
    """داده‌های عملیاتی قبلی (کلیدهای بدون __) باید در نمونهٔ جدید حفظ شوند."""
    engine = StateMachineEngine(db_session)
    result = await engine.restart_process_instance(
        instance_id=extra_session_instance.id,
        actor_id=sample_user.id,
        actor_role="admin",
        reason="تنظیم دوباره",
        is_own_instance=False,
    )
    await db_session.commit()

    new_row = await db_session.get(ProcessInstance, result.new_instance_id)
    assert new_row.context_data.get("note") == "before_restart"
    assert new_row.context_data.get("__restart_context_preserved") is True
    assert "__archived_reason" not in new_row.context_data


@pytest.mark.asyncio
async def test_engine_restart_semester_prep_now_allowed(
    db_session: AsyncSession,
    sample_user,
    semester_prep_instance: ProcessInstance,
):
    """فرایند آماده‌سازی ترم دیگر مسدود نیست و قابل شروع دوباره است."""
    engine = StateMachineEngine(db_session)
    result = await engine.restart_process_instance(
        instance_id=semester_prep_instance.id,
        actor_id=sample_user.id,
        actor_role="admin",
        reason="تنظیم دوبارهٔ آماده‌سازی ترم",
        is_own_instance=False,
    )
    await db_session.commit()

    assert result.success is True
    old_row = await db_session.get(ProcessInstance, semester_prep_instance.id)
    assert old_row.is_cancelled is True
    new_row = await db_session.get(ProcessInstance, result.new_instance_id)
    assert new_row.is_cancelled is False


@pytest.mark.asyncio
async def test_engine_restart_winter_semester_prep_allowed(
    db_session: AsyncSession,
    sample_user,
    winter_semester_prep_instance: ProcessInstance,
):
    """فرایند آماده‌سازی ترم زمستان هم قابل شروع دوباره است."""
    engine = StateMachineEngine(db_session)
    result = await engine.restart_process_instance(
        instance_id=winter_semester_prep_instance.id,
        actor_id=sample_user.id,
        actor_role="admin",
        reason="تنظیم دوبارهٔ آماده‌سازی زمستان",
        is_own_instance=False,
    )
    await db_session.commit()

    assert result.success is True
    old_row = await db_session.get(ProcessInstance, winter_semester_prep_instance.id)
    assert old_row.is_cancelled is True
    new_row = await db_session.get(ProcessInstance, result.new_instance_id)
    assert new_row.is_cancelled is False
    assert new_row.process_code == "winter_semester_preparation"


@pytest.mark.asyncio
async def test_api_restart_requires_confirm(
    db_session: AsyncSession,
    sample_user,
    extra_session_instance: ProcessInstance,
):
    try:
        async with _client_for_user(db_session, sample_user) as client:
            r = await client.post(
                f"/api/process/{extra_session_instance.id}/restart",
                json={"reason": "x", "confirm": False},
            )
        assert r.status_code == 400
        assert "تأیید" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
