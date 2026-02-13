"""Admin CRUD API endpoints for managing processes, states, transitions, and rules."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user, require_role
from app.models.operational_models import User
from app.models.meta_models import ProcessDefinition, StateDefinition, TransitionDefinition, RuleDefinition
from app.models.audit_models import AuditLog
from app.core.audit import AuditLogger

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ─── Process CRUD Schemas ──────────────────────────────────────

class ProcessCreate(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    initial_state_code: str
    config: Optional[dict] = None


class ProcessUpdate(BaseModel):
    name_fa: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    initial_state_code: Optional[str] = None
    is_active: Optional[bool] = None
    config: Optional[dict] = None


class ProcessResponse(BaseModel):
    id: str
    code: str
    name_fa: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    version: int
    is_active: bool
    initial_state_code: str
    config: Optional[dict] = None


# ─── State CRUD Schemas ────────────────────────────────────────

class StateCreate(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    state_type: str = "intermediate"
    assigned_role: Optional[str] = None
    sla_hours: Optional[int] = None
    on_sla_breach_event: Optional[str] = None
    metadata_: Optional[dict] = Field(None, alias="metadata")

    model_config = {"populate_by_name": True}


class StateUpdate(BaseModel):
    name_fa: Optional[str] = None
    name_en: Optional[str] = None
    state_type: Optional[str] = None
    assigned_role: Optional[str] = None
    sla_hours: Optional[int] = None
    on_sla_breach_event: Optional[str] = None


class StateResponse(BaseModel):
    id: str
    process_id: str
    code: str
    name_fa: str
    state_type: str
    assigned_role: Optional[str] = None
    sla_hours: Optional[int] = None


# ─── Transition CRUD Schemas ───────────────────────────────────

class TransitionCreate(BaseModel):
    from_state_code: str
    to_state_code: str
    trigger_event: str
    condition_rules: Optional[list[str]] = None
    required_role: Optional[str] = None
    actions: Optional[list[dict]] = None
    priority: int = 0
    description_fa: Optional[str] = None


class TransitionUpdate(BaseModel):
    from_state_code: Optional[str] = None
    to_state_code: Optional[str] = None
    trigger_event: Optional[str] = None
    condition_rules: Optional[list[str]] = None
    required_role: Optional[str] = None
    actions: Optional[list[dict]] = None
    priority: Optional[int] = None
    description_fa: Optional[str] = None


class TransitionResponse(BaseModel):
    id: str
    process_id: str
    from_state_code: str
    to_state_code: str
    trigger_event: str
    condition_rules: Optional[list[str]] = None
    required_role: Optional[str] = None
    actions: Optional[list[dict]] = None
    priority: int
    description_fa: Optional[str] = None


# ─── Rule CRUD Schemas ─────────────────────────────────────────

class RuleCreate(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    rule_type: str = "condition"
    expression: dict
    parameters: Optional[dict] = None
    error_message_fa: Optional[str] = None


class RuleUpdate(BaseModel):
    name_fa: Optional[str] = None
    name_en: Optional[str] = None
    rule_type: Optional[str] = None
    expression: Optional[dict] = None
    parameters: Optional[dict] = None
    error_message_fa: Optional[str] = None
    is_active: Optional[bool] = None


class RuleResponse(BaseModel):
    id: str
    code: str
    name_fa: str
    rule_type: str
    expression: dict
    parameters: Optional[dict] = None
    error_message_fa: Optional[str] = None
    is_active: bool
    version: int


# ─── Process CRUD Endpoints ────────────────────────────────────

@router.post("/processes", response_model=ProcessResponse)
async def create_process(
    data: ProcessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Create a new process definition."""
    process = ProcessDefinition(
        id=uuid.uuid4(),
        code=data.code,
        name_fa=data.name_fa,
        name_en=data.name_en,
        description=data.description,
        initial_state_code=data.initial_state_code,
        config=data.config,
        updated_by=current_user.id,
    )
    db.add(process)
    await db.flush()
    return _process_response(process)


@router.get("/processes", response_model=list[ProcessResponse])
async def list_processes(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all process definitions."""
    stmt = select(ProcessDefinition)
    if is_active is not None:
        stmt = stmt.where(ProcessDefinition.is_active == is_active)
    stmt = stmt.order_by(ProcessDefinition.code)
    result = await db.execute(stmt)
    processes = result.scalars().all()
    return [_process_response(p) for p in processes]


@router.get("/processes/{process_id}", response_model=ProcessResponse)
async def get_process(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Get a process definition by ID."""
    process = await _get_process_or_404(db, process_id)
    return _process_response(process)


@router.patch("/processes/{process_id}", response_model=ProcessResponse)
async def update_process(
    process_id: str,
    data: ProcessUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a process definition."""
    process = await _get_process_or_404(db, process_id)
    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(process, key, value)
    process.version += 1
    process.updated_by = current_user.id

    # Audit
    audit = AuditLogger(db)
    await audit.log(
        action_type="process_updated",
        actor_id=current_user.id,
        actor_role=current_user.role,
        process_code=process.code,
        details={"changes": update_dict},
    )
    await db.flush()
    return _process_response(process)


@router.delete("/processes/{process_id}")
async def delete_process(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete (deactivate) a process definition."""
    process = await _get_process_or_404(db, process_id)
    process.is_active = False
    await db.flush()
    return {"message": f"Process '{process.code}' deactivated"}


# ─── State CRUD Endpoints ──────────────────────────────────────

@router.post("/processes/{process_id}/states", response_model=StateResponse)
async def create_state(
    process_id: str,
    data: StateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Add a state to a process."""
    await _get_process_or_404(db, process_id)
    state = StateDefinition(
        id=uuid.uuid4(),
        process_id=uuid.UUID(process_id),
        code=data.code,
        name_fa=data.name_fa,
        name_en=data.name_en,
        state_type=data.state_type,
        assigned_role=data.assigned_role,
        sla_hours=data.sla_hours,
        on_sla_breach_event=data.on_sla_breach_event,
        metadata_=data.metadata_,
    )
    db.add(state)
    await db.flush()
    return _state_response(state)


@router.get("/processes/{process_id}/states", response_model=list[StateResponse])
async def list_states(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all states in a process."""
    stmt = select(StateDefinition).where(
        StateDefinition.process_id == uuid.UUID(process_id)
    )
    result = await db.execute(stmt)
    states = result.scalars().all()
    return [_state_response(s) for s in states]


@router.patch("/states/{state_id}", response_model=StateResponse)
async def update_state(
    state_id: str,
    data: StateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a state definition."""
    stmt = select(StateDefinition).where(StateDefinition.id == uuid.UUID(state_id))
    result = await db.execute(stmt)
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(state, key, value)
    await db.flush()
    return _state_response(state)


@router.delete("/states/{state_id}")
async def delete_state(
    state_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete a state definition."""
    stmt = select(StateDefinition).where(StateDefinition.id == uuid.UUID(state_id))
    result = await db.execute(stmt)
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    await db.delete(state)
    await db.flush()
    return {"message": "State deleted"}


# ─── Transition CRUD Endpoints ─────────────────────────────────

@router.post("/processes/{process_id}/transitions", response_model=TransitionResponse)
async def create_transition(
    process_id: str,
    data: TransitionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Add a transition to a process."""
    await _get_process_or_404(db, process_id)
    transition = TransitionDefinition(
        id=uuid.uuid4(),
        process_id=uuid.UUID(process_id),
        from_state_code=data.from_state_code,
        to_state_code=data.to_state_code,
        trigger_event=data.trigger_event,
        condition_rules=data.condition_rules,
        required_role=data.required_role,
        actions=data.actions,
        priority=data.priority,
        description_fa=data.description_fa,
    )
    db.add(transition)
    await db.flush()
    return _transition_response(transition)


@router.get("/processes/{process_id}/transitions", response_model=list[TransitionResponse])
async def list_transitions(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all transitions in a process."""
    stmt = select(TransitionDefinition).where(
        TransitionDefinition.process_id == uuid.UUID(process_id)
    )
    result = await db.execute(stmt)
    transitions = result.scalars().all()
    return [_transition_response(t) for t in transitions]


@router.patch("/transitions/{transition_id}", response_model=TransitionResponse)
async def update_transition(
    transition_id: str,
    data: TransitionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a transition definition."""
    stmt = select(TransitionDefinition).where(TransitionDefinition.id == uuid.UUID(transition_id))
    result = await db.execute(stmt)
    transition = result.scalars().first()
    if not transition:
        raise HTTPException(status_code=404, detail="Transition not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(transition, key, value)
    await db.flush()
    return _transition_response(transition)


@router.delete("/transitions/{transition_id}")
async def delete_transition(
    transition_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete a transition definition."""
    stmt = select(TransitionDefinition).where(TransitionDefinition.id == uuid.UUID(transition_id))
    result = await db.execute(stmt)
    transition = result.scalars().first()
    if not transition:
        raise HTTPException(status_code=404, detail="Transition not found")
    await db.delete(transition)
    await db.flush()
    return {"message": "Transition deleted"}


# ─── Rule CRUD Endpoints ───────────────────────────────────────

@router.post("/rules", response_model=RuleResponse)
async def create_rule(
    data: RuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Create a new rule definition."""
    rule = RuleDefinition(
        id=uuid.uuid4(),
        code=data.code,
        name_fa=data.name_fa,
        name_en=data.name_en,
        rule_type=data.rule_type,
        expression=data.expression,
        parameters=data.parameters,
        error_message_fa=data.error_message_fa,
    )
    db.add(rule)

    audit = AuditLogger(db)
    await audit.log_rule_change(
        rule_code=data.code,
        change_type="created",
        actor_id=current_user.id,
        actor_role=current_user.role,
        new_value=data.model_dump(),
    )
    await db.flush()
    return _rule_response(rule)


@router.get("/rules", response_model=list[RuleResponse])
async def list_rules(
    rule_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all rule definitions."""
    stmt = select(RuleDefinition)
    if rule_type:
        stmt = stmt.where(RuleDefinition.rule_type == rule_type)
    if is_active is not None:
        stmt = stmt.where(RuleDefinition.is_active == is_active)
    stmt = stmt.order_by(RuleDefinition.code)
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return [_rule_response(r) for r in rules]


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Get a rule definition by ID."""
    stmt = select(RuleDefinition).where(RuleDefinition.id == uuid.UUID(rule_id))
    result = await db.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _rule_response(rule)


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    data: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a rule definition."""
    stmt = select(RuleDefinition).where(RuleDefinition.id == uuid.UUID(rule_id))
    result = await db.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    old_value = _rule_response(rule).model_dump() if hasattr(_rule_response(rule), 'model_dump') else {}
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    rule.version += 1

    audit = AuditLogger(db)
    await audit.log_rule_change(
        rule_code=rule.code,
        change_type="updated",
        actor_id=current_user.id,
        actor_role=current_user.role,
        old_value=old_value,
        new_value=data.model_dump(exclude_unset=True),
    )
    await db.flush()
    return _rule_response(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Deactivate a rule definition."""
    stmt = select(RuleDefinition).where(RuleDefinition.id == uuid.UUID(rule_id))
    result = await db.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = False
    await db.flush()
    return {"message": f"Rule '{rule.code}' deactivated"}


# ─── Audit Log Endpoints ───────────────────────────────────────

@router.get("/audit-logs")
async def list_audit_logs(
    action_type: Optional[str] = Query(None),
    process_code: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """List audit logs with filters."""
    stmt = select(AuditLog)
    if action_type:
        stmt = stmt.where(AuditLog.action_type == action_type)
    if process_code:
        stmt = stmt.where(AuditLog.process_code == process_code)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == uuid.UUID(actor_id))
    stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    logs = result.scalars().all()

    # Count total
    count_stmt = select(func.count(AuditLog.id))
    if action_type:
        count_stmt = count_stmt.where(AuditLog.action_type == action_type)
    if process_code:
        count_stmt = count_stmt.where(AuditLog.process_code == process_code)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": [
            {
                "id": str(log.id),
                "action_type": log.action_type,
                "process_code": log.process_code,
                "from_state": log.from_state,
                "to_state": log.to_state,
                "trigger_event": log.trigger_event,
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "actor_role": log.actor_role,
                "actor_name": log.actor_name,
                "details": log.details,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in logs
        ],
    }


# ─── Dashboard Stats ───────────────────────────────────────────

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Get dashboard statistics."""
    from app.models.operational_models import ProcessInstance, Student

    process_count = await db.execute(select(func.count(ProcessDefinition.id)).where(ProcessDefinition.is_active == True))
    rule_count = await db.execute(select(func.count(RuleDefinition.id)).where(RuleDefinition.is_active == True))
    student_count = await db.execute(select(func.count(Student.id)))
    active_instances = await db.execute(select(func.count(ProcessInstance.id)).where(ProcessInstance.is_completed == False, ProcessInstance.is_cancelled == False))

    return {
        "active_processes": process_count.scalar(),
        "active_rules": rule_count.scalar(),
        "total_students": student_count.scalar(),
        "active_instances": active_instances.scalar(),
    }


# ─── User Management Endpoints ──────────────────────────────────

@router.get("/users")
async def list_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """List all users."""
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    stmt = stmt.order_by(User.created_at.desc())
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "full_name_fa": u.full_name_fa,
            "full_name_en": u.full_name_en,
            "role": u.role,
            "phone": u.phone,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a user."""
    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed_fields = {"full_name_fa", "full_name_en", "role", "phone", "email", "is_active"}
    for key, value in data.items():
        if key in allowed_fields:
            setattr(user, key, value)
    await db.flush()
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name_fa": user.full_name_fa,
        "full_name_en": user.full_name_en,
        "role": user.role,
        "phone": user.phone,
        "is_active": user.is_active,
    }


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Deactivate a user."""
    if str(current_user.id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.flush()
    return {"message": f"User '{user.username}' deactivated"}


# ─── Helper Functions ───────────────────────────────────────────

async def _get_process_or_404(db: AsyncSession, process_id: str) -> ProcessDefinition:
    stmt = select(ProcessDefinition).where(ProcessDefinition.id == uuid.UUID(process_id))
    result = await db.execute(stmt)
    process = result.scalars().first()
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


def _process_response(p: ProcessDefinition) -> ProcessResponse:
    return ProcessResponse(
        id=str(p.id), code=p.code, name_fa=p.name_fa, name_en=p.name_en,
        description=p.description, version=p.version, is_active=p.is_active,
        initial_state_code=p.initial_state_code, config=p.config,
    )


def _state_response(s: StateDefinition) -> StateResponse:
    return StateResponse(
        id=str(s.id), process_id=str(s.process_id), code=s.code,
        name_fa=s.name_fa, state_type=s.state_type, assigned_role=s.assigned_role,
        sla_hours=s.sla_hours,
    )


def _transition_response(t: TransitionDefinition) -> TransitionResponse:
    return TransitionResponse(
        id=str(t.id), process_id=str(t.process_id),
        from_state_code=t.from_state_code, to_state_code=t.to_state_code,
        trigger_event=t.trigger_event, condition_rules=t.condition_rules,
        required_role=t.required_role, actions=t.actions, priority=t.priority,
        description_fa=t.description_fa,
    )


def _rule_response(r: RuleDefinition) -> RuleResponse:
    return RuleResponse(
        id=str(r.id), code=r.code, name_fa=r.name_fa, rule_type=r.rule_type,
        expression=r.expression, parameters=r.parameters,
        error_message_fa=r.error_message_fa, is_active=r.is_active, version=r.version,
    )
