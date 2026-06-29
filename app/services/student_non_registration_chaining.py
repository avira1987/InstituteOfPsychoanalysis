"""زنجیرهٔ خودکار فرایند ۴۲ — عدم ثبت‌نام ترم بعد."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, User

logger = logging.getLogger(__name__)

_BRANCH_REGISTER_DAYS = 2
_BRANCH_LEAVE_DAYS = 3

_LEAVE_PROCESS_CODES = frozenset({"educational_leave", "full_education_leave"})
_REGISTRATION_COMPLETE_STATES = frozenset({
    "registration_complete",
    "term2_registration_closed",
})


def _ctx(instance: ProcessInstance) -> dict:
    return StateMachineEngine._as_mapping(instance.context_data)


async def _resolve_system_actor_id(db) -> uuid.UUID:
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row:
        return row
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row if row else uuid.uuid4()


async def _find_active_non_registration(
    db,
    student_id: uuid.UUID,
    *,
    state_code: str | None = None,
) -> ProcessInstance | None:
    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == "student_non_registration",
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
    )
    if state_code:
        stmt = stmt.where(ProcessInstance.current_state_code == state_code)
    return (await db.execute(stmt)).scalars().first()


def _set_branch_deadlines(ctx: dict, branch: str) -> dict:
    now = datetime.now(timezone.utc)
    out = dict(ctx)
    if branch == "register":
        out["branch_register_entered_at"] = now.isoformat()
        out["branch_register_deadline_at"] = (now + timedelta(days=_BRANCH_REGISTER_DAYS)).isoformat()
    elif branch == "leave":
        out["branch_leave_entered_at"] = now.isoformat()
        out["branch_leave_deadline_at"] = (now + timedelta(days=_BRANCH_LEAVE_DAYS)).isoformat()
    return out


async def chain_student_non_registration_after_transition(
    db,
    engine: StateMachineEngine,
    instance: ProcessInstance,
    to_state: str,
    actor_id: uuid.UUID,
) -> None:
    """پس از ترنزیشن فرایند ۴۲: دعوت‌نامه، مهلت شاخه‌ها."""
    if instance.process_code != "student_non_registration":
        return

    sys_id = await _resolve_system_actor_id(db)

    if to_state == "meeting_scheduled":
        try:
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="invitation_sent",
                actor_id=sys_id,
                actor_role="system",
            )
            if not result.success:
                logger.warning(
                    "student_non_registration invitation_sent failed instance=%s err=%s",
                    instance.id,
                    result.error,
                )
        except Exception:
            logger.exception(
                "student_non_registration auto invitation_sent failed instance=%s",
                instance.id,
            )
        return

    ctx = _ctx(instance)
    if to_state == "branch_register":
        instance.context_data = _set_branch_deadlines(ctx, "register")
        flag_modified(instance, "context_data")
        await db.flush()
    elif to_state == "branch_leave":
        instance.context_data = _set_branch_deadlines(ctx, "leave")
        flag_modified(instance, "context_data")
        await db.flush()


async def maybe_advance_non_registration_on_leave_start(
    db,
    engine: StateMachineEngine,
    student_id: uuid.UUID,
    leave_process_code: str,
    actor_id: uuid.UUID,
) -> None:
    """پس از آغاز مرخصی: اگر فرایند ۴۲ در branch_leave است → leave_process_started."""
    if leave_process_code not in _LEAVE_PROCESS_CODES:
        return
    inst = await _find_active_non_registration(db, student_id, state_code="branch_leave")
    if not inst:
        return
    sys_id = await _resolve_system_actor_id(db)
    try:
        await engine.execute_transition(
            instance_id=inst.id,
            trigger_event="leave_process_started",
            actor_id=actor_id or sys_id,
            actor_role="student",
            payload={"source_leave_process": leave_process_code},
        )
    except Exception:
        logger.exception(
            "leave_process_started chain failed student=%s instance=%s",
            student_id,
            inst.id,
        )


async def maybe_advance_non_registration_on_term_registration(
    db,
    engine: StateMachineEngine,
    instance: ProcessInstance,
    actor_id: uuid.UUID,
) -> None:
    """پس از تکمیل ثبت‌نام ترم: اگر فرایند ۴۲ در branch_register است → courses_selected."""
    pcode = instance.process_code
    state = instance.current_state_code
    if pcode == "comprehensive_term_start" and state == "registration_complete":
        pass
    elif pcode == "intro_second_semester_registration" and state == "term2_registration_closed":
        pass
    else:
        return

    nr_inst = await _find_active_non_registration(
        db, instance.student_id, state_code="branch_register",
    )
    if not nr_inst:
        return
    sys_id = await _resolve_system_actor_id(db)
    try:
        await engine.execute_transition(
            instance_id=nr_inst.id,
            trigger_event="courses_selected",
            actor_id=actor_id or sys_id,
            actor_role="student",
            payload={
                "source_registration_process": pcode,
                "source_registration_instance_id": str(instance.id),
            },
        )
    except Exception:
        logger.exception(
            "courses_selected chain failed student=%s nr_instance=%s",
            instance.student_id,
            nr_inst.id,
        )
