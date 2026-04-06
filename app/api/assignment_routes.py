"""Minimal assignments API for students and staff."""

import uuid
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user, require_role
from app.models.operational_models import User, Student, Assignment, AssignmentSubmission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/assignments", tags=["Assignments"])


class AssignmentCreate(BaseModel):
    student_id: str
    title_fa: str
    description: Optional[str] = None
    due_at: Optional[str] = None


class SubmissionCreate(BaseModel):
    body_text: str


class AssignmentOut(BaseModel):
    id: str
    student_id: str
    title_fa: str
    description: Optional[str]
    due_at: Optional[str]
    created_at: str


async def _get_student_profile(db: AsyncSession, user: User) -> Student:
    r = await db.execute(select(Student).where(Student.user_id == user.id))
    st = r.scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return st


@router.post("", response_model=AssignmentOut)
async def create_assignment(
    body: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff", "therapist")),
):
    due = None
    if body.due_at:
        try:
            due = datetime.fromisoformat(body.due_at.replace("Z", "+00:00"))
        except ValueError:
            due = None
    a = Assignment(
        id=uuid.uuid4(),
        student_id=uuid.UUID(body.student_id),
        title_fa=body.title_fa,
        description=body.description,
        due_at=due,
        created_by=current_user.id,
    )
    db.add(a)
    await db.flush()
    logger.info("assignment_created id=%s student_id=%s", a.id, body.student_id)
    return AssignmentOut(
        id=str(a.id),
        student_id=str(a.student_id),
        title_fa=a.title_fa,
        description=a.description,
        due_at=a.due_at.isoformat() if a.due_at else None,
        created_at=a.created_at.isoformat(),
    )


@router.get("/me", response_model=list[AssignmentOut])
async def list_my_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    st = await _get_student_profile(db, current_user)
    r = await db.execute(
        select(Assignment).where(Assignment.student_id == st.id).order_by(Assignment.created_at.desc())
    )
    items = r.scalars().all()
    return [
        AssignmentOut(
            id=str(x.id),
            student_id=str(x.student_id),
            title_fa=x.title_fa,
            description=x.description,
            due_at=x.due_at.isoformat() if x.due_at else None,
            created_at=x.created_at.isoformat(),
        )
        for x in items
    ]


@router.get("/{assignment_id}/submission")
async def get_submission(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    st = await _get_student_profile(db, current_user)
    aid = uuid.UUID(assignment_id)
    r = await db.execute(
        select(Assignment).where(Assignment.id == aid, Assignment.student_id == st.id)
    )
    a = r.scalars().first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    r2 = await db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == aid,
            AssignmentSubmission.student_id == st.id,
        )
    )
    sub = r2.scalars().first()
    return {
        "assignment": {
            "id": str(a.id),
            "title_fa": a.title_fa,
            "description": a.description,
            "due_at": a.due_at.isoformat() if a.due_at else None,
        },
        "submission": (
            {
                "body_text": sub.body_text,
                "submitted_at": sub.submitted_at.isoformat(),
                "score": sub.score,
                "feedback_fa": sub.feedback_fa,
            }
            if sub
            else None
        ),
    }


@router.post("/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: str,
    body: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    st = await _get_student_profile(db, current_user)
    aid = uuid.UUID(assignment_id)
    r = await db.execute(
        select(Assignment).where(Assignment.id == aid, Assignment.student_id == st.id)
    )
    a = r.scalars().first()
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    r2 = await db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == aid,
            AssignmentSubmission.student_id == st.id,
        )
    )
    existing = r2.scalars().first()
    if existing:
        existing.body_text = body.body_text
        existing.submitted_at = datetime.now(timezone.utc)
    else:
        db.add(
            AssignmentSubmission(
                id=uuid.uuid4(),
                assignment_id=aid,
                student_id=st.id,
                body_text=body.body_text,
                submitted_at=datetime.now(timezone.utc),
            )
        )
    await db.flush()
    return {"success": True}
