"""Process Service - High-level service for process operations."""

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance, Student
from app.models.meta_models import ProcessDefinition
from app.core.engine import StateMachineEngine


class ProcessService:
    """High-level service wrapping the state machine engine."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = StateMachineEngine(db)

    async def start_process_for_student(
        self,
        process_code: str,
        student_id: uuid.UUID,
        actor_id: uuid.UUID,
        actor_role: str,
        initial_context: Optional[dict] = None,
    ) -> ProcessInstance:
        """Start a new process instance for a student."""
        return await self.engine.start_process(
            process_code=process_code,
            student_id=student_id,
            actor_id=actor_id,
            actor_role=actor_role,
            initial_context=initial_context,
        )

    async def get_student_active_processes(self, student_id: uuid.UUID) -> list[dict]:
        """Get all active process instances for a student."""
        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student_id,
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        result = await self.db.execute(stmt)
        instances = result.scalars().all()

        return [
            await self.engine.get_instance_status(i.id)
            for i in instances
        ]

    async def get_student_lifecycle(self, student_id: uuid.UUID) -> dict:
        """Get complete lifecycle view of a student across all processes."""
        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student_id,
        ).order_by(ProcessInstance.started_at)
        result = await self.db.execute(stmt)
        instances = result.scalars().all()

        active = []
        completed = []
        cancelled = []

        for i in instances:
            info = {
                "instance_id": str(i.id),
                "process_code": i.process_code,
                "current_state": i.current_state_code,
                "started_at": i.started_at.isoformat() if i.started_at else None,
                "completed_at": i.completed_at.isoformat() if i.completed_at else None,
            }
            if i.is_cancelled:
                cancelled.append(info)
            elif i.is_completed:
                completed.append(info)
            else:
                active.append(info)

        return {
            "student_id": str(student_id),
            "active_processes": active,
            "completed_processes": completed,
            "cancelled_processes": cancelled,
            "total": len(instances),
        }
