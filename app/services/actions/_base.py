"""Shared record lookups every action mixin relies on.

Part of the ActionHandler split. Every method below runs as a mixin method
on ActionHandler, so `self` exposes the whole handler surface.
"""

from app.models.operational_models import (
    Student, User, ProcessInstance, TherapySession, FinancialRecord, AttendanceRecord,
    InterviewSlot,
)
from sqlalchemy import select, delete, func
from typing import Optional, Any, List


class ActionHandlerBase:
    """Shared record lookups every action mixin relies on."""

    async def _get_student(self, student_id) -> Optional[Student]:
        stmt = select(Student).where(Student.id == student_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _get_user(self, user_id) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _get_user_direct(self, user_id) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()


REGISTRY: dict = {}
