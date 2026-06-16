"""قالب‌های فرم داینامیک (DB) — منو و پاسخ‌ها."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.compat import GUID as UUID, JSONType as JSONB


def utcnow():
    return datetime.now(timezone.utc)


class FormTemplate(Base):
    """قالب منطقی فرم (چند نسخه دارد)."""

    __tablename__ = "form_templates"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    code = Column(String(80), nullable=False, unique=True, index=True)
    name_fa = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    audience = Column(String(20), nullable=False, default="both")  # student | operator | both
    created_by_id = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    versions = relationship("FormTemplateVersion", back_populates="template", order_by="FormTemplateVersion.version.desc()")
    assignments = relationship("FormAssignment", back_populates="template")


class FormTemplateVersion(Base):
    """نسخهٔ منتشرشده یا پیش‌نویس schema_json."""

    __tablename__ = "form_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_form_template_version"),
        Index("ix_form_template_versions_template", "template_id"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID, ForeignKey("form_templates.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    schema_json = Column(JSONB, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    # منبع نسخه: metadata (واردشده از JSON فرایند) یا manual (ساختهٔ ادمین)
    source = Column(String(16), nullable=False, default="manual")
    process_code = Column(String(100), nullable=True)
    state_code = Column(String(100), nullable=True)

    template = relationship("FormTemplate", back_populates="versions")
    responses = relationship("FormResponse", back_populates="template_version")


class FormAssignment(Base):
    """اتصال قالب به پورتال یا فرایند."""

    __tablename__ = "form_assignments"
    __table_args__ = (
        Index("ix_form_assignments_process_state", "process_code", "state_code"),
        Index("ix_form_assignments_portal_role", "portal_role"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID, ForeignKey("form_templates.id", ondelete="CASCADE"), nullable=False)
    template_version_id = Column(
        UUID, ForeignKey("form_template_versions.id", ondelete="SET NULL"), nullable=True
    )
    assignment_type = Column(String(32), nullable=False)  # portal | process | standalone
    portal_role = Column(String(64), nullable=True)
    portal_section = Column(String(64), nullable=True)
    process_code = Column(String(100), nullable=True)
    state_code = Column(String(100), nullable=True)
    context_key = Column(String(80), nullable=True)
    submit_label_fa = Column(String(255), nullable=True)
    header_fa = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    template = relationship("FormTemplate", back_populates="assignments")
    pinned_version = relationship("FormTemplateVersion", foreign_keys=[template_version_id])


class FormResponse(Base):
    """پاسخ به یک نسخهٔ قالب."""

    __tablename__ = "form_responses"
    __table_args__ = (
        Index("ix_form_responses_student", "student_id"),
        Index("ix_form_responses_instance", "instance_id"),
        Index("ix_form_responses_version", "template_version_id"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    template_version_id = Column(
        UUID, ForeignKey("form_template_versions.id", ondelete="CASCADE"), nullable=False
    )
    assignment_id = Column(UUID, ForeignKey("form_assignments.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    student_id = Column(UUID, ForeignKey("students.id", ondelete="CASCADE"), nullable=True)
    instance_id = Column(UUID, ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=True)
    status = Column(String(24), nullable=False, default="draft")  # draft | submitted | approved | rejected
    answers_json = Column(JSONB, nullable=False, default=dict)
    # وضعیت تأیید/رد per فیلد (برای بازبینی مدارک): { field_name: {"status","note"} }
    field_status = Column(JSONB, nullable=True)
    # فیلدهایی که برای ویرایش مجدد توسط دانشجو باز شده‌اند
    edit_unlocked_fields = Column(JSONB, nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    template_version = relationship("FormTemplateVersion", back_populates="responses")
    approval_steps = relationship(
        "FormApprovalStep", back_populates="response", order_by="FormApprovalStep.step_index"
    )
    files = relationship("FormFieldFile", back_populates="response", cascade="all, delete-orphan")


class FormApprovalStep(Base):
    """گام تأیید برای یک پاسخ."""

    __tablename__ = "form_approval_steps"
    __table_args__ = (Index("ix_form_approval_steps_response", "response_id"),)

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    response_id = Column(UUID, ForeignKey("form_responses.id", ondelete="CASCADE"), nullable=False)
    step_index = Column(Integer, nullable=False)
    required_role = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="pending")  # pending | approved | rejected
    acted_by_id = Column(UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acted_at = Column(DateTime(timezone=True), nullable=True)
    comment = Column(Text, nullable=True)

    response = relationship("FormResponse", back_populates="approval_steps")


class FormFieldFile(Base):
    """فایل بارگذاری‌شده برای یک فیلد از یک پاسخ (multipart)."""

    __tablename__ = "form_field_files"
    __table_args__ = (Index("ix_form_field_files_response", "response_id"),)

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    response_id = Column(UUID, ForeignKey("form_responses.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(120), nullable=False)
    file_name = Column(String(512), nullable=False)
    url = Column(String(1024), nullable=False)
    mime_type = Column(String(120), nullable=True)
    size = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    response = relationship("FormResponse", back_populates="files")


class FormDynamicSource(Base):
    """رجیستری منابع پویای گزینه‌ها (drop-down ها) که سرور resolve می‌کند."""

    __tablename__ = "form_dynamic_sources"

    key = Column(String(80), primary_key=True)
    resolver = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class PortalNavConfig(Base):
    """منوی پویا per نقش پورتال."""

    __tablename__ = "portal_nav_configs"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    role = Column(String(64), nullable=False, unique=True, index=True)
    items_json = Column(JSONB, nullable=False, default=list)
    merge_mode = Column(String(24), default="append", nullable=False)  # append | prepend | replace
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
