"""Operational Database Models - Students, Process Instances, Sessions, Financials.

These models store the *runtime data* for active process instances and student records.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, Float, ForeignKey,
    Index, Date
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.compat import GUID as UUID, JSONType as JSONB


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    """System user (admin, staff, therapist, student)."""
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    full_name_fa = Column(String(255), nullable=True)
    full_name_en = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="student")  # admin, staff, therapist, student, committee
    is_active = Column(Boolean, default=True, nullable=False)
    phone = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    student_profile = relationship("Student", back_populates="user", uselist=False, foreign_keys="[Student.user_id]")


class Student(Base):
    """Student profile with educational details."""
    __tablename__ = "students"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    student_code = Column(String(50), unique=True, nullable=False, index=True)
    course_type = Column(String(50), nullable=False)  # "introductory" | "comprehensive"
    is_intern = Column(Boolean, default=False, nullable=False)
    term_count = Column(Integer, default=1, nullable=False)
    current_term = Column(Integer, default=1, nullable=False)
    therapy_started = Column(Boolean, default=False, nullable=False)
    weekly_sessions = Column(Integer, default=1, nullable=False)
    supervisor_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    therapist_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    enrollment_date = Column(Date, nullable=True)
    extra_data = Column(JSONB, nullable=True)  # Flexible additional data
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])
    process_instances = relationship("ProcessInstance", back_populates="student")


class ProcessInstance(Base):
    """A running instance of a process for a specific student."""
    __tablename__ = "process_instances"
    __table_args__ = (
        Index("ix_instance_student", "student_id"),
        Index("ix_instance_process", "process_code"),
        Index("ix_instance_state", "current_state_code"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    process_code = Column(String(100), nullable=False)
    student_id = Column(UUID, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    current_state_code = Column(String(100), nullable=False)
    is_completed = Column(Boolean, default=False, nullable=False)
    is_cancelled = Column(Boolean, default=False, nullable=False)
    context_data = Column(JSONB, nullable=True)  # instance-level context data
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_transition_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_by = Column(UUID, ForeignKey("users.id"), nullable=True)

    # Relationships
    student = relationship("Student", back_populates="process_instances")
    state_history = relationship("StateHistory", back_populates="instance", cascade="all, delete-orphan",
                                 order_by="StateHistory.entered_at")


class StateHistory(Base):
    """History of state transitions for a process instance."""
    __tablename__ = "state_history"
    __table_args__ = (
        Index("ix_history_instance", "instance_id"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False)
    from_state_code = Column(String(100), nullable=True)  # null for initial state
    to_state_code = Column(String(100), nullable=False)
    trigger_event = Column(String(100), nullable=False)
    actor_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(50), nullable=True)
    payload = Column(JSONB, nullable=True)
    entered_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    instance = relationship("ProcessInstance", back_populates="state_history")


class TherapySession(Base):
    """Record of a therapy session (educational therapy)."""
    __tablename__ = "therapy_sessions"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID, ForeignKey("students.id"), nullable=False)
    therapist_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    session_date = Column(Date, nullable=False)
    session_number = Column(Integer, nullable=True)
    status = Column(String(30), nullable=False, default="scheduled")  # scheduled, completed, cancelled, absent
    is_extra = Column(Boolean, default=False, nullable=False)
    payment_status = Column(String(30), default="pending")  # pending, paid, waived
    amount = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class FinancialRecord(Base):
    """Financial record for billing and payments."""
    __tablename__ = "financial_records"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID, ForeignKey("students.id"), nullable=False)
    record_type = Column(String(50), nullable=False)  # "payment", "debt", "credit", "absence_fee"
    amount = Column(Float, nullable=False)
    description_fa = Column(String(500), nullable=True)
    reference_id = Column(UUID, nullable=True)  # linked therapy_session or process_instance
    shamsi_year = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by = Column(UUID, ForeignKey("users.id"), nullable=True)


class AttendanceRecord(Base):
    """Attendance tracking for therapy sessions."""
    __tablename__ = "attendance_records"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID, ForeignKey("students.id"), nullable=False)
    session_id = Column(UUID, ForeignKey("therapy_sessions.id"), nullable=True)
    record_date = Column(Date, nullable=False)
    status = Column(String(30), nullable=False)  # "present", "absent_excused", "absent_unexcused"
    absence_type = Column(String(50), nullable=True)  # "student", "therapist", "mutual"
    shamsi_year = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
