"""Tests for SMS when a process is started for a student."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.engine import StateMachineEngine
from app.models.operational_models import SmsSimulationOutbox


@pytest.mark.asyncio
async def test_notify_sends_sms_for_admin_start(
    db_session, sample_process, sample_rules, sample_student, sample_student_user, sample_user
):
    sample_student_user.phone = "09121234567"
    db_session.add(sample_student_user)
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    with patch(
        "app.services.manual_process_start_notification.notification_service.send_notification",
        new_callable=AsyncMock,
    ) as send_mock:
        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

    assert instance is not None
    send_mock.assert_awaited_once()
    args = send_mock.await_args
    assert args[0][0] == "sms"
    assert args[0][1] == "manual_process_started"
    assert args[0][2] == "09121234567"
    assert args[0][3]["process_name_fa"] == "فرایند تست"


@pytest.mark.asyncio
async def test_notify_sends_sms_for_student_and_system_roles(
    db_session, sample_process, sample_rules, sample_student, sample_student_user, sample_user
):
    sample_student_user.phone = "09129876543"
    db_session.add(sample_student_user)
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    with patch(
        "app.services.manual_process_start_notification.notification_service.send_notification",
        new_callable=AsyncMock,
    ) as send_mock:
        await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

    assert send_mock.await_count == 2


@pytest.mark.asyncio
async def test_notify_writes_simulation_outbox_when_no_mock(
    db_session, sample_process, sample_rules, sample_student, sample_student_user, sample_user
):
    sample_student_user.phone = "09121112233"
    db_session.add(sample_student_user)
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    await engine.start_process(
        process_code="test_process",
        student_id=sample_student.id,
        actor_id=sample_student_user.id,
        actor_role="student",
    )
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(SmsSimulationOutbox).where(SmsSimulationOutbox.phone == "09121112233")
        )
    ).scalars().all()
    assert len(rows) >= 1
    assert "فرایند تست" in (rows[-1].message or "")
    assert rows[-1].template_key == "manual_process_started"
