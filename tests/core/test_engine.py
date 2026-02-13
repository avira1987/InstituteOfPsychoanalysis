"""Unit tests for the State Machine Engine."""

import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import (
    StateMachineEngine,
    ProcessNotFoundError,
    InstanceNotFoundError,
    InvalidTransitionError,
    UnauthorizedError,
)
from app.models.operational_models import ProcessInstance


@pytest.mark.asyncio
class TestStateMachineEngine:

    async def test_start_process(self, db_session, sample_process, sample_rules, sample_student, sample_user):
        """Test starting a new process instance."""
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance is not None
        assert instance.process_code == "test_process"
        assert instance.current_state_code == "initial"
        assert instance.is_completed is False

    async def test_start_nonexistent_process(self, db_session, sample_student, sample_user):
        """Test starting a process that doesn't exist."""
        engine = StateMachineEngine(db_session)
        with pytest.raises(ProcessNotFoundError):
            await engine.start_process(
                process_code="nonexistent",
                student_id=sample_student.id,
                actor_id=sample_user.id,
                actor_role="admin",
            )

    async def test_execute_transition(self, db_session, sample_process, sample_rules, sample_student, sample_student_user):
        """Test executing a valid transition."""
        engine = StateMachineEngine(db_session)

        # Start process
        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        # Execute transition: initial -> review
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "initial"
        assert result.to_state == "review"

    async def test_execute_transition_with_rules(self, db_session, sample_process, sample_rules, sample_student, sample_user, sample_student_user):
        """Test transition that requires rule evaluation."""
        engine = StateMachineEngine(db_session)

        # Start process and move to review state
        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        # Approve (has condition: is_not_intern, student is not intern -> should pass)
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="approve",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert result.success is True
        assert result.to_state == "approved"

    async def test_transition_unauthorized(self, db_session, sample_process, sample_rules, sample_student, sample_student_user):
        """Test transition with unauthorized role."""
        engine = StateMachineEngine(db_session)

        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        # Move to review
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        # Try to approve as student (should fail, requires admin)
        with pytest.raises(UnauthorizedError):
            await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="approve",
                actor_id=sample_student_user.id,
                actor_role="student",
            )

    async def test_invalid_transition(self, db_session, sample_process, sample_rules, sample_student, sample_user):
        """Test triggering a non-existent transition."""
        engine = StateMachineEngine(db_session)

        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        with pytest.raises(InvalidTransitionError):
            await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="nonexistent_event",
                actor_id=sample_user.id,
                actor_role="admin",
            )

    async def test_terminal_state_completes_instance(self, db_session, sample_process, sample_rules, sample_student, sample_user, sample_student_user):
        """Test that reaching a terminal state completes the instance."""
        engine = StateMachineEngine(db_session)

        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        # initial -> review
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        # review -> rejected (terminal)
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="reject",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert result.success is True
        assert result.to_state == "rejected"
        assert instance.is_completed is True

    async def test_completed_instance_cannot_transition(self, db_session, sample_process, sample_rules, sample_student, sample_user, sample_student_user):
        """Test that a completed instance cannot have further transitions."""
        engine = StateMachineEngine(db_session)

        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id, trigger_event="submitted",
            actor_id=sample_student_user.id, actor_role="student",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id, trigger_event="reject",
            actor_id=sample_user.id, actor_role="admin",
        )
        await db_session.commit()

        with pytest.raises(InvalidTransitionError):
            await engine.execute_transition(
                instance_id=instance.id, trigger_event="approve",
                actor_id=sample_user.id, actor_role="admin",
            )

    async def test_get_instance_status(self, db_session, sample_process, sample_rules, sample_student, sample_user, sample_student_user):
        """Test getting process instance status with history."""
        engine = StateMachineEngine(db_session)

        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id, trigger_event="submitted",
            actor_id=sample_student_user.id, actor_role="student",
        )
        await db_session.commit()

        status = await engine.get_instance_status(instance.id)
        assert status["process_code"] == "test_process"
        assert status["current_state"] == "review"
        assert len(status["history"]) == 2  # initial + submitted

    async def test_get_available_transitions(self, db_session, sample_process, sample_rules, sample_student, sample_user, sample_student_user):
        """Test getting available transitions."""
        engine = StateMachineEngine(db_session)

        instance = await engine.start_process(
            process_code="test_process",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        # As student at initial state
        transitions = await engine.get_available_transitions(instance.id, "student")
        assert len(transitions) == 1
        assert transitions[0]["trigger_event"] == "submitted"

    async def test_get_nonexistent_instance(self, db_session):
        """Test getting a non-existent instance."""
        engine = StateMachineEngine(db_session)
        with pytest.raises(InstanceNotFoundError):
            await engine.get_instance_status(uuid.uuid4())
