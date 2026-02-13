"""Shared test fixtures and configuration."""

import uuid
import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.meta_models import ProcessDefinition, StateDefinition, TransitionDefinition, RuleDefinition
from app.models.operational_models import User, Student, ProcessInstance
from app.models.audit_models import AuditLog


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create a test database session."""
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession):
    """Create a sample admin user."""
    from app.api.auth import get_password_hash
    user = User(
        id=uuid.uuid4(),
        username="admin_test",
        email="admin@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="مدیر تست",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def sample_student_user(db_session: AsyncSession):
    """Create a sample student user."""
    from app.api.auth import get_password_hash
    user = User(
        id=uuid.uuid4(),
        username="student_test",
        email="student@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="دانشجوی تست",
        role="student",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def sample_student(db_session: AsyncSession, sample_student_user: User):
    """Create a sample student profile."""
    student = Student(
        id=uuid.uuid4(),
        user_id=sample_student_user.id,
        student_code="STU-001",
        course_type="comprehensive",
        is_intern=False,
        term_count=3,
        current_term=3,
        weekly_sessions=2,
    )
    db_session.add(student)
    await db_session.commit()
    return student


@pytest_asyncio.fixture
async def sample_process(db_session: AsyncSession):
    """Create a sample process definition with states and transitions."""
    process_id = uuid.uuid4()

    process = ProcessDefinition(
        id=process_id,
        code="test_process",
        name_fa="فرایند تست",
        initial_state_code="initial",
        version=1,
        is_active=True,
    )
    db_session.add(process)

    # States
    states = [
        StateDefinition(id=uuid.uuid4(), process_id=process_id, code="initial",
                        name_fa="شروع", state_type="initial", assigned_role="student"),
        StateDefinition(id=uuid.uuid4(), process_id=process_id, code="review",
                        name_fa="بررسی", state_type="intermediate", assigned_role="admin",
                        sla_hours=48),
        StateDefinition(id=uuid.uuid4(), process_id=process_id, code="approved",
                        name_fa="تایید", state_type="terminal", assigned_role="system"),
        StateDefinition(id=uuid.uuid4(), process_id=process_id, code="rejected",
                        name_fa="رد", state_type="terminal", assigned_role="system"),
    ]
    for s in states:
        db_session.add(s)

    # Transitions
    transitions = [
        TransitionDefinition(
            id=uuid.uuid4(), process_id=process_id,
            from_state_code="initial", to_state_code="review",
            trigger_event="submitted", required_role="student",
        ),
        TransitionDefinition(
            id=uuid.uuid4(), process_id=process_id,
            from_state_code="review", to_state_code="approved",
            trigger_event="approve", required_role="admin",
            condition_rules=["is_not_intern"],
        ),
        TransitionDefinition(
            id=uuid.uuid4(), process_id=process_id,
            from_state_code="review", to_state_code="rejected",
            trigger_event="reject", required_role="admin",
        ),
    ]
    for t in transitions:
        db_session.add(t)

    await db_session.commit()
    return process


@pytest_asyncio.fixture
async def sample_rules(db_session: AsyncSession):
    """Create sample rule definitions."""
    rules = [
        RuleDefinition(
            id=uuid.uuid4(),
            code="is_intern",
            name_fa="آیا انترن است",
            rule_type="condition",
            expression={"field": "student.is_intern", "operator": "eq", "value": True},
        ),
        RuleDefinition(
            id=uuid.uuid4(),
            code="is_not_intern",
            name_fa="آیا انترن نیست",
            rule_type="condition",
            expression={"field": "student.is_intern", "operator": "eq", "value": False},
        ),
        RuleDefinition(
            id=uuid.uuid4(),
            code="min_term",
            name_fa="حداقل ترم",
            rule_type="validation",
            expression={"field": "student.term_count", "operator": "gte", "value": 1},
            error_message_fa="حداقل یک ترم تحصیل لازم است",
        ),
    ]
    for r in rules:
        db_session.add(r)
    await db_session.commit()
    return rules
