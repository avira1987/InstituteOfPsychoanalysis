"""Process execution API endpoints."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.operational_models import User, ProcessInstance, Student
from app.core.engine import (
    StateMachineEngine, ProcessNotFoundError,
    InstanceNotFoundError, InvalidTransitionError, UnauthorizedError,
)
from app.meta.loader import MetadataLoader
from app.meta.process_forms import get_process_forms

router = APIRouter(prefix="/api/process", tags=["Process"])


# ─── Request/Response Schemas ───────────────────────────────────

class StartProcessRequest(BaseModel):
    process_code: str
    student_id: str
    initial_context: Optional[dict] = None


class TriggerTransitionRequest(BaseModel):
    trigger_event: str
    payload: Optional[dict] = None


class ProcessInstanceResponse(BaseModel):
    instance_id: str
    process_code: str
    current_state: str
    is_completed: bool
    is_cancelled: bool
    context_data: Optional[dict] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class TransitionResultResponse(BaseModel):
    success: bool
    from_state: str
    to_state: Optional[str] = None
    trigger_event: Optional[str] = None
    error: Optional[str] = None
    actions: list[dict] = []
    rule_results: list[dict] = []


# ─── Endpoints ──────────────────────────────────────────────────

@router.get("/definitions")
async def list_processes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active process definitions."""
    loader = MetadataLoader(db)
    processes = await loader.load_all_processes()
    return {"processes": processes}


@router.get("/definitions/{process_code}")
async def get_process_definition(
    process_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a full process definition with states and transitions."""
    loader = MetadataLoader(db)
    process = await loader.load_process(process_code)
    if not process:
        raise HTTPException(status_code=404, detail=f"Process '{process_code}' not found")
    return process


@router.get("/definitions/{process_code}/forms")
async def get_process_forms_for_state(
    process_code: str,
    state: Optional[str] = Query(None, description="Filter forms by used_in_state (e.g. current state)"),
    current_user: User = Depends(get_current_user),
):
    """Get form metadata for a process (for rendering in UI). Optional state filter for current state forms (BUILD_TODO § ز)."""
    forms = get_process_forms(process_code, state_code=state)
    return {"process_code": process_code, "state": state, "forms": forms}


@router.post("/start", response_model=ProcessInstanceResponse)
async def start_process(
    request: StartProcessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new process instance for a student."""
    engine = StateMachineEngine(db)
    try:
        instance = await engine.start_process(
            process_code=request.process_code,
            student_id=uuid.UUID(request.student_id),
            actor_id=current_user.id,
            actor_role=current_user.role,
            initial_context=request.initial_context,
        )
        await db.flush()
        return ProcessInstanceResponse(
            instance_id=str(instance.id),
            process_code=instance.process_code,
            current_state=instance.current_state_code,
            is_completed=instance.is_completed,
            is_cancelled=instance.is_cancelled,
            context_data=instance.context_data,
            started_at=instance.started_at.isoformat() if instance.started_at else None,
        )
    except ProcessNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/trigger", response_model=TransitionResultResponse)
async def trigger_transition(
    instance_id: str,
    request: TriggerTransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute a state transition for a process instance."""
    engine = StateMachineEngine(db)
    try:
        result = await engine.execute_transition(
            instance_id=uuid.UUID(instance_id),
            trigger_event=request.trigger_event,
            actor_id=current_user.id,
            actor_role=current_user.role,
            payload=request.payload,
        )
        return TransitionResultResponse(
            success=result.success,
            from_state=result.from_state,
            to_state=result.to_state,
            trigger_event=result.trigger_event,
            error=result.error,
            actions=result.actions,
            rule_results=[r.to_dict() for r in result.rule_results],
        )
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except UnauthorizedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/status")
async def get_instance_status(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full status of a process instance including history."""
    engine = StateMachineEngine(db)
    try:
        status = await engine.get_instance_status(uuid.UUID(instance_id))
        return status
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{instance_id}/dashboard")
async def get_instance_dashboard(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get instance status + available transitions in one call for dashboard UI (BUILD_TODO § ز)."""
    engine = StateMachineEngine(db)
    try:
        status = await engine.get_instance_status(uuid.UUID(instance_id))
        transitions = await engine.get_available_transitions(
            instance_id=uuid.UUID(instance_id),
            actor_role=current_user.role,
        )
        forms = get_process_forms(
            status.get("process_code", ""),
            state_code=status.get("current_state"),
        )
        return {
            "status": status,
            "transitions": transitions,
            "forms": forms,
        }
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{instance_id}/transitions")
async def get_available_transitions(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available transitions from the current state for the current user."""
    engine = StateMachineEngine(db)
    try:
        transitions = await engine.get_available_transitions(
            instance_id=uuid.UUID(instance_id),
            actor_role=current_user.role,
        )
        return {"transitions": transitions}
    except InstanceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/instances/student/{student_id}")
async def get_student_instances(
    student_id: str,
    is_completed: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all process instances for a student."""
    stmt = select(ProcessInstance).where(
        ProcessInstance.student_id == uuid.UUID(student_id)
    )
    if is_completed is not None:
        stmt = stmt.where(ProcessInstance.is_completed == is_completed)
    stmt = stmt.order_by(ProcessInstance.started_at.desc())

    result = await db.execute(stmt)
    instances = result.scalars().all()

    return {
        "instances": [
            {
                "instance_id": str(i.id),
                "process_code": i.process_code,
                "current_state": i.current_state_code,
                "is_completed": i.is_completed,
                "is_cancelled": i.is_cancelled,
                "started_at": i.started_at.isoformat() if i.started_at else None,
                "completed_at": i.completed_at.isoformat() if i.completed_at else None,
            }
            for i in instances
        ]
    }
