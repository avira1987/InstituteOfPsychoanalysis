"""فاز ۱: implied و نقش ثانویه باید ترنزیشن را ببینند و بزنند."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.core.engine import StateMachineEngine, UnauthorizedError
from app.core.rule_engine import RuleEvaluator
from app.core.transition import TransitionManager
from app.meta.seed import load_process, load_rules
from app.models.operational_models import InterviewSlot, ProcessInstance, StateHistory, User


PROCESSES_DIR = Path(__file__).resolve().parent.parent / "metadata" / "processes"


async def _make_user(
    db: AsyncSession,
    *,
    role: str,
    prefix: str,
    roles: list[str] | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        username=f"{prefix}_{uuid.uuid4().hex[:10]}",
        email=f"{prefix}_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa=prefix,
        role=role,
        roles=list(roles) if roles is not None else [role],
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


def test_validate_role_faculty_1_grants_supervisor() -> None:
    tm = TransitionManager(None, RuleEvaluator())
    tr = SimpleNamespace(
        required_role="supervisor",
        trigger_event="supervisor_rejected",
        from_state_code="supervisor_review",
    )
    assert tm.validate_role(tr, "faculty_1", "supervisor_rejected") is True
    assert tm.validate_role(tr, "supervisor", "supervisor_rejected") is True
    assert tm.validate_role(tr, "therapist", "supervisor_rejected") is False


def test_validate_role_educational_instructor_grants_instructor() -> None:
    tm = TransitionManager(None, RuleEvaluator())
    tr = SimpleNamespace(
        required_role="instructor",
        trigger_event="cancellation_confirmed",
        from_state_code="cancellation_request",
    )
    assert tm.validate_role(tr, "educational_instructor", "cancellation_confirmed") is True
    assert tm.validate_role(tr, "instructor", "cancellation_confirmed") is True
    assert tm.validate_role(tr, "therapist", "cancellation_confirmed") is False


def test_validate_role_therapist_string_does_not_grant_interviewer() -> None:
    tm = TransitionManager(None, RuleEvaluator())
    tr = SimpleNamespace(
        required_role="interviewer",
        trigger_event="interview_result_submitted",
        from_state_code="interview_completed",
    )
    assert tm.validate_role(tr, "therapist", "interview_result_submitted") is False
    assert tm.validate_role(tr, "interviewer", "interview_result_submitted") is True


@pytest.mark.asyncio
async def test_faculty_1_sees_supervisor_transitions(
    db_session: AsyncSession, sample_student
) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "supervision_session_increase.json")
    await db_session.commit()

    faculty = await _make_user(
        db_session, role="faculty_1", prefix="fac_sup", roles=["faculty_1"]
    )
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="supervision_session_increase",
        student_id=sample_student.id,
        current_state_code="supervisor_review",
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    transitions = await engine.get_available_transitions(
        inst.id, "faculty_1", actor_id=faculty.id
    )
    events = [t["trigger_event"] for t in transitions]
    assert "supervisor_rejected" in events
    assert "supervisor_approved" in events

    result = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="supervisor_rejected",
        actor_id=faculty.id,
        actor_role="faculty_1",
        payload={},
    )
    assert result.success, result.error
    refreshed = await engine.get_process_instance(inst.id)
    assert refreshed.current_state_code == "request_rejected"


@pytest.mark.asyncio
async def test_educational_instructor_sees_instructor_transitions(
    db_session: AsyncSession, sample_student
) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "class_session_cancellation.json")
    await db_session.commit()

    edu = await _make_user(
        db_session,
        role="educational_instructor",
        prefix="edu_ins",
        roles=["educational_instructor"],
    )
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="class_session_cancellation",
        student_id=sample_student.id,
        current_state_code="cancellation_request",
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    transitions = await engine.get_available_transitions(
        inst.id, "educational_instructor", actor_id=edu.id
    )
    events = [t["trigger_event"] for t in transitions]
    assert "cancellation_confirmed" in events

    therapist = await _make_user(
        db_session, role="therapist", prefix="ther_no", roles=["therapist"]
    )
    hidden = await engine.get_available_transitions(
        inst.id, "therapist", actor_id=therapist.id
    )
    assert "cancellation_confirmed" not in [t["trigger_event"] for t in hidden]


@pytest.mark.asyncio
async def test_dual_role_therapist_interviewer_sees_and_fires_interview(
    db_session: AsyncSession, sample_student
) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await db_session.commit()

    dual = await _make_user(
        db_session,
        role="therapist",
        prefix="dual_int",
        roles=["therapist", "interviewer"],
    )
    staff = await _make_user(db_session, role="staff", prefix="staff_dual")
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="interview_completed",
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.flush()
    t0 = datetime.now(timezone.utc) + timedelta(hours=1)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        course_type="introductory",
        mode="in_person",
        created_by=staff.id,
        interviewer_user_id=dual.id,
        assigned_student_id=sample_student.id,
        assigned_instance_id=inst.id,
    )
    db_session.add(slot)
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    without_actor = await engine.get_available_transitions(inst.id, "therapist")
    assert "interview_result_submitted" not in [t["trigger_event"] for t in without_actor]

    transitions = await engine.get_available_transitions(
        inst.id, "therapist", actor_id=dual.id
    )
    events = [t["trigger_event"] for t in transitions]
    assert "interview_result_submitted" in events

    result = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="interview_result_submitted",
        actor_id=dual.id,
        actor_role="therapist",
        payload={
            "interview_result": "full_admission",
            "to_state": "result_full_admission",
        },
    )
    assert result.success, result.error
    hist = (
        await db_session.execute(
            select(StateHistory)
            .where(StateHistory.instance_id == inst.id)
            .order_by(StateHistory.entered_at.desc())
        )
    ).scalars().first()
    assert hist is not None
    assert hist.actor_role == "interviewer"


@pytest.mark.asyncio
async def test_therapist_without_interviewer_cannot_fire_interview(
    db_session: AsyncSession, sample_student
) -> None:
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await db_session.commit()

    therapist = await _make_user(
        db_session, role="therapist", prefix="ther_only", roles=["therapist"]
    )
    staff = await _make_user(db_session, role="staff", prefix="staff_ther")
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="interview_completed",
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.flush()
    t0 = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.add(
        InterviewSlot(
            id=uuid.uuid4(),
            starts_at=t0,
            ends_at=t0 + timedelta(hours=1),
            course_type="introductory",
            mode="in_person",
            created_by=staff.id,
            interviewer_user_id=therapist.id,
            assigned_student_id=sample_student.id,
            assigned_instance_id=inst.id,
        )
    )
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    events = [
        t["trigger_event"]
        for t in await engine.get_available_transitions(
            inst.id, "therapist", actor_id=therapist.id
        )
    ]
    assert "interview_result_submitted" not in events

    with pytest.raises(UnauthorizedError):
        await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="interview_result_submitted",
            actor_id=therapist.id,
            actor_role="therapist",
            payload={
                "interview_result": "full_admission",
                "to_state": "result_full_admission",
            },
        )
