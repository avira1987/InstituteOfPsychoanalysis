"""Attendance Service - Tracking therapy session attendance and absence quotas."""

import uuid
import math
import logging
from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import AttendanceRecord, TherapySession, Student

logger = logging.getLogger(__name__)

# When no upcoming session exists, use a large value so 24_hour_rule does not block (use_first_slot).
NO_UPCOMING_SESSION_HOURS = 999.0


class AttendanceService:
    """Service for tracking attendance, absences, and quota management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Attendance Recording ───────────────────────────────────

    async def record_attendance(
        self,
        student_id: uuid.UUID,
        session_id: Optional[uuid.UUID],
        record_date: date,
        status: str,  # "present", "absent_excused", "absent_unexcused"
        absence_type: Optional[str] = None,  # "student", "therapist", "mutual"
        shamsi_year: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> AttendanceRecord:
        """Record attendance for a therapy session."""
        record = AttendanceRecord(
            id=uuid.uuid4(),
            student_id=student_id,
            session_id=session_id,
            record_date=record_date,
            status=status,
            absence_type=absence_type,
            shamsi_year=shamsi_year,
            notes=notes,
        )
        self.db.add(record)

        # Update session status if session_id provided
        if session_id:
            session_stmt = select(TherapySession).where(TherapySession.id == session_id)
            result = await self.db.execute(session_stmt)
            session = result.scalars().first()
            if session:
                if status == "present":
                    session.status = "completed"
                elif status.startswith("absent"):
                    session.status = "absent"

        logger.info(f"Attendance recorded: student={student_id}, date={record_date}, status={status}")
        return record

    # ─── Absence Quota Calculation ──────────────────────────────

    async def calculate_absence_quota(self, student_id: uuid.UUID) -> int:
        """Calculate the annual absence quota for a student.

        Formula from SOP: ceil(weekly_sessions * 3) per Shamsi year
        """
        stmt = select(Student).where(Student.id == student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return 0
        return math.ceil(student.weekly_sessions * 3)

    async def get_absence_count(
        self,
        student_id: uuid.UUID,
        shamsi_year: Optional[int] = None,
        status_filter: str = "absent_unexcused",
    ) -> int:
        """Get the count of absences for a student in a given year."""
        stmt = select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.status == status_filter,
        )
        if shamsi_year:
            stmt = stmt.where(AttendanceRecord.shamsi_year == shamsi_year)

        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def check_quota_exceeded(
        self,
        student_id: uuid.UUID,
        shamsi_year: Optional[int] = None,
    ) -> dict:
        """Check if a student has exceeded their absence quota."""
        quota = await self.calculate_absence_quota(student_id)
        absences = await self.get_absence_count(student_id, shamsi_year)
        remaining = max(0, quota - absences)

        return {
            "student_id": str(student_id),
            "quota": quota,
            "absences": absences,
            "remaining": remaining,
            "exceeded": absences >= quota,
            "shamsi_year": shamsi_year,
        }

    # ─── First upcoming slot (for 24_hour_rule) ───────────────────

    async def get_hours_until_first_slot(self, student_id: uuid.UUID, today: Optional[date] = None) -> float:
        """Hours from now until the first upcoming scheduled therapy session.

        Used by rule 24_hour_rule. Sessions have only session_date (no time); we use
        (session_date - today).days * 24. If session is today, return 0 so rule treats as < 24h.
        If no upcoming session, return NO_UPCOMING_SESSION_HOURS so rule does not block.
        """
        if today is None:
            today = datetime.now(timezone.utc).date()
        stmt = (
            select(TherapySession.session_date)
            .where(
                TherapySession.student_id == student_id,
                TherapySession.session_date >= today,
                TherapySession.status == "scheduled",
            )
            .order_by(TherapySession.session_date.asc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        session_date = result.scalars().first()
        if not session_date:
            return NO_UPCOMING_SESSION_HOURS
        delta_days = (session_date - today).days
        if delta_days <= 0:
            return 0.0  # today → treat as less than 24h
        return float(delta_days * 24)

    # ─── Session Hour Tracking ──────────────────────────────────

    async def get_completed_hours(self, student_id: uuid.UUID) -> dict:
        """Get the total completed therapy hours for a student."""
        stmt = select(func.count(TherapySession.id)).where(
            TherapySession.student_id == student_id,
            TherapySession.status == "completed",
        )
        result = await self.db.execute(stmt)
        completed_sessions = result.scalar() or 0

        # Also count extra sessions
        extra_stmt = select(func.count(TherapySession.id)).where(
            TherapySession.student_id == student_id,
            TherapySession.status == "completed",
            TherapySession.is_extra == True,
        )
        extra_result = await self.db.execute(extra_stmt)
        extra_sessions = extra_result.scalar() or 0

        return {
            "student_id": str(student_id),
            "total_completed_sessions": completed_sessions,
            "regular_sessions": completed_sessions - extra_sessions,
            "extra_sessions": extra_sessions,
            "total_hours": completed_sessions,  # 1 session = 1 hour (standard)
        }

    async def get_therapy_completion_metrics(self, student_id: uuid.UUID) -> dict:
        """
        ساعات مورد استفاده در فرایند therapy_completion:
        - therapy_hours_2x: همهٔ جلسات درمان آموزشی با وضعیت completed (۱ جلسه = ۱ ساعت؛
          شامل جلسه اضافی)؛ هم‌تراز با ثبت حضور و جلسه اضافی.
        - clinical_hours / supervision_hours: از extra_data دانشجو (ثبت دستی/فرایندهای دیگر).
        """
        stmt = select(func.count()).select_from(TherapySession).where(
            TherapySession.student_id == student_id,
            TherapySession.status == "completed",
        )
        r = await self.db.execute(stmt)
        from_sessions = float(r.scalar() or 0)

        st = await self.db.get(Student, student_id)
        ex = dict(st.extra_data or {}) if st else {}
        clinical = float(ex.get("clinical_hours") or 0)
        supervision = float(ex.get("supervision_hours") or 0)
        # انباشت قدیمی جلسه اضافی یا اصلاح دستی؛ با حداکثر جلسات تکمیل‌شده هم‌تراز می‌شود
        try:
            legacy_extra = float(ex.get("accumulated_therapy_hours") or 0)
        except (TypeError, ValueError):
            legacy_extra = 0.0
        try:
            stored_th = float(ex.get("therapy_hours_2x") or 0)
        except (TypeError, ValueError):
            stored_th = 0.0
        therapy_hours_2x = max(from_sessions, legacy_extra, stored_th)
        return {
            "therapy_hours_2x": therapy_hours_2x,
            "clinical_hours": clinical,
            "supervision_hours": supervision,
        }

    # ─── Attendance History ─────────────────────────────────────

    async def get_attendance_history(
        self,
        student_id: uuid.UUID,
        limit: int = 50,
    ) -> list[dict]:
        """Get attendance history for a student."""
        stmt = (
            select(AttendanceRecord)
            .where(AttendanceRecord.student_id == student_id)
            .order_by(AttendanceRecord.record_date.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        records = result.scalars().all()

        return [
            {
                "id": str(r.id),
                "date": r.record_date.isoformat(),
                "status": r.status,
                "absence_type": r.absence_type,
                "notes": r.notes,
            }
            for r in records
        ]

    async def get_attendance_summary(self, student_id: uuid.UUID, shamsi_year: Optional[int] = None) -> dict:
        """Get attendance summary statistics for a student."""
        base_filter = [AttendanceRecord.student_id == student_id]
        if shamsi_year:
            base_filter.append(AttendanceRecord.shamsi_year == shamsi_year)

        # Present count
        present_stmt = select(func.count(AttendanceRecord.id)).where(
            *base_filter, AttendanceRecord.status == "present"
        )
        present_result = await self.db.execute(present_stmt)
        present = present_result.scalar() or 0

        # Excused absences
        excused_stmt = select(func.count(AttendanceRecord.id)).where(
            *base_filter, AttendanceRecord.status == "absent_excused"
        )
        excused_result = await self.db.execute(excused_stmt)
        excused = excused_result.scalar() or 0

        # Unexcused absences
        unexcused_stmt = select(func.count(AttendanceRecord.id)).where(
            *base_filter, AttendanceRecord.status == "absent_unexcused"
        )
        unexcused_result = await self.db.execute(unexcused_stmt)
        unexcused = unexcused_result.scalar() or 0

        quota = await self.calculate_absence_quota(student_id)

        return {
            "student_id": str(student_id),
            "present": present,
            "absent_excused": excused,
            "absent_unexcused": unexcused,
            "total_sessions": present + excused + unexcused,
            "attendance_rate": round(present / max(1, present + excused + unexcused) * 100, 1),
            "absence_quota": quota,
            "remaining_quota": max(0, quota - unexcused),
        }
