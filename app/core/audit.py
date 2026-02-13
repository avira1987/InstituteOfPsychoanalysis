"""Audit Logger - Records every action in the system for compliance and traceability."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_models import AuditLog


class AuditLogger:
    """Logs every action (transitions, rule changes, overrides, etc.) to audit_logs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action_type: str,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[str] = None,
        actor_name: Optional[str] = None,
        instance_id: Optional[uuid.UUID] = None,
        process_code: Optional[str] = None,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        trigger_event: Optional[str] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Create an immutable audit log entry."""
        entry = AuditLog(
            id=uuid.uuid4(),
            action_type=action_type,
            actor_id=actor_id,
            actor_role=actor_role,
            actor_name=actor_name,
            instance_id=instance_id,
            process_code=process_code,
            from_state=from_state,
            to_state=to_state,
            trigger_event=trigger_event,
            details=details,
            ip_address=ip_address,
            timestamp=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        return entry

    async def log_transition(
        self,
        instance_id: uuid.UUID,
        process_code: str,
        from_state: str,
        to_state: str,
        trigger_event: str,
        actor_id: uuid.UUID,
        actor_role: str,
        actor_name: Optional[str] = None,
        payload: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log a state transition."""
        return await self.log(
            action_type="transition",
            actor_id=actor_id,
            actor_role=actor_role,
            actor_name=actor_name,
            instance_id=instance_id,
            process_code=process_code,
            from_state=from_state,
            to_state=to_state,
            trigger_event=trigger_event,
            details={"payload": payload} if payload else None,
            ip_address=ip_address,
        )

    async def log_rule_change(
        self,
        rule_code: str,
        change_type: str,
        actor_id: uuid.UUID,
        actor_role: str,
        old_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
    ) -> AuditLog:
        """Log a rule definition change."""
        return await self.log(
            action_type="rule_change",
            actor_id=actor_id,
            actor_role=actor_role,
            details={
                "rule_code": rule_code,
                "change_type": change_type,
                "old_value": old_value,
                "new_value": new_value,
            },
        )

    async def log_process_start(
        self,
        instance_id: uuid.UUID,
        process_code: str,
        student_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: str,
    ) -> AuditLog:
        """Log the start of a new process instance."""
        return await self.log(
            action_type="process_start",
            actor_id=actor_id,
            actor_role=actor_role,
            instance_id=instance_id,
            process_code=process_code,
            details={"student_id": str(student_id)},
        )
