"""Tests for ActionHandler (BUILD_TODO § ب)."""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, ProcessInstance, TherapySession
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

    async def test_deduct_credit_session_reduces_context_balance(
        self, db_session: AsyncSession, sample_student: Student
    ):
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="therapist_session_cancellation",
            student_id=sample_student.id,
            current_state_code="pending",
            context_data={"session_credit_balance": 1_000_000.0},
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        results = await handler.handle_actions(
            [{"type": "deduct_credit_session", "amount": 500_000}],
            instance,
            {},
        )
        await db_session.commit()

        assert results[0]["success"] is True
        await db_session.refresh(instance)
        assert instance.context_data["session_credit_balance"] == 500_000.0

    async def test_create_session_link_sets_meeting_url(
        self, db_session: AsyncSession, sample_student: Student, sample_user
    ):
        today = datetime.now(timezone.utc).date()
        ts = TherapySession(
            id=uuid.uuid4(),
            student_id=sample_student.id,
            therapist_id=sample_user.id,
            session_date=today + timedelta(days=3),
            status="scheduled",
            payment_status="paid",
        )
        db_session.add(ts)
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="start_therapy",
            student_id=sample_student.id,
            current_state_code="active",
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        await handler.handle_actions(
            [{"type": "create_session_link", "meeting_url": "https://meet.example/x"}],
            instance,
            {},
        )
        await db_session.commit()

        await db_session.refresh(ts)
        assert ts.meeting_url == "https://meet.example/x"
        assert ts.links_unlocked is True

    async def test_update_record_writes_gradebook(
        self, db_session: AsyncSession, sample_student: Student
    ):
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="live_supervision_ta_evaluation",
            student_id=sample_student.id,
            current_state_code="evaluation_computed",
            context_data={"total_score": 80, "result_status": "PASS"},
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        await handler.handle_actions([{"type": "update_record"}], instance, {})
        await db_session.commit()

        await db_session.refresh(sample_student)
        gb = sample_student.extra_data.get("gradebook", {})
        assert "live_supervision_ta_evaluation" in gb
        assert gb["live_supervision_ta_evaluation"]["total_score"] == 80

    async def test_external_integration_logs_events_without_webhook(
        self, db_session: AsyncSession, sample_student: Student
    ):
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="specialized_commission_review",
            student_id=sample_student.id,
            current_state_code="x",
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        results = await handler.handle_actions(
            [{"type": "send_unlock_to_lms", "foo": 1}],
            instance,
            {"k": "v"},
        )
        await db_session.commit()

        assert results[0]["success"] is True
        await db_session.refresh(instance)
        ev = instance.context_data.get("integration_events") or []
        assert len(ev) >= 1
        assert ev[-1]["action"] == "send_unlock_to_lms"
        assert "skipped" in str(results[0].get("detail", "")) or "integration=" in str(
            results[0].get("detail", "")
        )

    async def test_merge_initial_payment_sets_next_installment_due_term2(
        self, db_session: AsyncSession, sample_student: Student
    ):
        """merge_instance_context initial_payment برای اقساط: شمارنده و next_installment_due_at."""
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="intro_second_semester_registration",
            student_id=sample_student.id,
            current_state_code="registration_complete",
            context_data={"payment_method": "installment", "installment_count": 4},
        )
        db_session.add(instance)
        await db_session.flush()

        handler = ActionHandler(db_session)
        await handler.handle_actions(
            [{"type": "merge_instance_context", "mode": "initial_payment"}],
            instance,
            {},
        )
        await db_session.commit()
        await db_session.refresh(instance)
        assert instance.context_data.get("pending_installments_remaining") == 3
        due = instance.context_data.get("next_installment_due_at")
        assert due and len(str(due)) >= 10
