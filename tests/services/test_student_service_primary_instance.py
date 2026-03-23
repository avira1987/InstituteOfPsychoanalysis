import uuid
import pytest

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, User
from app.services.student_service import StudentService


@pytest.mark.asyncio
async def test_set_primary_instance_for_student(db_session: AsyncSession):
    """StudentService.set_primary_instance_for_student should store instance id in extra_data."""
    user = User(
        id=uuid.uuid4(),
        username="student_primary_test",
        hashed_password="x",
        role="student",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code="STU-PRIMARY-1",
        course_type="introductory",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=1,
    )
    db_session.add_all([user, student])
    await db_session.commit()

    service = StudentService(db_session)
    instance_id = uuid.uuid4()

    await service.set_primary_instance_for_student(student, instance_id)
    await db_session.commit()
    await db_session.refresh(student)

    assert isinstance(student.extra_data, dict)
    assert student.extra_data.get("primary_instance_id") == str(instance_id)

