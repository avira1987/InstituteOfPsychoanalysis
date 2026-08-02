"""Admin API for flow-through test seeding."""

from __future__ import annotations

import os
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_role
from app.database import get_db
from app.flow_through.state_seeder import seed_instance_at_state
from app.models.operational_models import User

router = APIRouter(prefix="/api/admin/flow-through", tags=["flow-through"])


class FlowThroughSeedRequest(BaseModel):
    process_code: str
    target_state: str
    student_code: Optional[str] = None
    extra_ctx: dict[str, Any] = Field(default_factory=dict)
    institute_student: bool = False


class FlowThroughSeedResponse(BaseModel):
    instance_id: str
    student_id: str
    student_code: str
    process_code: str
    target_state: str
    current_state: str
    mode: str
    walk_steps: int
    blocked_at: Optional[str] = None
    portal_logins: dict[str, str]


@router.post("/seed", response_model=FlowThroughSeedResponse)
async def flow_through_seed(
    body: FlowThroughSeedRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Seed a process instance at target state for flow-through E2E/API tests."""
    if os.getenv("FLOW_THROUGH_SEED_ENABLED", "1") not in ("1", "true", "yes"):
        raise HTTPException(status_code=403, detail="Flow-through seeding disabled")

    try:
        result = await seed_instance_at_state(
            db,
            body.process_code.strip(),
            body.target_state.strip(),
            student_code=body.student_code,
            extra_ctx=body.extra_ctx or None,
            institute_student=body.institute_student,
        )
        await db.commit()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e

    return FlowThroughSeedResponse(
        instance_id=str(result.instance_id),
        student_id=str(result.student_id),
        student_code=result.student_code,
        process_code=result.process_code,
        target_state=result.target_state,
        current_state=result.current_state,
        mode=result.mode,
        walk_steps=result.walk_steps,
        blocked_at=result.blocked_at,
        portal_logins={
            "admin": "admin / admin123",
            "demo_roles": "{role}1 / demo123",
            "note": "Use POST /api/auth/login for API tests; login-json + challenge for browser",
        },
    )
