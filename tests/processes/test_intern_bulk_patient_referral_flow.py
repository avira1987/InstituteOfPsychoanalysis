"""Test intern_bulk_patient_referral flow (process 72)."""

import pytest
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.meta.student_step_forms import apply_register_to_context


PATIENT_ROWS = [
    {"row_id": "row-1", "patient_name": "بیمار الف", "patient_phone": "09121111111"},
    {"row_id": "row-2", "patient_name": "بیمار ب", "patient_phone": "09122222222"},
]


@pytest.mark.asyncio
class TestInternBulkPatientReferralFlow:

    async def _load(self, db_session: AsyncSession) -> StateMachineEngine:
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "intern_bulk_patient_referral.json")
        await db_session.commit()
        return StateMachineEngine(db_session)

    async def test_load_and_start_supervision(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="intern_bulk_patient_referral",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert instance.process_code == "intern_bulk_patient_referral"
        assert instance.current_state_code == "supervision_start"

    async def test_full_happy_path_to_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="intern_bulk_patient_referral",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        ctx = apply_register_to_context(
            dict(instance.context_data or {}),
            "supervision_start",
            {
                "meeting_datetime": "2026-06-20T14:00:00+00:00",
                "meeting_held": True,
                "referral_conditions": "ارجاع فوری به درمانگر دیگر",
                "patient_referral_rows": PATIENT_ROWS,
            },
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="meeting_and_conditions_logged",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
            payload={
                "referral_conditions": "ارجاع فوری به درمانگر دیگر",
                "patient_referral_rows": PATIENT_ROWS,
            },
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "student_patient_log"

        student_rows = [
            {
                **PATIENT_ROWS[0],
                "contacted": True,
                "contact_notes": "بیمار موافقت کرد",
            },
            {
                **PATIENT_ROWS[1],
                "contacted": True,
                "contact_notes": "تماس گرفته شد",
            },
        ]
        ctx = apply_register_to_context(
            dict(instance.context_data or {}),
            "student_patient_log",
            {"patient_referral_rows": student_rows},
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_patient_contacts_done",
            actor_id=sample_user.id,
            actor_role="student",
            payload={"patient_referral_rows": student_rows},
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "general_therapy_committee_review"

        committee_rows = [
            {
                **student_rows[0],
                "committee_contacted": True,
                "referral_notes": "ارجاع به دکتر احمدی",
                "replacement_therapist": "دکتر احمدی",
            },
            {
                **student_rows[1],
                "committee_contacted": True,
                "referral_notes": "ارجاع به دکتر رضایی",
                "replacement_therapist": "دکتر رضایی",
            },
        ]
        ctx = apply_register_to_context(
            dict(instance.context_data or {}),
            "general_therapy_committee_review",
            {"patient_referral_rows": committee_rows},
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="committee_referral_notes_complete",
            actor_id=sample_user.id,
            actor_role="therapy_committee_executor",
            payload={"patient_referral_rows": committee_rows},
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "coordination_followup"

        coord_rows = [
            {**committee_rows[0], "followup_done": True},
            {**committee_rows[1], "followup_done": True},
        ]
        ctx = apply_register_to_context(
            dict(instance.context_data or {}),
            "coordination_followup",
            {"patient_referral_rows": coord_rows},
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="coordination_followup_complete",
            actor_id=sample_user.id,
            actor_role="therapy_education_coordinator",
            payload={"patient_referral_rows": coord_rows},
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "completed"
        assert instance.is_completed is True
