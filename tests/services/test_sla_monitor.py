"""Tests for SLA Monitor (BUILD_TODO § ج-۲ و بخش ۴)."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import User, ProcessInstance, Student
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.services.sla_monitor import SLAMonitor, SLABreachInfo


@pytest.mark.asyncio
class TestSLAMonitor:

    async def test_resolve_contact_for_role_returns_phone_when_user_exists(
        self, db_session: AsyncSession, sample_user
    ):
        """_resolve_contact_for_role returns phone or email for first active user with role."""
        sample_user.role = "deputy_education"
        sample_user.phone = "09121234567"
        await db_session.flush()

        monitor = SLAMonitor()
        contact = await monitor._resolve_contact_for_role(db_session, "deputy_education")
        assert contact == "09121234567"

    async def test_resolve_contact_for_role_fallback_when_no_user(self, db_session: AsyncSession):
        """_resolve_contact_for_role returns 'admin' when no user has role."""
        monitor = SLAMonitor()
        contact = await monitor._resolve_contact_for_role(db_session, "nonexistent_role_xyz")
        assert contact == "admin"

    async def test_handle_breach_uses_committee_template_for_educational_leave(
        self, db_session: AsyncSession, sample_student_user
    ):
        """For process educational_leave, breach notification uses committee_sla_breach and deputy_education."""
        deputy = User(
            id=uuid.uuid4(),
            username="deputy_test",
            email="deputy@test.com",
            hashed_password="x",
            full_name_fa="معاون آموزش",
            role="deputy_education",
            is_active=True,
            phone="09991112222",
        )
        db_session.add(deputy)
        await db_session.flush()

        breach = SLABreachInfo(
            instance_id=str(uuid.uuid4()),
            process_code="educational_leave",
            state_code="committee_review",
            sla_hours=168,
            elapsed_hours=200,
            breach_event="sla_breach_7days",
        )

        with patch("app.services.sla_monitor.notification_service") as mock_ns:
            mock_send = AsyncMock(return_value=type("R", (), {"success": True})())
            mock_ns.send_notification = mock_send
            monitor = SLAMonitor()
            await monitor._handle_breach(breach, db_session)

        mock_send.assert_called_once()
        call_kw = mock_send.call_args[1]
        assert call_kw["template_name"] == "committee_sla_breach"
        assert call_kw["recipient_contact"] == "09991112222"
        assert call_kw["context"]["process_code"] == "educational_leave"

    async def test_start_monitoring_loop_runs_and_stops_cleanly(self):
        """start_monitoring_loop runs in background and exits when stop_monitoring() is called (BUILD_TODO § ج-۲ بخش ۴)."""
        call_count = 0

        @asynccontextmanager
        async def mock_db_factory():
            nonlocal call_count
            call_count += 1
            class MockDB:
                async def commit(self):
                    pass
            yield MockDB()

        monitor = SLAMonitor()
        task = asyncio.create_task(
            monitor.start_monitoring_loop(mock_db_factory, interval_seconds=1)
        )
        await asyncio.sleep(0.3)  # let at least one iteration run
        monitor.stop_monitoring()
        await asyncio.wait_for(task, timeout=5.0)
        assert call_count >= 1

    async def test_handle_breach_fires_transition_when_on_sla_breach_event_set(
        self, db_session: AsyncSession
    ):
        """دسته ج-۲: وقتی breach_event (on_sla_breach_event) تنظیم شده، engine.execute_transition با آن trigger فراخوانی می‌شود."""
        breach = SLABreachInfo(
            instance_id=str(uuid.uuid4()),
            process_code="educational_leave",
            state_code="committee_review",
            sla_hours=168,
            elapsed_hours=200,
            breach_event="sla_breach_7days",
        )
        with patch("app.services.sla_monitor.notification_service") as mock_ns:
            mock_ns.send_notification = AsyncMock(return_value=type("R", (), {"success": True})())
            with patch("app.core.engine.StateMachineEngine") as MockEngine:
                mock_engine_instance = AsyncMock()
                mock_engine_instance.execute_transition = AsyncMock(
                    return_value=type("Result", (), {"success": True})()
                )
                MockEngine.return_value = mock_engine_instance

                monitor = SLAMonitor()
                await monitor._handle_breach(breach, db_session)

        mock_engine_instance.execute_transition.assert_called_once()
        call_kw = mock_engine_instance.execute_transition.call_args[1]
        assert call_kw["trigger_event"] == "sla_breach_7days"
        assert call_kw["actor_role"] == "system"
        assert str(call_kw["instance_id"]) == breach.instance_id
