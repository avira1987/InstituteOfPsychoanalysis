"""Slice 1 / Phase E: patient_referral list → assign → notify → closed + therapist SMS."""

from pathlib import Path
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import SmsSimulationOutbox, User
from app.services.fee_determination_runner import SYSTEM_ACTOR_ID


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


@pytest.mark.asyncio
class TestPatientReferralHubE2E:
    async def _load(self, db: AsyncSession) -> StateMachineEngine:
        await load_rules(db)
        await load_process(db, PROCESSES_DIR / "educational_leave.json")
        await load_process(db, PROCESSES_DIR / "patient_referral.json")
        await load_process(db, PROCESSES_DIR / "violation_registration.json")
        await db.commit()
        return StateMachineEngine(db)

    async def test_intern_two_term_referral_closes_with_therapist_sms(
        self,
        db_session: AsyncSession,
        sample_student,
        sample_student_user: User,
        sample_user: User,
    ):
        sample_student.is_intern = True
        sample_student_user.phone = "09121234567"
        suid = uuid.uuid4().hex[:8]
        therapist = User(
            id=uuid.uuid4(),
            username=f"therapist_ref_{suid}",
            email=f"therapist_ref_{suid}@test.com",
            hashed_password=get_password_hash("testpass"),
            full_name_fa="درمانگر جایگزین تست",
            role="therapist",
            phone="09127654321",
        )
        db_session.add(therapist)
        await db_session.flush()

        engine = await self._load(db_session)
        parent = await engine.start_process(
            process_code="educational_leave",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        for trigger, role, actor, payload in (
            ("student_submitted", "student", sample_student_user.id, {"leave_terms": 2}),
            (
                "committee_set_meeting",
                "progress_committee",
                sample_user.id,
                {
                    "committee_meeting_at": "2026-09-15T10:30:00+00:00",
                    "committee_meeting_mode": "online",
                    "committee_meeting_link": "https://meet.example/leave",
                },
            ),
            ("meeting_held", "progress_committee", sample_user.id, None),
            ("committee_approved", "progress_committee", sample_user.id, {"leave_terms": 2}),
        ):
            r = await engine.execute_transition(
                instance_id=parent.id,
                trigger_event=trigger,
                actor_id=actor,
                actor_role=role,
                payload=payload or {},
            )
            await db_session.commit()
            assert r.success is True, f"{trigger}: {r.error}"

        parent = await engine.get_process_instance(parent.id)
        child_id = uuid.UUID(str((parent.context_data or {}).get("patient_referral_instance_id")))
        child = await engine.get_process_instance(child_id)
        assert child.current_state_code == "referral_triggered"

        listed = await engine.execute_transition(
            instance_id=child.id,
            trigger_event="list_submitted",
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
            payload={"referral_patients": [{"patient_label": "بیمار ارجاعی"}]},
        )
        await db_session.commit()
        assert listed.success is True, listed.error

        assigned = await engine.execute_transition(
            instance_id=child.id,
            trigger_event="assignments_done",
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
            payload={
                "referral_patients": [
                    {
                        "patient_label": "بیمار ارجاعی",
                        "assigned_therapist_user_id": str(therapist.id),
                    }
                ]
            },
        )
        await db_session.commit()
        assert assigned.success is True, assigned.error

        notified = await engine.execute_transition(
            instance_id=child.id,
            trigger_event="notifications_done",
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()
        assert notified.success is True, notified.error

        child = await engine.get_process_instance(child.id)
        assert child.current_state_code == "closed"
        assert child.is_completed is True

        phones = {
            row.phone
            for row in (
                await db_session.execute(select(SmsSimulationOutbox))
            ).scalars().all()
        }
        assert any("09127654321" in p or p.endswith("917654321") for p in phones), phones
        assert any("09121234567" in p or p.endswith("9121234567") for p in phones), phones
