"""Student-facing API endpoints."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user, require_role
from app.models.operational_models import User, Student

router = APIRouter(prefix="/api/students", tags=["Students"])


# ─── Schemas ────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    user_id: str
    student_code: str
    course_type: str  # "introductory" | "comprehensive"
    is_intern: bool = False
    term_count: int = 1
    current_term: int = 1
    weekly_sessions: int = 1


class StudentUpdate(BaseModel):
    course_type: Optional[str] = None
    is_intern: Optional[bool] = None
    term_count: Optional[int] = None
    current_term: Optional[int] = None
    weekly_sessions: Optional[int] = None
    therapy_started: Optional[bool] = None


class StudentResponse(BaseModel):
    id: str
    user_id: str
    student_code: str
    course_type: str
    is_intern: bool
    term_count: int
    current_term: int
    therapy_started: bool
    weekly_sessions: int

    model_config = {"from_attributes": True}


# ─── Endpoints ──────────────────────────────────────────────────

@router.post("/", response_model=StudentResponse)
async def create_student(
    student_data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Create a new student profile."""
    student = Student(
        id=uuid.uuid4(),
        user_id=uuid.UUID(student_data.user_id),
        student_code=student_data.student_code,
        course_type=student_data.course_type,
        is_intern=student_data.is_intern,
        term_count=student_data.term_count,
        current_term=student_data.current_term,
        weekly_sessions=student_data.weekly_sessions,
    )
    db.add(student)
    await db.flush()

    return StudentResponse(
        id=str(student.id),
        user_id=str(student.user_id),
        student_code=student.student_code,
        course_type=student.course_type,
        is_intern=student.is_intern,
        term_count=student.term_count,
        current_term=student.current_term,
        therapy_started=student.therapy_started,
        weekly_sessions=student.weekly_sessions,
    )


@router.get("/", response_model=list[StudentResponse])
async def list_students(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all students."""
    stmt = select(Student)
    result = await db.execute(stmt)
    students = result.scalars().all()
    return [
        StudentResponse(
            id=str(s.id),
            user_id=str(s.user_id),
            student_code=s.student_code,
            course_type=s.course_type,
            is_intern=s.is_intern,
            term_count=s.term_count,
            current_term=s.current_term,
            therapy_started=s.therapy_started,
            weekly_sessions=s.weekly_sessions,
        )
        for s in students
    ]


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a student profile."""
    stmt = select(Student).where(Student.id == uuid.UUID(student_id))
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    return StudentResponse(
        id=str(student.id),
        user_id=str(student.user_id),
        student_code=student.student_code,
        course_type=student.course_type,
        is_intern=student.is_intern,
        term_count=student.term_count,
        current_term=student.current_term,
        therapy_started=student.therapy_started,
        weekly_sessions=student.weekly_sessions,
    )


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: str,
    update_data: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Update a student profile."""
    stmt = select(Student).where(Student.id == uuid.UUID(student_id))
    result = await db.execute(stmt)
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(student, key, value)

    await db.flush()

    return StudentResponse(
        id=str(student.id),
        user_id=str(student.user_id),
        student_code=student.student_code,
        course_type=student.course_type,
        is_intern=student.is_intern,
        term_count=student.term_count,
        current_term=student.current_term,
        therapy_started=student.therapy_started,
        weekly_sessions=student.weekly_sessions,
    )
