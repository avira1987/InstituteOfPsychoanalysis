"""Operational Database Models - Students, Process Instances, Sessions, Financials.

These models store the *runtime data* for active process instances and student records.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, Float, ForeignKey,
    Index, Date, text,
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
    role = Column(String(50), nullable=False, default="student")  # admin, staff, finance, therapist, student, …
    is_active = Column(Boolean, default=True, nullable=False)
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(512), nullable=True)  # مسیر نسبی عکس پروفایل، مثلاً /uploads/avatars/xxx.jpg
    security_question = Column(String(255), nullable=True)  # سوال امنیتی
    security_answer_hash = Column(String(255), nullable=True)  # پاسخ هش‌شده
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    # شناسهٔ کاربر agent در الوکام (برای نقش teacher/participant در رویداد)
    alocom_agent_user_id = Column(Integer, nullable=True)

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
    # رکوردهای بارگذاری‌شده برای آموزش/تست فرایند — در گزارش‌ها پیش‌فرض حذف می‌شوند
    is_sample_data = Column(Boolean, default=False, nullable=False, server_default=text("false"))
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
    meeting_url = Column(Text, nullable=True)
    meeting_provider = Column(String(50), nullable=True)  # manual, skyroom, voicoom, alocom
    links_unlocked = Column(Boolean, default=False, nullable=False)
    instructor_score = Column(Float, nullable=True)
    instructor_comment = Column(Text, nullable=True)
    alocom_event_id = Column(String(80), nullable=True, index=True)
    session_starts_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Assignment(Base):
    """Minimal homework item for a student."""
    __tablename__ = "assignments"
    __table_args__ = (Index("ix_assignments_student", "student_id"),)

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    title_fa = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (Index("ix_submission_assignment", "assignment_id"),)

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    assignment_id = Column(UUID, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    body_text = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    score = Column(Float, nullable=True)
    feedback_fa = Column(Text, nullable=True)


class PaymentPending(Base):
    """Links order reference (ResNum/orderId) + optional gateway id to instance for callback (BUILD_TODO § و — بخش ۶)."""
    __tablename__ = "payment_pending"
    __table_args__ = (
        Index("ix_payment_pending_authority", "authority"),
        Index("ix_payment_pending_gateway_track_id", "gateway_track_id"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    authority = Column(String(255), nullable=False)  # ResNum / orderId (same as SendToken ResNum)
    gateway_track_id = Column(String(255), nullable=True)  # SEP token, Zibal trackId, mock authority
    instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)
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


class OTPCode(Base):
    """One-time password codes for SMS-based authentication."""
    __tablename__ = "otp_codes"
    __table_args__ = (
        Index("ix_otp_phone", "phone"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    phone = Column(String(15), nullable=False)
    code = Column(String(6), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )
    attempts = Column(Integer, default=0, nullable=False)


class LoginChallenge(Base):
    """Simple math challenge for password login anti-bot."""
    __tablename__ = "login_challenges"
    __table_args__ = (
        Index("ix_login_challenge_created_at", "created_at"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    question = Column(String(255), nullable=False)
    answer_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(
        Boolean, default=False, nullable=False, server_default=text("false")
    )


class InterviewSlot(Base):
    """زمان‌های قابل رزرو برای مصاحبهٔ پذیرش؛ پس از تخصیص تا پایان مصاحبه برای دیگران آزاد نمی‌شود."""

    __tablename__ = "interview_slots"
    __table_args__ = (
        Index("ix_interview_slots_starts", "starts_at"),
        Index("ix_interview_slots_assigned_student", "assigned_student_id"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    course_type = Column(String(50), nullable=True)  # introductory | comprehensive | None = هر دو
    mode = Column(String(20), nullable=False, default="in_person")  # in_person | online
    location_fa = Column(String(500), nullable=True)
    meeting_link = Column(Text, nullable=True)
    label_fa = Column(String(255), nullable=True)
    created_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    assigned_student_id = Column(UUID, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    assigned_instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="SET NULL"), nullable=True)
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class BlogPost(Base):
    """Blog/article content for the public website."""
    __tablename__ = "blog_posts"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False, index=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    author_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    category = Column(String(100), nullable=True)  # "news", "article", "tutorial", "announcement"
    tags = Column(String(500), nullable=True)
    featured_image = Column(String(500), nullable=True)
    is_published = Column(Boolean, default=False, nullable=False)
    views = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)

    author = relationship("User", foreign_keys=[author_id])


class SupportTicket(Base):
    """درخواست داخلی کارکنان (تیکت) برای ارجاع به فرد دارای دسترسی مناسب."""

    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_support_tickets_requester", "requester_id"),
        Index("ix_support_tickets_assignee", "assignee_id"),
        Index("ix_support_tickets_status", "status"),
        Index("ix_support_tickets_created", "created_at"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    # مثال: profile_edit_unlock, process_general, data_correction, other
    category = Column(String(80), nullable=False, default="other")
    status = Column(String(30), nullable=False, default="open")  # open, in_progress, resolved, closed
    priority = Column(String(20), nullable=False, default="normal")  # low, normal, high

    requester_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assignee_id = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    student_id = Column(UUID, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    process_instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="SET NULL"), nullable=True)
    extra_context = Column(JSONB, nullable=True)  # شناسهٔ مرحله، یادداشت ساختاری، ...

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    requester = relationship("User", foreign_keys=[requester_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    student = relationship("Student", foreign_keys=[student_id])
    comments = relationship(
        "TicketComment",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )


class TicketComment(Base):
    """پاسخ یا پیام روی تیکت."""

    __tablename__ = "ticket_comments"
    __table_args__ = (Index("ix_ticket_comments_ticket", "ticket_id"),)

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    ticket_id = Column(UUID, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # user = پیام کاربر | system = لاگ خودکار (پیگیری، تغییر وضعیت، ارجاع)
    kind = Column(String(20), nullable=False, default="user")
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    ticket = relationship("SupportTicket", back_populates="comments")
    author = relationship("User", foreign_keys=[author_id])


class SiteSetting(Base):
    """تنظیمات کلید-مقدار برای وب‌سایت (مثلاً سیاست اقساط)."""

    __tablename__ = "site_settings"

    key = Column(String(100), primary_key=True)
    value_json = Column(JSONB, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
