"""Hub data contract: violation spawn payload and suspension flags."""

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance, Student
from app.services.action_handler import ActionHandler
from app.services.hub_student_flags import HUB_VIOLATION, VIOLATION_PRESENT_BLOCK_REASON_FA


def _contract_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "metadata" / "hub_data_contract.json"


class TestHubDataContractFile:
    def test_hub_data_contract_file_lists_locked_keys(self):
        data = json.loads(_contract_path().read_text(encoding="utf-8"))
        extra = data["student_extra_data"]
        assert "is_suspended" in extra
        assert "class_present_blocked" in extra
        assert "gates.next_term_registration_blocked" in extra
        assert "violation_registration" in data["hub_process_codes"]


@pytest.mark.asyncio
class TestHubViolationContract:
    async def test_merge_copies_title_fa_to_description(
        self, db_session: AsyncSession, sample_student: Student
    ):
        parent = ProcessInstance(
            id=uuid.uuid4(),
            process_code="student_session_cancellation",
            student_id=sample_student.id,
            current_state_code="violation_and_applied",
            context_data={},
        )
        db_session.add(parent)
        await db_session.flush()
        handler = ActionHandler(db_session)
        merged = await handler._merge_violation_registration_initial_payload(
            parent,
            {
                "reason": "student_cancellation_violation",
                "title_fa": "تخلف آموزشی — کنسلی بیش از ۱۲٪",
            },
            {},
        )
        assert merged["source_reason"] == "student_cancellation_violation"
        assert merged["description"] == "تخلف آموزشی — کنسلی بیش از ۱۲٪"
        assert merged["source_process_code"] == "student_session_cancellation"
        assert merged["parent_instance_id"] == str(parent.id)

    async def test_block_attendance_on_violation_sets_present_block(
        self, db_session: AsyncSession, sample_student: Student
    ):
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code=HUB_VIOLATION,
            student_id=sample_student.id,
            current_state_code="suspension_immediate",
        )
        db_session.add(instance)
        await db_session.flush()
        handler = ActionHandler(db_session)
        out = await handler._handle_block_attendance(
            {"type": "block_attendance_registration"}, instance, {}
        )
        await db_session.commit()
        assert out == "class_present_blocked"
        await db_session.refresh(sample_student)
        flag = (sample_student.extra_data or {}).get("class_present_blocked") or {}
        assert flag.get("active") is True
        assert flag.get("source") == HUB_VIOLATION
        assert VIOLATION_PRESENT_BLOCK_REASON_FA in str(flag.get("reason_fa") or "")

    async def test_suspend_class_on_violation_sets_is_suspended(
        self, db_session: AsyncSession, sample_student: Student
    ):
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code=HUB_VIOLATION,
            student_id=sample_student.id,
            current_state_code="suspension_immediate",
        )
        db_session.add(instance)
        await db_session.flush()
        handler = ActionHandler(db_session)
        await handler.handle_actions(
            [{"type": "suspend_class_registration"}], instance, {}
        )
        await db_session.commit()
        await db_session.refresh(sample_student)
        extra = sample_student.extra_data or {}
        assert extra.get("class_access_blocked") is True
        assert extra.get("is_suspended") is True

    async def test_block_class_access_on_other_process_does_not_suspend(
        self, db_session: AsyncSession, sample_student: Student
    ):
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code="start_therapy",
            student_id=sample_student.id,
            current_state_code="week9_blocked",
        )
        db_session.add(instance)
        await db_session.flush()
        handler = ActionHandler(db_session)
        await handler.handle_actions([{"type": "block_class_access"}], instance, {})
        await db_session.commit()
        await db_session.refresh(sample_student)
        extra = sample_student.extra_data or {}
        assert extra.get("class_access_blocked") is True
        assert extra.get("is_suspended") is not True

    async def test_next_term_block_on_violation_sets_is_suspended(
        self, db_session: AsyncSession, sample_student: Student
    ):
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code=HUB_VIOLATION,
            student_id=sample_student.id,
            current_state_code="suspension_next_term",
        )
        db_session.add(instance)
        await db_session.flush()
        handler = ActionHandler(db_session)
        await handler.handle_actions(
            [{"type": "block_next_term_registration"}], instance, {}
        )
        await db_session.commit()
        await db_session.refresh(sample_student)
        extra = sample_student.extra_data or {}
        assert extra.get("gates", {}).get("next_term_registration_blocked") is True
        assert extra.get("is_suspended") is True

    async def test_lift_suspension_clears_hub_flags(
        self, db_session: AsyncSession, sample_student: Student
    ):
        sample_student.extra_data = {
            "is_suspended": True,
            "class_access_blocked": True,
            "class_present_blocked": {
                "active": True,
                "process_code": HUB_VIOLATION,
                "source": HUB_VIOLATION,
            },
            "gates": {"next_term_registration_blocked": True},
        }
        await db_session.flush()
        instance = ProcessInstance(
            id=uuid.uuid4(),
            process_code=HUB_VIOLATION,
            student_id=sample_student.id,
            current_state_code="suspension_immediate",
        )
        db_session.add(instance)
        await db_session.flush()
        handler = ActionHandler(db_session)
        out = await handler._handle_lift_suspension_restrictions(
            {"type": "lift_suspension_restrictions"}, instance, {}
        )
        await db_session.commit()
        assert out == "lift_suspension_restrictions"
        await db_session.refresh(sample_student)
        extra = sample_student.extra_data or {}
        assert extra.get("is_suspended") is False
        assert extra.get("class_access_blocked") is False
        assert extra.get("gates", {}).get("next_term_registration_blocked") is False
        assert extra.get("class_present_blocked") is None
