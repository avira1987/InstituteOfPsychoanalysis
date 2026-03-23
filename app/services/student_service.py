"""Student Service - Business logic for student operations."""

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, User
from app.services.process_service import ProcessService


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

    async def set_primary_instance_for_student(self, student: Student, instance_id: uuid.UUID) -> None:
        """
        Store the primary process instance for a student.

        To avoid schema migrations, this is stored in student.extra_data["primary_instance_id"].
        """
        extra = dict(student.extra_data or {})
        extra["primary_instance_id"] = str(instance_id)
        student.extra_data = extra

    async def start_initial_process_for_student(self, student: Student, actor: User):
        """
        Start the initial registration process for a newly registered student and
        mark it as the primary instance in the student's extra_data.

        The process_code is chosen based on course_type:
        - introductory -> introductory_course_registration
        - comprehensive -> comprehensive_course_registration
        """
        if not student or not actor:
            return None

        if student.course_type == "introductory":
            process_code = "introductory_course_registration"
        else:
            process_code = "comprehensive_course_registration"

        service = ProcessService(self.db)
        instance = await service.start_process_for_student(
            process_code=process_code,
            student_id=student.id,
            actor_id=actor.id,
            actor_role=actor.role or "student",
            initial_context={"source": "auto_start_on_registration"},
        )
        await self.set_primary_instance_for_student(student, instance.id)
        return instance

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
