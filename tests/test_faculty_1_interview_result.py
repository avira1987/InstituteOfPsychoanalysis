"""هیئت علمی (مثل سارا طراوتی) باید بتواند نتیجهٔ مصاحبه را ثبت کند."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.api.interview_slots_routes import list_interview_result_queue
from app.core.engine import StateMachineEngine
from app.core.rule_engine import RuleEvaluator
from app.core.transition import (
    TransitionManager,
    actor_may_fire_interview_operator_action,
    human_may_list_system_transition,
)
from app.meta.seed import load_process, load_rules
from app.models.operational_models import InterviewSlot, ProcessInstance, User


PROCESSES_DIR = Path(__file__).resolve().parent.parent / "metadata" / "processes"


async def _make_user(
    db: AsyncSession,
    *,
    role: str,
    prefix: str,
    roles: list[str] | None = None,
    full_name_fa: str | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        username=f"{prefix}_{uuid.uuid4().hex[:10]}",
        email=f"{prefix}_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa=full_name_fa or prefix,
        role=role,
        roles=list(roles) if roles is not None else [role],
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_instance(
    db: AsyncSession,
    *,
    sample_student,
    process_code: str,
    state: str,
    interviewer: User,
    creator: User,
) -> tuple[ProcessInstance, InterviewSlot]:
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code=process_code,
        student_id=sample_student.id,
        current_state_code=state,
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db.add(inst)
    await db.flush()
    t0 = datetime.now(timezone.utc) + timedelta(hours=1)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        course_type="introductory" if "intro" in process_code else "comprehensive",
        mode="in_person",
        created_by=creator.id,
        interviewer_user_id=interviewer.id,
        assigned_student_id=sample_student.id,
        assigned_instance_id=inst.id,
    )
    db.add(slot)
    await db.flush()
    return inst, slot


def test_faculty_1_may_fire_interview_operator_actions() -> None:
    assert actor_may_fire_interview_operator_action("faculty_1") is True
    assert actor_may_fire_interview_operator_action("interviewer") is True
    assert actor_may_fire_interview_operator_action("staff") is True
    assert actor_may_fire_interview_operator_action("therapist") is False
    assert human_may_list_system_transition("interview_time_reached", "faculty_1") is True
    assert human_may_list_system_transition("interview_time_reached", "therapist") is False


def test_validate_role_accepts_faculty_1_for_interview_result() -> None:
    tm = TransitionManager(None, RuleEvaluator())
    tr = SimpleNamespace(
        required_role="interviewer",
        trigger_event="interview_result_submitted",
        from_state_code="interview_completed",
    )
    assert tm.validate_role(tr, "faculty_1", "interview_result_submitted") is True
    assert tm.validate_role(tr, "interviewer", "interview_result_submitted") is True
    assert tm.validate_role(tr, "staff", "interview_result_submitted") is True
    assert tm.validate_role(tr, "therapist", "interview_result_submitted") is False

    tr_adv = SimpleNamespace(
        required_role="system",
        trigger_event="interview_time_reached",
        from_state_code="interview_payment_confirmed",
    )
    assert tm.validate_role(tr_adv, "faculty_1", "interview_time_reached") is True
    assert tm.validate_role(tr_adv, "therapist", "interview_time_reached") is False

    tr_comp = SimpleNamespace(
        required_role="interviewer",
        trigger_event="interview_result_accepted",
        from_state_code="interview_completed",
    )
    assert tm.validate_role(tr_comp, "faculty_1", "interview_result_accepted") is True


@pytest.mark.asyncio
async def test_result_queue_faculty_1_can_submit(
    db_session: AsyncSession, sample_student
) -> None:
    sara = await _make_user(
        db_session,
        role="faculty_1",
        prefix="sara_q",
        roles=["faculty_1"],
        full_name_fa="سارا طراوتی",
    )
    staff = await _make_user(db_session, role="staff", prefix="staff_q")
    await _make_instance(
        db_session,
        sample_student=sample_student,
        process_code="introductory_course_registration",
        state="interview_completed",
        interviewer=sara,
        creator=staff,
    )
    out = await list_interview_result_queue(include_past=False, db=db_session, user=sara)
    assert len(out["items"]) == 1
    item = out["items"][0]
    assert item["is_assigned_interviewer"] is True
    assert item["can_submit_result"] is True
    assert item["can_advance"] is False


@pytest.mark.asyncio
async def test_result_queue_faculty_1_can_advance_intro_payment_confirmed(
    db_session: AsyncSession, sample_student
) -> None:
    sara = await _make_user(
        db_session, role="faculty_1", prefix="sara_adv", roles=["faculty_1"]
    )
    staff = await _make_user(db_session, role="staff", prefix="staff_adv")
    await _make_instance(
        db_session,
        sample_student=sample_student,
        process_code="introductory_course_registration",
        state="interview_payment_confirmed",
        interviewer=sara,
        creator=staff,
    )
    out = await list_interview_result_queue(include_past=False, db=db_session, user=sara)
    assert len(out["items"]) == 1
    assert out["items"][0]["can_advance"] is True
    assert out["items"][0]["can_submit_result"] is False


@pytest.mark.asyncio
async def test_faculty_1_sees_and_fires_intro_interview_result(
    db_session: AsyncSession, sample_student
) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await db_session.commit()

    sara = await _make_user(
        db_session,
        role="faculty_1",
        prefix="sara_flow",
        roles=["faculty_1"],
        full_name_fa="سارا طراوتی",
    )
    staff = await _make_user(db_session, role="staff", prefix="staff_flow")
    inst, _slot = await _make_instance(
        db_session,
        sample_student=sample_student,
        process_code="introductory_course_registration",
        state="interview_completed",
        interviewer=sara,
        creator=staff,
    )
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    transitions = await engine.get_available_transitions(
        inst.id, "faculty_1", actor_id=sara.id
    )
    events = [t["trigger_event"] for t in transitions]
    assert "interview_result_submitted" in events

    status = await engine.get_instance_status(inst.id)
    ctx = status.get("context_data") or {}
    assert ctx.get("interviewer_user_id") == str(sara.id)

    result = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="interview_result_submitted",
        actor_id=sara.id,
        actor_role="faculty_1",
        payload={
            "interview_result": "full_admission",
            "to_state": "result_full_admission",
        },
    )
    assert result.success, result.error
    assert result.from_state == "interview_completed"
    refreshed = await engine.get_process_instance(inst.id)
    assert refreshed.current_state_code != "interview_completed"


@pytest.mark.asyncio
async def test_faculty_1_can_advance_then_submit_intro_result(
    db_session: AsyncSession, sample_student
) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await db_session.commit()

    sara = await _make_user(
        db_session, role="faculty_1", prefix="sara_two_step", roles=["faculty_1"]
    )
    staff = await _make_user(db_session, role="staff", prefix="staff_two_step")
    inst, _slot = await _make_instance(
        db_session,
        sample_student=sample_student,
        process_code="introductory_course_registration",
        state="interview_payment_confirmed",
        interviewer=sara,
        creator=staff,
    )
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    advance = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="interview_time_reached",
        actor_id=sara.id,
        actor_role="faculty_1",
        payload={},
    )
    assert advance.success, advance.error
    assert advance.to_state == "interview_completed"

    submitted = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="interview_result_submitted",
        actor_id=sara.id,
        actor_role="faculty_1",
        payload={
            "interview_result": "conditional_therapy",
            "to_state": "result_conditional_therapy",
        },
    )
    assert submitted.success, submitted.error
    assert submitted.from_state == "interview_completed"


@pytest.mark.asyncio
async def test_faculty_1_can_submit_comprehensive_accepted(
    db_session: AsyncSession, sample_student
) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "comprehensive_course_registration.json")
    await db_session.commit()

    sara = await _make_user(
        db_session, role="faculty_1", prefix="sara_comp_flow", roles=["faculty_1"]
    )
    staff = await _make_user(db_session, role="staff", prefix="staff_comp_flow")
    inst, _slot = await _make_instance(
        db_session,
        sample_student=sample_student,
        process_code="comprehensive_course_registration",
        state="interview_completed",
        interviewer=sara,
        creator=staff,
    )
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    transitions = await engine.get_available_transitions(
        inst.id, "faculty_1", actor_id=sara.id
    )
    events = [t["trigger_event"] for t in transitions]
    assert "interview_result_accepted" in events
    assert "interview_result_rejected" in events

    result = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="interview_result_accepted",
        actor_id=sara.id,
        actor_role="faculty_1",
        payload={"evaluation_notes": "پذیرش"},
    )
    assert result.success, result.error
    assert result.from_state == "interview_completed"


@pytest.mark.asyncio
async def test_unrelated_faculty_1_does_not_see_result_transitions(
    db_session: AsyncSession, sample_student
) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await db_session.commit()

    owner = await _make_user(
        db_session, role="faculty_1", prefix="owner_fac", roles=["faculty_1"]
    )
    other = await _make_user(
        db_session, role="faculty_1", prefix="other_fac", roles=["faculty_1"]
    )
    inst, _slot = await _make_instance(
        db_session,
        sample_student=sample_student,
        process_code="introductory_course_registration",
        state="interview_completed",
        interviewer=owner,
        creator=owner,
    )
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    transitions = await engine.get_available_transitions(
        inst.id, "faculty_1", actor_id=other.id
    )
    events = [t["trigger_event"] for t in transitions]
    assert "interview_result_submitted" not in events
