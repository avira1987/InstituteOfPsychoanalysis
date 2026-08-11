"""End-to-end flow for supervision_block_transition (slot book + both payments)."""

from __future__ import annotations

from datetime import time
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_password_hash
from app.core.engine import StateMachineEngine
from app.meta.process_forms import get_process_forms
from app.meta.seed import load_process, load_rules
from app.meta.student_step_forms import apply_register_to_context, validate_student_step_forms
from app.models.operational_models import EducationalTherapistSlot, ProcessInstance, Student, User
from app.services.educational_therapist_slot_service import create_slot


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


@pytest.mark.asyncio
class TestSupervisionBlockTransitionFlow:

    async def test_supervision_block_transition_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        await load_process(db_session, PROCESSES_DIR / "supervision_block_transition.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_block_transition",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert instance.process_code == "supervision_block_transition"
        assert instance.current_state_code == "payment_intent_50th"
        assert instance.is_completed is False

    async def test_supervision_block_supervisor_form_defined(self):
        forms = get_process_forms(
            "supervision_block_transition", state_code="supervisor_slots_displayed"
        )
        assert len(forms) == 1
        assert forms[0]["code"] == "supervision_block_supervisor_pick"
        names = {f["name"] for f in forms[0]["fields"]}
        assert "new_supervisor_id" in names
        assert "slot_ids" in names

    async def test_supervision_block_transition_flow_to_both_paid_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """آخرین گام پرداخت ۵۰ام — سازگاری با تست قبلی."""
        await load_process(db_session, PROCESSES_DIR / "supervision_block_transition.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_block_transition",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        inst = (
            await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
        ).scalars().first()
        inst.current_state_code = "new_block_first_paid"
        await db_session.flush()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_success_50th",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "both_paid_completed"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "both_paid_completed"
        assert instance.is_completed is True

    async def test_full_path_at_50_select_book_pay_both(
        self, db_session: AsyncSession, sample_student, sample_student_user, sample_user
    ):
        """start → at_50 → slots → select+book → pay new → unlock → pay 50th → done."""
        await load_rules(db_session)
        await load_process(db_session, PROCESSES_DIR / "supervision_block_transition.json")
        await db_session.commit()

        supervisor = User(
            username="sup_block_e2e",
            email="sup_block_e2e@test.local",
            hashed_password=get_password_hash("x"),
            full_name_fa="سوپروایزر تست بلوک",
            role="supervisor",
            is_active=True,
        )
        db_session.add(supervisor)
        await db_session.flush()

        slot = await create_slot(
            db_session,
            therapist_user_id=supervisor.id,
            day_of_week=0,
            start_local_time=time(10, 0),
            end_local_time=time(11, 0),
            course_type=None,
            created_by=sample_user.id,
        )
        await db_session.commit()

        st = await db_session.get(Student, sample_student.id)
        extra = dict(st.extra_data or {})
        lms = dict(extra.get("lms") or {})
        lms["supervision_blocks"] = [
            {"id": "block-1", "supervisor_id": str(supervisor.id), "hours": 50, "status": "active"}
        ]
        extra["lms"] = lms
        st.extra_data = extra
        flag_modified(st, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_block_transition",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
            initial_context={"current_supervision_block_attendance": 50},
        )
        await db_session.commit()

        # Step 1: at 50th → slots displayed
        r1 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="check_attendance",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={"current_supervision_block_attendance": 50},
        )
        await db_session.commit()
        assert r1.success is True, r1.error
        assert r1.to_state == "supervisor_slots_displayed"

        instance = await engine.get_process_instance(instance.id)
        ctx = instance.context_data or {}
        assert ctx.get("available_supervisor_slots") or ctx.get("available_supervisors")
        assert ctx.get("current_supervision_block_attendance") == 50

        forms = get_process_forms(
            "supervision_block_transition", state_code="supervisor_slots_displayed"
        )
        values = {
            "new_supervisor_id": str(supervisor.id),
            "slot_ids": [str(slot.id)],
            "weekly_sessions": 1,
            "selected_supervision_weekly_count": 1,
        }
        ok, missing = validate_student_step_forms(forms, values, ctx)
        assert ok is True, missing

        instance.context_data = apply_register_to_context(
            instance.context_data or {},
            "supervisor_slots_displayed",
            values,
        )
        flag_modified(instance, "context_data")
        await db_session.flush()

        # Step 2: select + book + prepare payment
        r2 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_selects_supervisor_and_time",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload=values,
        )
        await db_session.commit()
        assert r2.success is True, r2.error
        assert r2.to_state == "slot_selected"

        instance = await engine.get_process_instance(instance.id)
        ctx = instance.context_data or {}
        assert ctx.get("payment_amount_rial")
        assert ctx.get("calculated_start_date") or ctx.get("start_date_rule") == "24h"
        assert str(ctx.get("new_supervisor_id")) == str(supervisor.id)

        slot_row = await db_session.get(EducationalTherapistSlot, slot.id)
        assert slot_row.status == "booked"
        assert slot_row.assigned_student_id == sample_student.id

        # Step 3: pay first session of new block
        r3 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_success_new_block_first",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert r3.success is True, r3.error
        assert r3.to_state == "new_block_first_paid"

        instance = await engine.get_process_instance(instance.id)
        ctx = instance.context_data or {}
        assert ctx.get("payment_unlocked_for_50th_session") is True
        assert ctx.get("supervision_payment_purpose") == "session_50th"

        st = await db_session.get(Student, sample_student.id)
        assert (st.extra_data or {}).get("payment_unlocked_for_50th_session") is True
        blocks = ((st.extra_data or {}).get("lms") or {}).get("supervision_blocks") or []
        assert any(isinstance(b, dict) and b.get("status") == "active" for b in blocks)

        # Step 4: pay 50th
        r4 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_success_50th",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert r4.success is True, r4.error
        assert r4.to_state == "both_paid_completed"

        instance = await engine.get_process_instance(instance.id)
        assert instance.is_completed is True
        lms = ((await db_session.get(Student, sample_student.id)).extra_data or {}).get("lms") or {}
        assert any(
            isinstance(link, dict) and link.get("kind") == "supervision_50th"
            for link in (lms.get("online_links") or [])
        )
