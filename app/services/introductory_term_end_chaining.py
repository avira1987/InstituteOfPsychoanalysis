"""زنجیرهٔ خودکار پایان ترم آشنایی تا بررسی شرط درمان."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, User
from app.services.admission_type_service import (
    derive_has_active_therapist,
    normalize_admission_type,
    persist_admission_type_on_student,
)
from app.models.operational_models import Student

logger = logging.getLogger(__name__)

_ADVANCERS: dict[str, tuple[str, ...]] = {
    "grades_submitted": ("auto_generate_transcripts",),
    "transcript_generated": ("transcripts_ready",),
    "therapy_check": ("therapy_condition_check",),
}


async def _resolve_system_actor_id(db, preferred: uuid.UUID | None = None) -> uuid.UUID:
    if preferred:
        return preferred
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row:
        return row
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row if row else uuid.uuid4()


async def _enrich_student_flags_for_term_end(db, instance: ProcessInstance) -> None:
    """Ensure admission_type / has_active_therapist are available for therapy_condition_check rules."""
    student = (
        await db.execute(select(Student).where(Student.id == instance.student_id))
    ).scalars().first()
    if not student:
        return
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    persist_admission_type_on_student(
        student,
        admission_type=ctx.get("admission_type") or StateMachineEngine._as_mapping(student.extra_data).get("admission_type"),
        interview_result=ctx.get("interview_result"),
    )
    # mirror derived flags into instance context for debugging / forms
    extra = StateMachineEngine._as_mapping(student.extra_data)
    ctx = dict(ctx)
    if normalize_admission_type(extra.get("admission_type")):
        ctx.setdefault("admission_type", normalize_admission_type(extra.get("admission_type")))
    ctx["has_active_therapist"] = derive_has_active_therapist(student, extra)
    instance.context_data = ctx
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(instance, "context_data")


async def advance_introductory_term_end(
    db,
    engine: StateMachineEngine,
    instance: ProcessInstance,
    actor_id: uuid.UUID | None = None,
) -> list[str]:
    """از grades_submitted تا therapy_blocked / registration_notification_sent پیش ببر."""
    if instance.process_code != "introductory_term_end":
        return []
    if instance.is_completed or instance.is_cancelled:
        return []

    sys_id = await _resolve_system_actor_id(db, actor_id or instance.started_by)
    await _enrich_student_flags_for_term_end(db, instance)
    await db.flush()

    advanced: list[str] = []
    for _ in range(6):
        inst = await engine.get_process_instance(instance.id)
        if not inst or inst.is_completed or inst.is_cancelled:
            break
        triggers = _ADVANCERS.get(inst.current_state_code)
        if not triggers:
            break
        moved = False
        for trigger in triggers:
            result = await engine.execute_transition(
                instance_id=inst.id,
                trigger_event=trigger,
                actor_id=sys_id,
                actor_role="system",
                payload=None,
            )
            if result.success:
                advanced.append(f"{trigger}->{result.to_state}")
                moved = True
                break
        if not moved:
            break
    return advanced


async def chain_introductory_term_end_after_transition(
    db,
    engine: StateMachineEngine,
    instance: ProcessInstance,
    to_state: str,
    actor_id: uuid.UUID,
) -> None:
    if instance.process_code != "introductory_term_end":
        return
    if to_state not in _ADVANCERS:
        return
    await advance_introductory_term_end(db, engine, instance, actor_id)
