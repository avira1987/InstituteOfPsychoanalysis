"""Operational Database Models - Students, Process Instances, Sessions, Financials.

These models store the *runtime data* for active process instances and student records.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, BigInteger, Boolean, DateTime, Time, Float,
    ForeignKey, Index, Date, text, UniqueConstraint,
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
    # رمز ورود با نام کاربری (مسیر «ورود پرسنل»)؛ متن ساده فقط برای نمایش ادمین/کارمند
    portal_password_plain = Column(String(128), nullable=True)
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
    # رسته‌های کمیته دروس، tier مدرس/کمک‌مدرس، و سایر متادیتای نقش آموزشی
    profile_meta = Column(JSONB, nullable=True)

    # Relationships
    # DB: students.user_id → users.id ON DELETE CASCADE — بدون passive_deletes، ORM سعی می‌کند user_id را NULL کند و خطای NOT NULL می‌دهد.
    student_profile = relationship(
        "Student",
        back_populates="user",
        uselist=False,
        foreign_keys="[Student.user_id]",
        passive_deletes=True,
    )


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
    host_meeting_url = Column(Text, nullable=True)
    meeting_provider = Column(String(50), nullable=True)  # manual, skyroom, voicoom, alocom
    links_unlocked = Column(Boolean, default=False, nullable=False)
    instructor_score = Column(Float, nullable=True)
    instructor_comment = Column(Text, nullable=True)
    alocom_event_id = Column(String(80), nullable=True, index=True)
    session_starts_at = Column(DateTime(timezone=True), nullable=True)
    link_reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
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
    gateway_track_id = Column(String(255), nullable=True)  # SEP token, Zibal trackId, Zarinpal authority, mock
    gateway_provider = Column(String(32), nullable=True)  # zibal | zarinpal | saman | mock (verify در callback)
    instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(UUID, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class PaymentGatewayReceipt(Base):
    """رسید درگاه (زیبال: refNumber) — یکتا برای جلوگیری از دوبار ثبت مالی/ریپلی."""

    __tablename__ = "payment_gateway_receipts"
    __table_args__ = (
        UniqueConstraint("provider", "gateway_ref", name="uq_pgr_provider_ref"),
        Index("ix_pgr_student_id", "student_id"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    provider = Column(String(32), nullable=False)
    gateway_ref = Column(String(128), nullable=False)
    authority = Column(String(255), nullable=True)
    amount_rial = Column(BigInteger, nullable=False)
    student_id = Column(UUID, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    process_instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class NotificationOutbox(Base):
    """Durable SMS/notification queue with retry."""

    __tablename__ = "notification_outbox"
    __table_args__ = (
        Index("ix_notif_outbox_status", "status"),
        Index("ix_notif_outbox_next_retry", "next_retry_at"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    channel = Column(String(20), nullable=False, default="sms")
    recipient = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    template_key = Column(String(120), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=5)
    last_error = Column(Text, nullable=True)
    context_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)


class FailedAction(Base):
    """Post-transition actions that failed — for operator retry."""

    __tablename__ = "failed_actions"
    __table_args__ = (Index("ix_failed_actions_instance", "instance_id"),)

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(String(100), nullable=False)
    action_payload = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


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


class InterviewSlotRecurringRule(Base):
    """الگوی هفتگی برای ساخت خودکار اسلات مصاحبه (فقط مصاحبه‌گر)."""

    __tablename__ = "interview_slot_recurring_rules"
    __table_args__ = (
        Index("ix_interview_slot_rr_interviewer", "interviewer_user_id"),
        Index("ix_interview_slot_rr_active", "is_active"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    interviewer_user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # weekdays به‌قرار تقویم میلادی محلی تهران — همان weekday پایتون: دوشنبه=0 … یکشنبه=6
    days_of_week = Column(JSONB, nullable=False)
    start_local_time = Column(Time(timezone=False), nullable=False)
    end_local_time = Column(Time(timezone=False), nullable=False)
    course_type = Column(String(50), nullable=True)
    mode = Column(String(20), nullable=False, default="online")
    location_fa = Column(String(500), nullable=True)
    meeting_link = Column(Text, nullable=True)
    label_fa = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    # چند روز رو به جلو اسلات قطعی می‌سازد (هر بار اجرای job)
    horizon_days = Column(Integer, nullable=False, default=21, server_default=text("21"))
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    interviewer = relationship("User", foreign_keys=[interviewer_user_id])


class InterviewSlot(Base):
    """زمان‌های قابل رزرو برای مصاحبهٔ پذیرش؛ پس از تخصیص تا پایان مصاحبه برای دیگران آزاد نمی‌شود."""

    __tablename__ = "interview_slots"
    __table_args__ = (
        Index("ix_interview_slots_starts", "starts_at"),
        Index("ix_interview_slots_assigned_student", "assigned_student_id"),
        Index(
            "uq_interview_slot_rule_generated_start",
            "generated_from_rule_id",
            "starts_at",
            unique=True,
            postgresql_where=text("generated_from_rule_id IS NOT NULL"),
        ),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    course_type = Column(String(50), nullable=True)  # introductory | comprehensive | None = هر دو
    mode = Column(String(20), nullable=False, default="online")  # in_person | online
    location_fa = Column(String(500), nullable=True)
    meeting_link = Column(Text, nullable=True)
    host_meeting_link = Column(Text, nullable=True)
    interviewer_meeting_link = Column(Text, nullable=True)
    alocom_event_id = Column(String(80), nullable=True, index=True)
    label_fa = Column(String(255), nullable=True)
    created_by = Column(UUID, ForeignKey("users.id"), nullable=True)
    interviewer_user_id = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    generated_from_rule_id = Column(
        UUID, ForeignKey("interview_slot_recurring_rules.id", ondelete="SET NULL"), nullable=True
    )
    assigned_student_id = Column(UUID, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    assigned_instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="SET NULL"), nullable=True)
    # تا تأیید پرداخت مصاحبه: اگر الان از این زمان گذشت، اسلات آزاد و فرایند عقب کشیده می‌شود.
    booking_payment_deadline_at = Column(DateTime(timezone=True), nullable=True)
    # اگر فعال باشد دانشجو می‌تواند قبل از پنجرهٔ ۳۰ دقیقه‌ای وارد جلسهٔ آنلاین شود.
    student_join_open = Column(Boolean, default=False, nullable=False, server_default="false")
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


class SmsSimulationOutbox(Base):
    """پیامک شبیه‌سازی‌شده هنگام SMS_PROVIDER=log — برای نمایش پاپ‌آپ تست در پنل."""

    __tablename__ = "sms_simulation_outbox"
    __table_args__ = (
        Index("ix_sms_sim_outbox_phone", "phone"),
        Index("ix_sms_sim_outbox_created", "created_at"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    phone = Column(String(15), nullable=False)
    message = Column(Text, nullable=False)
    kind = Column(String(32), nullable=False)  # otp | notification | pattern | free_text
    template_key = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class InstituteCalendar(Base):
    """تقویم آموزشی فعال انستیتو — منبع تاریخ ترم، ثبت‌نام و ارزیابی."""

    __tablename__ = "institute_calendars"
    __table_args__ = (
        Index("ix_institute_calendars_active", "is_active"),
        Index("ix_institute_calendars_term_code", "term_code"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    term_code = Column(String(50), unique=True, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False, server_default=text("false"))
    term_start_date = Column(Date, nullable=True)
    term_end_date = Column(Date, nullable=True)
    registration_open_at = Column(DateTime(timezone=True), nullable=True)
    registration_deadline_at = Column(DateTime(timezone=True), nullable=True)
    evaluation_open_at = Column(DateTime(timezone=True), nullable=True)
    evaluation_close_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source_process_instance_id = Column(
        UUID, ForeignKey("process_instances.id", ondelete="SET NULL"), nullable=True
    )
    extra_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class PanelTaskReminder(Base):
    """نوتیفیکیشن ثبت‌شدهٔ پنل — مثلاً یادآوری روزانه کار عقب‌افتاده."""

    __tablename__ = "panel_task_reminders"
    __table_args__ = (
        Index("ix_panel_task_reminders_user", "user_id"),
        Index("ix_panel_task_reminders_run_date", "run_date_tehran"),
        UniqueConstraint("fingerprint", name="uq_panel_task_reminders_fingerprint"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(50), nullable=False, default="daily_overdue")
    title_fa = Column(String(500), nullable=False)
    summary_fa = Column(Text, nullable=True)
    action_path = Column(String(1024), nullable=False)
    instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(UUID, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    process_code = Column(String(100), nullable=True)
    state_code = Column(String(100), nullable=True)
    responsible_role_code = Column(String(50), nullable=True)
    source = Column(String(50), nullable=False, default="daily_overdue_check")
    run_date_tehran = Column(Date, nullable=False)
    sms_sent_at = Column(DateTime(timezone=True), nullable=True)
    fingerprint = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id])


class DailyOverdueRunLog(Base):
    """گزارش اجرای موتور چک روزانه کارهای عقب‌افتاده."""

    __tablename__ = "daily_overdue_run_logs"
    __table_args__ = (
        Index("ix_daily_overdue_run_logs_date", "run_date_tehran"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    run_date_tehran = Column(Date, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    tasks_found = Column(Integer, default=0, nullable=False)
    sms_sent = Column(Integer, default=0, nullable=False)
    notifications_created = Column(Integer, default=0, nullable=False)
    skipped_dedup = Column(Integer, default=0, nullable=False)
    errors_json = Column(JSONB, nullable=True)
    triggered_by = Column(String(20), nullable=False, default="scheduler")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class SmsSimulationDismissal(Base):
    """بستن پاپ‌آپ توسط کاربر — هر کاربر فقط پیامک به شمارهٔ خودش را می‌بیند."""

    __tablename__ = "sms_simulation_dismissals"
    __table_args__ = (
        Index("ix_sms_sim_dismiss_user", "user_id"),
    )

    sms_id = Column(
        UUID,
        ForeignKey("sms_simulation_outbox.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    dismissed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


