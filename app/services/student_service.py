"""Student Service - Business logic for student operations."""

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, User


class StudentService:
    """Service for student-related operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_student_by_code(self, student_code: str) -> Optional[Student]:
        """Get a student by their student code."""
        stmt = select(Student).where(Student.student_code == student_code)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_student_by_user_id(self, user_id: uuid.UUID) -> Optional[Student]:
        """Get a student by their user ID."""
        stmt = select(Student).where(Student.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def update_therapy_status(self, student_id: uuid.UUID, started: bool):
        """Update the therapy_started status of a student."""
        stmt = select(Student).where(Student.id == student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if student:
            student.therapy_started = started

    async def update_intern_status(self, student_id: uuid.UUID, is_intern: bool):
        """Update the intern status of a student."""
        stmt = select(Student).where(Student.id == student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if student:
            student.is_intern = is_intern

    async def get_students_by_course_type(self, course_type: str) -> list[Student]:
        """Get all students of a specific course type."""
        stmt = select(Student).where(Student.course_type == course_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
