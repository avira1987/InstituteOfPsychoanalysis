"""Meta Database Models - Process, State, Transition, and Rule definitions.

These models store the *metadata* that drives the state machine engine.
No business logic is hardcoded; everything is data-driven.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, LargeBinary,
)
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.compat import GUID as UUID, JSONType as JSONB


def utcnow():
    return datetime.now(timezone.utc)


class ProcessDefinition(Base):
    """Top-level process definition (state machine blueprint)."""
    __tablename__ = "process_definitions"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name_fa = Column(String(255), nullable=False)
    name_en = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    initial_state_code = Column(String(100), nullable=False)
    config = Column(JSONB, nullable=True)  # process-level config (timeouts, etc.)
    # سند خام SOP و تصویر فلوچارت (فقط پنل ادمین؛ اجرای موتور وابسته نیست)
    source_text = Column(Text, nullable=True)
    flowchart_image = Column(LargeBinary, nullable=True)
    flowchart_content_type = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    updated_by = Column(UUID, nullable=True)

    # Relationships
    states = relationship("StateDefinition", back_populates="process", cascade="all, delete-orphan")
    transitions = relationship("TransitionDefinition", back_populates="process", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ProcessDefinition(code='{self.code}', name_fa='{self.name_fa}')>"


class StateDefinition(Base):
    """A state within a process (node in the state diagram)."""
    __tablename__ = "state_definitions"
    __table_args__ = (
        UniqueConstraint("process_id", "code", name="uq_state_process_code"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    process_id = Column(UUID, ForeignKey("process_definitions.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(100), nullable=False)
    name_fa = Column(String(255), nullable=False)
    name_en = Column(String(255), nullable=True)
    state_type = Column(String(20), nullable=False)  # "initial" | "intermediate" | "terminal"
    metadata_ = Column("meta_info", JSONB, nullable=True)  # UI hints, timeout settings
    assigned_role = Column(String(100), nullable=True)
    sla_hours = Column(Integer, nullable=True)
    on_sla_breach_event = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    process = relationship("ProcessDefinition", back_populates="states")

    def __repr__(self):
        return f"<StateDefinition(code='{self.code}', process='{self.process_id}')>"


class TransitionDefinition(Base):
    """A transition between two states (edge in the state diagram)."""
    __tablename__ = "transition_definitions"
    __table_args__ = (
        Index("ix_transition_lookup", "process_id", "from_state_code", "trigger_event"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    process_id = Column(UUID, ForeignKey("process_definitions.id", ondelete="CASCADE"), nullable=False)
    from_state_code = Column(String(100), nullable=False)
    to_state_code = Column(String(100), nullable=False)
    trigger_event = Column(String(100), nullable=False)
    condition_rules = Column(JSONB, nullable=True)  # list of rule codes to evaluate
    required_role = Column(String(100), nullable=True)
    actions = Column(JSONB, nullable=True)  # post-transition actions
    priority = Column(Integer, default=0, nullable=False)
    description_fa = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    process = relationship("ProcessDefinition", back_populates="transitions")

    def __repr__(self):
        return f"<TransitionDefinition(from='{self.from_state_code}', to='{self.to_state_code}')>"


class RuleDefinition(Base):
    """A dynamic rule evaluated at runtime by the rule engine."""
    __tablename__ = "rule_definitions"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name_fa = Column(String(255), nullable=False)
    name_en = Column(String(255), nullable=True)
    rule_type = Column(String(30), nullable=False)  # "condition" | "validation" | "computation"
    expression = Column(JSONB, nullable=False)
    parameters = Column(JSONB, nullable=True)
    error_message_fa = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self):
        return f"<RuleDefinition(code='{self.code}', type='{self.rule_type}')>"
