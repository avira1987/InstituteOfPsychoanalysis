"""تست موتور چک روزانه کارهای عقب‌افتاده."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.models.meta_models import StateDefinition
from app.models.operational_models import PanelTaskReminder, ProcessInstance
from app.services.daily_overdue_check_service import (
    collect_overdue_tasks,
    dispatch_daily_reminders,
    run_daily_overdue_check_pass,
)
from app.services.panel_action_notifications import build_action_notifications


@pytest.mark.asyncio
async def test_collect_overdue_sla_task(
    db_session, sample_student, sample_process, sample_user
):
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="test_process",
        student_id=sample_student.id,
        current_state_code="review",
        is_completed=False,
        is_cancelled=False,
        last_transition_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    db_session.add(inst)
    await db_session.commit()

    tasks = await collect_overdue_tasks(db_session)
    keys = {t.task_key for t in tasks}
    assert f"sla:{inst.id}:review" in keys


@pytest.mark.asyncio
async def test_daily_overdue_creates_reminder_and_sms(
    db_session, sample_student, sample_process, sample_user, sample_student_user
):
    sample_student_user.phone = "09121234567"
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="test_process",
        student_id=sample_student.id,
        current_state_code="initial",
        is_completed=False,
        is_cancelled=False,
        last_transition_at=datetime.now(timezone.utc) - timedelta(hours=200),
    )
    db_session.add(inst)
    await db_session.commit()

    run_date = datetime.now(timezone.utc).date()
    tasks = await collect_overdue_tasks(db_session)
    student_tasks = [t for t in tasks if t.instance_id == str(inst.id)]
    if not student_tasks:
        from app.models.meta_models import StateDefinition

        sd = (
            await db_session.execute(
                select(StateDefinition).where(
                    StateDefinition.process_id == sample_process.id,
                    StateDefinition.code == "initial",
                )
            )
        ).scalars().first()
        if sd:
            sd.sla_hours = 1
            await db_session.commit()
        tasks = await collect_overdue_tasks(db_session)
        student_tasks = [t for t in tasks if t.instance_id == str(inst.id)]

    assert student_tasks, "expected at least one overdue task for instance"

    dispatch = await dispatch_daily_reminders(
        db_session, student_tasks[:1], run_date=run_date
    )
    await db_session.commit()

    assert dispatch["notifications_created"] >= 1
    assert dispatch["sms_sent"] >= 1

    r = await db_session.execute(
        select(PanelTaskReminder).where(PanelTaskReminder.student_id == sample_student.id)
    )
    reminders = r.scalars().all()
    assert len(reminders) >= 1
    assert reminders[0].action_path.startswith("/panel/")


@pytest.mark.asyncio
async def test_daily_overdue_dedup_same_day(
    db_session, sample_student, sample_process, sample_user
):
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="test_process",
        student_id=sample_student.id,
        current_state_code="review",
        is_completed=False,
        is_cancelled=False,
        last_transition_at=datetime.now(timezone.utc) - timedelta(hours=72),
    )
    db_session.add(inst)
    await db_session.commit()

    first = await run_daily_overdue_check_pass(db_session, triggered_by="manual", force=True)
    await db_session.commit()
    second = await run_daily_overdue_check_pass(db_session, triggered_by="manual", force=True)
    await db_session.commit()

    assert first["notifications_created"] >= 1
    assert second["skipped_dedup"] >= first["notifications_created"]


@pytest.mark.asyncio
async def test_build_action_notifications_includes_daily_overdue(
    db_session, sample_student, sample_process, sample_student_user
):
    sample_student_user.phone = "09122222222"
    from app.models.meta_models import StateDefinition

    sd = (
        await db_session.execute(
            select(StateDefinition).where(
                StateDefinition.process_id == sample_process.id,
                StateDefinition.code == "initial",
            )
        )
    ).scalars().first()
    if sd:
        sd.sla_hours = 1
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="test_process",
        student_id=sample_student.id,
        current_state_code="initial",
        is_completed=False,
        is_cancelled=False,
        last_transition_at=datetime.now(timezone.utc) - timedelta(hours=48),
    )
    db_session.add(inst)
    await db_session.commit()

    await run_daily_overdue_check_pass(db_session, triggered_by="manual", force=True)
    await db_session.commit()

    out = await build_action_notifications(db_session, sample_student_user, limit=20, offset=0)
    kinds = {i.get("kind") for i in out["items"]}
    assert "daily_overdue" in kinds


@pytest.mark.asyncio
async def test_installment_overdue_detected(
    db_session, sample_student, sample_user
):
    from pathlib import Path

    from app.meta.seed import load_process, load_rules

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "introductory_course_registration.json")
    await db_session.commit()

    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="registration_complete",
        is_completed=False,
        is_cancelled=False,
        context_data={
            "next_installment_due_at": (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat(),
        },
    )
    db_session.add(inst)
    await db_session.commit()

    tasks = await collect_overdue_tasks(db_session)
    assert any(t.kind == "installment" and t.instance_id == str(inst.id) for t in tasks)


@pytest.mark.asyncio
async def test_prep_calendar_deadline_overdue(db_session, sample_user):
    from pathlib import Path

    from app.meta.seed import load_process
    from app.services.semester_prep_service import FALL_PREP, get_or_start_prep_instance
    from sqlalchemy.orm.attributes import flag_modified

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    ctx = dict(inst.context_data or {})
    ctx["calendar_sla_deadline_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    inst.context_data = ctx
    flag_modified(inst, "context_data")
    await db_session.commit()

    tasks = await collect_overdue_tasks(db_session)
    prep_tasks = [t for t in tasks if t.instance_id == str(inst.id)]
    assert any(t.kind == "prep_calendar_deadline" for t in prep_tasks)


@pytest.mark.asyncio
async def test_prep_overdue_notifies_all_deputy_education_users(db_session, sample_user):
    from pathlib import Path

    from app.api.auth import get_password_hash
    from app.meta.seed import load_process
    from app.models.operational_models import User
    from app.services.semester_prep_service import FALL_PREP, get_or_start_prep_instance

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    deputy_users = []
    for i in range(2):
        uid = uuid.uuid4()
        suid = uuid.uuid4().hex[:8]
        u = User(
            id=uid,
            username=f"deputy_{suid}",
            email=f"deputy_{suid}@test.com",
            hashed_password=get_password_hash("testpass"),
            full_name_fa=f"معاون {i}",
            role="deputy_education",
            phone=f"0912{i:07d}",
        )
        db_session.add(u)
        deputy_users.append(u)
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    ctx = dict(inst.context_data or {})
    ctx["calendar_sla_deadline_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    inst.context_data = ctx
    flag_modified(inst, "context_data")
    await db_session.commit()

    run_date = datetime.now(timezone.utc).date()
    tasks = await collect_overdue_tasks(db_session)
    prep_tasks = [t for t in tasks if t.instance_id == str(inst.id)]
    assert prep_tasks

    dispatch = await dispatch_daily_reminders(db_session, prep_tasks[:1], run_date=run_date)
    await db_session.commit()

    assert dispatch["notifications_created"] >= 2
    r = await db_session.execute(
        select(PanelTaskReminder).where(PanelTaskReminder.instance_id == inst.id)
    )
    reminders = r.scalars().all()
    assert len(reminders) >= 2


@pytest.mark.asyncio
async def test_resolve_users_for_assigned_role_maps_metadata(db_session, sample_user):
    from app.api.auth import get_password_hash
    from app.models.operational_models import User
    from app.services.process_role_user_resolver import resolve_users_for_assigned_role

    uid = uuid.uuid4()
    suid = uuid.uuid4().hex[:8]
    deputy = User(
        id=uid,
        username=f"deputy_map_{suid}",
        email=f"deputy_map_{suid}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="معاون نقش",
        role="deputy_education",
    )
    db_session.add(deputy)
    await db_session.commit()

    users = await resolve_users_for_assigned_role(db_session, "course_committee_executive")
    roles = {u.role for u in users}
    assert "deputy_education" in roles
    assert any(u.id == deputy.id for u in users)
