"""Audit Log Models - Complete audit trail for every action."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from app.database import Base
from app.models.compat import GUID as UUID, JSONType as JSONB


def utcnow():
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """Immutable audit log entry."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_instance", "instance_id"),
        Index("ix_audit_actor", "actor_id"),
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_action", "action_type"),
    )

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    instance_id = Column(UUID, nullable=True)
    process_code = Column(String(100), nullable=True)
    action_type = Column(String(50), nullable=False)  # "transition", "rule_change", "override", "login", etc.
    from_state = Column(String(100), nullable=True)
    to_state = Column(String(100), nullable=True)
    trigger_event = Column(String(100), nullable=True)
    actor_id = Column(UUID, nullable=True)
    actor_role = Column(String(50), nullable=True)
    actor_name = Column(String(255), nullable=True)
    details = Column(JSONB, nullable=True)  # Full details of the action
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    def __repr__(self):
        return f"<AuditLog(action='{self.action_type}', actor='{self.actor_id}', ts='{self.timestamp}')>"
