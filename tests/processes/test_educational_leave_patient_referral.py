"""Slice 1 / Phase D: educational_leave intern 2-term → patient_referral hub."""

from pathlib import Path
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance
from app.services.hub_patient_referral import normalize_referral_patients


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


def test_normalize_referral_patients_maps_label_and_therapist():
    rows = normalize_referral_patients(
        [
            {"patient_name": "بیمار الف", "therapist_user_id": "  t1  "},
            {"patient_label": "بیمار ب"},
            {"patient_label": "  "},
        ]
    )
    assert rows == [
        {"patient_label": "بیمار الف", "assigned_therapist_user_id": "t1"},
        {"patient_label": "بیمار ب", "assigned_therapist_user_id": None},
    ]


@pytest.mark.asyncio
class TestEducationalLeavePatientReferralSpawn:
    async def _load(self, db_session: AsyncSession) -> StateMachineEngine:
        await load_rules(db_session)
        await load_process(db_session, PROCESSES_DIR / "educational_leave.json")
        await load_process(db_session, PROCESSES_DIR / "patient_referral.json")
        await load_process(db_session, PROCESSES_DIR / "violation_registration.json")
        await db_session.commit()
        return StateMachineEngine(db_session)

    async def test_intern_two_term_approve_spawns_referral_and_officer_lists(
        self,
        db_session: AsyncSession,
        sample_student,
        sample_student_user,
        sample_user,
    ):
        sample_student.is_intern = True
        await db_session.flush()
        engine = await self._load(db_session)

        parent = await engine.start_process(
            process_code="educational_leave",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        r = await engine.execute_transition(
            instance_id=parent.id,
            trigger_event="student_submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={"leave_terms": 2},
        )
        await db_session.commit()
        assert r.success is True, r.error

        r = await engine.execute_transition(
            instance_id=parent.id,
            trigger_event="committee_set_meeting",
            actor_id=sample_user.id,
            actor_role="progress_committee",
            payload={
                "committee_meeting_at": "2026-09-15T10:30:00+00:00",
                "committee_meeting_mode": "online",
                "committee_meeting_link": "https://meet.example/leave",
            },
        )
        await db_session.commit()
        assert r.success is True, r.error

        r = await engine.execute_transition(
            instance_id=parent.id,
            trigger_event="meeting_held",
            actor_id=sample_user.id,
            actor_role="progress_committee",
        )
        await db_session.commit()
        assert r.success is True, r.error

        r = await engine.execute_transition(
            instance_id=parent.id,
            trigger_event="committee_approved",
            actor_id=sample_user.id,
            actor_role="progress_committee",
            payload={"leave_terms": 2},
        )
        await db_session.commit()
        assert r.success is True, r.error
        parent = await engine.get_process_instance(parent.id)
        assert parent.current_state_code == "approved_intern_2term"
        child_id = (parent.context_data or {}).get("patient_referral_instance_id")
        assert child_id

        child = await engine.get_process_instance(uuid.UUID(str(child_id)))
        assert child.process_code == "patient_referral"
        assert child.current_state_code == "referral_triggered"
        ctx = child.context_data or {}
        assert ctx.get("parent_instance_id") == str(parent.id)
        assert ctx.get("source_process_code") == "educational_leave"
        assert ctx.get("leave_terms") == 2
        assert ctx.get("student_id") == str(sample_student.id)
        assert ctx.get("source_reason") == "educational_leave_intern_2term"

        listed = await engine.execute_transition(
            instance_id=child.id,
            trigger_event="list_submitted",
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
            payload={
                "referral_patients": [
                    {"patient_label": "بیمار نمونه ۱"},
                    {"patient_name": "بیمار نمونه ۲"},
                ]
            },
        )
        await db_session.commit()
        assert listed.success is True, listed.error
        child = await engine.get_process_instance(child.id)
        assert child.current_state_code == "patients_listed"
        rows = (child.context_data or {}).get("referral_patients") or []
        assert [x.get("patient_label") for x in rows] == ["بیمار نمونه ۱", "بیمار نمونه ۲"]

        # sanity: hub instance is queryable as child of this leave
        found = (
            await db_session.execute(
                select(ProcessInstance).where(
                    ProcessInstance.process_code == "patient_referral",
                    ProcessInstance.student_id == sample_student.id,
                )
            )
        ).scalars().all()
        assert any(str(x.id) == str(child.id) for x in found)
