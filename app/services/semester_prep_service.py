"""Semester preparation process — institute anchor, start, status, pre-fill."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import ProcessInstance
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.utils.shamsi_calendar_utils import farvardin_20_end_tehran, parse_iso_date, shamsi_parts

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

PREP_PROCESS_CODES = frozenset(
    {
        "fall_semester_preparation",
        "winter_semester_preparation",
    }
)

FALL_PREP = "fall_semester_preparation"
WINTER_PREP = "winter_semester_preparation"


def _ctx(instance: ProcessInstance) -> dict[str, Any]:
    return StateMachineEngine._as_mapping(instance.context_data)


def _set_ctx(instance: ProcessInstance, ctx: dict[str, Any]) -> None:
    instance.context_data = ctx
    flag_modified(instance, "context_data")


def _calendar_sla_context_for_fall_start() -> dict[str, Any]:
    """Absolute deadline for calendar_entry (Farvardin 20 end, Tehran)."""
    deadline = farvardin_20_end_tehran()
    return {
        "calendar_sla_deadline_at": deadline.isoformat(),
        "prep_term_label_fa": f"ترم پاییز {shamsi_parts()[0]}",
    }


async def get_active_prep_instance(
    db: AsyncSession,
    process_code: str,
    *,
    student_id: uuid.UUID | None = None,
) -> ProcessInstance | None:
    if process_code not in PREP_PROCESS_CODES:
        return None
    if student_id is None:
        anchor = await ensure_institute_operational_student(db)
        student_id = anchor.id
    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.process_code == process_code,
            ProcessInstance.student_id == student_id,
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
        )
        .order_by(desc(ProcessInstance.started_at))
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def get_completed_fall_prep_instance(
    db: AsyncSession,
    *,
    student_id: uuid.UUID | None = None,
) -> ProcessInstance | None:
    if student_id is None:
        anchor = await ensure_institute_operational_student(db)
        student_id = anchor.id
    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.process_code == FALL_PREP,
            ProcessInstance.student_id == student_id,
            ProcessInstance.is_completed.is_(True),
            ProcessInstance.is_cancelled.is_(False),
            ProcessInstance.current_state_code == "published",
        )
        .order_by(desc(ProcessInstance.completed_at))
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def get_or_start_prep_instance(
    db: AsyncSession,
    process_code: str,
    *,
    actor_id: uuid.UUID | None = None,
    actor_role: str = "system",
) -> tuple[ProcessInstance, bool]:
    """Return (instance, created). Idempotent for active instance."""
    if process_code not in PREP_PROCESS_CODES:
        raise ValueError(f"unsupported process_code: {process_code}")

    anchor = await ensure_institute_operational_student(db)
    existing = await get_active_prep_instance(db, process_code, student_id=anchor.id)
    if existing is not None:
        return existing, False

    if process_code == WINTER_PREP:
        fall_done = await get_completed_fall_prep_instance(db, student_id=anchor.id)
        if fall_done is None:
            raise ValueError("fall_semester_preparation must reach published before winter prep")

    initial_context: dict[str, Any] = {}
    if process_code == FALL_PREP:
        initial_context.update(_calendar_sla_context_for_fall_start())

    engine = StateMachineEngine(db)
    instance = await engine.start_process(
        process_code=process_code,
        student_id=anchor.id,
        actor_id=actor_id or SYSTEM_ACTOR_ID,
        actor_role=actor_role,
        initial_context=initial_context,
    )
    return instance, True


async def ensure_fall_prep_started(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    actor_role: str = "system",
) -> dict[str, Any]:
    inst, created = await get_or_start_prep_instance(
        db, FALL_PREP, actor_id=actor_id, actor_role=actor_role
    )
    return {
        "process_code": FALL_PREP,
        "instance_id": str(inst.id),
        "current_state": inst.current_state_code,
        "created": created,
    }


async def ensure_winter_prep_started(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None = None,
    actor_role: str = "system",
) -> dict[str, Any]:
    inst, created = await get_or_start_prep_instance(
        db, WINTER_PREP, actor_id=actor_id, actor_role=actor_role
    )
    return {
        "process_code": WINTER_PREP,
        "instance_id": str(inst.id),
        "current_state": inst.current_state_code,
        "created": created,
    }


async def should_auto_start_winter(db: AsyncSession, today=None) -> bool:
    """True when fall is published, no active winter prep, and within auto-start window."""
    from datetime import timedelta

    from app.config import get_settings
    from app.utils.shamsi_calendar_utils import tehran_today

    fall = await get_completed_fall_prep_instance(db)
    if fall is None:
        return False
    if await get_active_prep_instance(db, WINTER_PREP) is not None:
        return False
    ctx = _ctx(fall)
    winter_start = parse_iso_date(ctx.get("winter_start_date"))
    if winter_start is None:
        return False
    ref = today or tehran_today()
    days_before = int(get_settings().WINTER_PREP_AUTO_START_DAYS_BEFORE or 30)
    window_start = winter_start - timedelta(days=days_before)
    return window_start <= ref <= winter_start


async def load_fall_prep_context_field(
    db: AsyncSession,
    field_name: str,
) -> Any:
    """Read a field from fall prep instance context (active first, then latest completed)."""
    anchor = await ensure_institute_operational_student(db)
    active = await get_active_prep_instance(db, FALL_PREP, student_id=anchor.id)
    if active is not None:
        val = _ctx(active).get(field_name)
        if val is not None:
            return val
    fall = await get_completed_fall_prep_instance(db, student_id=anchor.id)
    if fall is not None:
        return _ctx(fall).get(field_name)
    return None


async def apply_pre_filled_fields(
    db: AsyncSession,
    process_code: str,
    state_code: str,
    context_data: dict[str, Any],
) -> dict[str, Any]:
    """Merge pre_filled_from field values into context for operator forms."""
    from app.meta.process_forms import get_process_forms

    forms = get_process_forms(process_code, state_code=state_code)
    out = dict(context_data or {})
    for form in forms:
        for field in form.get("fields") or []:
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            pref = field.get("pre_filled_from")
            if not name or not pref or out.get(name) not in (None, "", []):
                continue
            value = await _resolve_pre_filled(db, str(pref))
            if value is not None:
                out[name] = value
    return out


async def _resolve_pre_filled(db: AsyncSession, spec: str) -> Any:
    """spec: 'fall_semester_preparation.courses' or 'fall_semester_preparation.course_list_form'."""
    parts = spec.split(".", 1)
    if len(parts) != 2:
        return None
    proc, tail = parts[0].strip(), parts[1].strip()
    field = tail
    if tail.endswith("_form"):
        field = "courses"
    if proc == FALL_PREP:
        return await load_fall_prep_context_field(db, field)
    return None


async def build_prep_status(db: AsyncSession) -> dict[str, Any]:
    """Status payload for admin API."""
    anchor = await ensure_institute_operational_student(db)
    out: dict[str, Any] = {
        "anchor_student_code": anchor.student_code,
        "anchor_student_id": str(anchor.id),
        "processes": {},
    }
    engine = StateMachineEngine(db)
    for code in (FALL_PREP, WINTER_PREP):
        inst = await get_active_prep_instance(db, code, student_id=anchor.id)
        entry: dict[str, Any] = {
            "active": inst is not None,
            "instance_id": str(inst.id) if inst else None,
            "current_state": inst.current_state_code if inst else None,
            "is_completed": bool(inst.is_completed) if inst else False,
        }
        if inst is not None:
            entry["student_id"] = str(anchor.id)
            proc_def = await engine.get_process_definition(code)
            sd_stmt = select(StateDefinition).where(
                StateDefinition.process_id == proc_def.id,
                StateDefinition.code == inst.current_state_code,
            )
            sd = (await db.execute(sd_stmt)).scalars().first()
            entry["state_name_fa"] = sd.name_fa if sd else inst.current_state_code
            entry["assigned_role"] = sd.assigned_role if sd else None
            if sd and sd.sla_hours:
                elapsed = (datetime.now(timezone.utc) - inst.last_transition_at).total_seconds() / 3600
                entry["sla_hours"] = sd.sla_hours
                entry["sla_overdue"] = elapsed > sd.sla_hours
            ctx = _ctx(inst)
            cal_deadline = ctx.get("calendar_sla_deadline_at")
            if inst.current_state_code == "calendar_entry" and cal_deadline:
                try:
                    dl = datetime.fromisoformat(str(cal_deadline).replace("Z", "+00:00"))
                    entry["calendar_sla_deadline_at"] = dl.isoformat()
                    entry["sla_overdue"] = datetime.now(timezone.utc) > dl
                except (TypeError, ValueError):
                    pass
        else:
            if code == FALL_PREP:
                last = await get_completed_fall_prep_instance(db, student_id=anchor.id)
                entry["last_completed_at"] = (
                    last.completed_at.isoformat() if last and last.completed_at else None
                )
        out["processes"][code] = entry
    return out
