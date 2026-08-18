"""RBAC اختصاصی آماده‌سازی ترم و اعلان دست‌به‌دست نقش بعدی."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine, UnauthorizedError
from app.meta.seed import load_process
from app.models.operational_models import PanelFlashMessage, User
from app.services.panel_action_notifications import notification_action_path
from app.services.semester_prep_rbac import portal_role_can_act_on_prep_state
from app.services.semester_prep_service import get_or_start_prep_instance

PROCESSES_DIR = Path(__file__).resolve().parents[2] / "metadata" / "processes"


@pytest.mark.asyncio
async def test_prep_rbac_blocks_wrong_roles_on_transitions(
    db_session: AsyncSession, sample_user
):
    await load_process(db_session, PROCESSES_DIR / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session,
        "fall_semester_preparation",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()
    engine = StateMachineEngine(db_session)

    # کارمند نباید تقویم را ثبت کند
    with pytest.raises(UnauthorizedError):
        await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="calendar_submitted",
            actor_id=sample_user.id,
            actor_role="staff",
        )

    ok = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="calendar_submitted",
        actor_id=sample_user.id,
        actor_role="course_committee",
    )
    await db_session.commit()
    assert ok.success

    # کمیته نباید شهریه بزند
    with pytest.raises(UnauthorizedError):
        await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="tuition_submitted",
            actor_id=sample_user.id,
            actor_role="course_committee",
        )

    for trigger, role in (
        ("tuition_submitted", "deputy_education"),
        ("license_reviewed", "deputy_education"),
        ("course_list_submitted", "course_committee"),
        ("courses_finalized", "course_committee"),
    ):
        r = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event=trigger,
            actor_id=sample_user.id,
            actor_role=role,
        )
        await db_session.commit()
        assert r.success, r.error

    # معاون نباید بازاریابی بزند
    with pytest.raises(UnauthorizedError):
        await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="marketing_started",
            actor_id=sample_user.id,
            actor_role="deputy_education",
        )

    r = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="marketing_started",
        actor_id=sample_user.id,
        actor_role="staff",
    )
    await db_session.commit()
    assert r.success

    # معاون نباید مصاحبه‌گر تعیین کند
    with pytest.raises(UnauthorizedError):
        await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="interviewers_assigned",
            actor_id=sample_user.id,
            actor_role="deputy_education",
        )


@pytest.mark.asyncio
async def test_calendar_submitted_creates_flash_for_deputy(
    db_session: AsyncSession, sample_user
):
    await load_process(db_session, PROCESSES_DIR / "fall_semester_preparation.json")
    await db_session.commit()

    deputy = User(
        username=f"prep_deputy_{sample_user.id.hex[:8]}",
        hashed_password="x",
        role="deputy_education",
        roles=["deputy_education"],
        is_active=True,
        full_name_fa="معاون تست",
        phone="09121110001",
    )
    staff = User(
        username=f"prep_staff_{sample_user.id.hex[:8]}",
        hashed_password="x",
        role="staff",
        roles=["staff"],
        is_active=True,
        full_name_fa="کارمند تست",
        phone="09121110002",
    )
    db_session.add_all([deputy, staff])
    await db_session.flush()

    inst, _ = await get_or_start_prep_instance(
        db_session,
        "fall_semester_preparation",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    result = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="calendar_submitted",
        actor_id=sample_user.id,
        actor_role="course_committee",
    )
    await db_session.commit()
    assert result.success, result.error

    flashes = list(
        (
            await db_session.execute(
                select(PanelFlashMessage).where(PanelFlashMessage.user_id == deputy.id)
            )
        )
        .scalars()
        .all()
    )
    assert flashes, "deputy should receive flash after calendar_submitted"
    assert any(
        "شهریه" in (f.message or "") or "آماده‌سازی" in (f.message or "") for f in flashes
    )
    assert any(
        f.source_path and "semester-prep/workbench" in f.source_path for f in flashes
    )

    staff_flashes = list(
        (
            await db_session.execute(
                select(PanelFlashMessage).where(PanelFlashMessage.user_id == staff.id)
            )
        )
        .scalars()
        .all()
    )
    # بعد از تقویم، گیرنده معاون است نه کارمند
    assert not any(
        f.source_path and "semester-prep/workbench" in (f.source_path or "")
        for f in staff_flashes
    )


@pytest.mark.asyncio
async def test_marketing_started_flash_goes_to_staff_not_deputy(
    db_session: AsyncSession, sample_user
):
    await load_process(db_session, PROCESSES_DIR / "fall_semester_preparation.json")
    await db_session.commit()

    deputy = User(
        username=f"prep_deputy2_{sample_user.id.hex[:8]}",
        hashed_password="x",
        role="deputy_education",
        roles=["deputy_education"],
        is_active=True,
        full_name_fa="معاون تست ۲",
        phone="09121110003",
    )
    staff = User(
        username=f"prep_staff2_{sample_user.id.hex[:8]}",
        hashed_password="x",
        role="staff",
        roles=["staff"],
        is_active=True,
        full_name_fa="کارمند تست ۲",
        phone="09121110004",
    )
    db_session.add_all([deputy, staff])
    await db_session.flush()

    inst, _ = await get_or_start_prep_instance(
        db_session,
        "fall_semester_preparation",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    for trigger in (
        "calendar_submitted",
        "tuition_submitted",
        "license_reviewed",
        "course_list_submitted",
        "courses_finalized",
        "marketing_started",
    ):
        r = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event=trigger,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert r.success, r.error

    staff_flashes = list(
        (
            await db_session.execute(
                select(PanelFlashMessage).where(PanelFlashMessage.user_id == staff.id)
            )
        )
        .scalars()
        .all()
    )
    assert any(
        "مصاحبه" in (f.message or "") or "بازاریابی" in (f.message or "")
        for f in staff_flashes
    ), "staff should get marketing→interview handoff flash"

    # آخرین flashهای بعد از marketing نباید فقط برای معاون باشد
    deputy_msgs = [
        f.message
        for f in (
            await db_session.execute(
                select(PanelFlashMessage).where(PanelFlashMessage.user_id == deputy.id)
            )
        )
        .scalars()
        .all()
        if f.message and "مصاحبه" in f.message and "بازاریابی" in f.message
    ]
    assert not deputy_msgs


def test_notification_action_path_prep_goes_to_workbench():
    href = notification_action_path(
        {
            "kind": "process",
            "process_code": "fall_semester_preparation",
            "state_code": "tuition_entry",
            "instance_id": "11111111-1111-1111-1111-111111111111",
            "student_id": "22222222-2222-2222-2222-222222222222",
            "responsible_role_code": "deputy_education_director",
        }
    )
    assert "/panel/semester-prep/workbench" in href
    assert "process_code=fall_semester_preparation" in href


def test_prep_state_portal_matrix():
    assert portal_role_can_act_on_prep_state(
        "course_committee", "fall_semester_preparation", "calendar_entry"
    )
    assert portal_role_can_act_on_prep_state(
        "deputy_education", "fall_semester_preparation", "tuition_entry"
    )
    assert not portal_role_can_act_on_prep_state(
        "staff", "fall_semester_preparation", "tuition_entry"
    )
    assert portal_role_can_act_on_prep_state(
        "internal_manager", "fall_semester_preparation", "interviewer_assignment"
    )
    assert not portal_role_can_act_on_prep_state(
        "site_manager", "fall_semester_preparation", "interviewer_assignment"
    )
