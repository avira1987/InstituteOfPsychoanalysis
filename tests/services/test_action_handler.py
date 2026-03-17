"""Tests for ActionHandler (BUILD_TODO § ب)."""

import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, ProcessInstance
from app.services.action_handler import ActionHandler


@pytest.mark.asyncio
class TestActionHandlerTherapyLifecycle:

    async def test_activate_therapy_sets_student_therapy_started(
        self, db_session: AsyncSession, sample_student: Student
    ):
        """activate_therapy sets student.therapy_started = True."""
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="start_therapy",
            student_id=sample_student.id,
            current_state_code="payment_pending",
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        results = await handler.handle_actions(
            [{"type": "activate_therapy"}],
            instance,
            {},
        )
        await db_session.commit()

        assert len(results) == 1
        assert results[0]["success"] is True
        assert "therapy_activated" in str(results[0].get("detail", ""))

        await db_session.refresh(sample_student)
        assert sample_student.therapy_started is True

    async def test_activate_therapy_sets_therapist_id_from_context(
        self, db_session: AsyncSession, sample_student: Student, sample_user
    ):
        """activate_therapy can set therapist_id from instance/context."""
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="start_therapy",
            student_id=sample_student.id,
            current_state_code="payment_pending",
            context_data={"therapist_id": str(sample_user.id)},
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        await handler.handle_actions([{"type": "activate_therapy"}], instance, {})
        await db_session.commit()

        await db_session.refresh(sample_student)
        assert sample_student.therapy_started is True
        assert sample_student.therapist_id == sample_user.id

    async def test_block_class_access_sets_extra_data(
        self, db_session: AsyncSession, sample_student: Student
    ):
        """block_class_access sets student.extra_data['class_access_blocked'] = True."""
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="start_therapy",
            student_id=sample_student.id,
            current_state_code="eligibility_check",
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        results = await handler.handle_actions(
            [{"type": "block_class_access"}],
            instance,
            {},
        )
        await db_session.commit()

        assert results[0]["success"] is True
        await db_session.refresh(sample_student)
        assert sample_student.extra_data is not None
        assert sample_student.extra_data.get("class_access_blocked") is True

    async def test_resolve_access_restrictions_clears_block(
        self, db_session: AsyncSession, sample_student: Student
    ):
        """resolve_access_restrictions sets class_access_blocked = False."""
        sample_student.extra_data = {"class_access_blocked": True}
        await db_session.flush()

        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="start_therapy",
            student_id=sample_student.id,
            current_state_code="therapy_active",
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        await handler.handle_actions(
            [{"type": "resolve_access_restrictions"}],
            instance,
            {},
        )
        await db_session.commit()

        await db_session.refresh(sample_student)
        assert sample_student.extra_data.get("class_access_blocked") is False

    async def test_session_payment_actions_have_handlers(
        self, db_session: AsyncSession, sample_student: Student
    ):
        """دسته ب: اکشن‌های session_payment (استاب) ثبت شده‌اند و بدون خطا اجرا می‌شوند."""
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="session_payment",
            student_id=sample_student.id,
            current_state_code="awaiting_payment",
        )
        db_session.add(instance)
        await db_session.flush()

        actions = [
            {"type": "zero_debt_if_paid"},
            {"type": "add_to_credit_balance"},
            {"type": "allocate_credit_to_sessions"},
            {"type": "unlock_session_links"},
            {"type": "unlock_attendance_registration"},
        ]
        handler = ActionHandler(db_session)
        results = await handler.handle_actions(actions, instance, {})
        await db_session.commit()

        assert len(results) == 5
        for r in results:
            assert r["success"] is True, r.get("error", r)
            assert "no_handler" not in str(r.get("detail", ""))
