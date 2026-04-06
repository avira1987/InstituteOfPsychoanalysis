"""Student Service - Business logic for student operations."""

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import ProcessInstance, Student, User
from app.services.process_service import ProcessService

logger = logging.getLogger(__name__)

EXPECTED_REGISTRATION_CODE = {
    "introductory": "introductory_course_registration",
    "comprehensive": "comprehensive_course_registration",
}


class StudentService:
    """Service for student-related operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_student_by_code(self, student_code: str) -> Optional[Student]:
        """Get a student by their student code."""
        stmt = select(Student).where(Student.student_code == student_code)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_student_by_user_id(self, user_id: uuid.UUID) -> Optional[Student]:
        """Get a student by their user ID."""
        stmt = select(Student).where(Student.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def ensure_primary_registration_path(self, student: Student, actor: User) -> bool:
        """
        If primary_instance_id is missing or invalid, attach an existing registration
        instance or start the initial registration process (same as post-registration).

        Returns True if student.extra_data was updated (caller should commit).
        """
        if not student or not actor:
            return False
        expected = EXPECTED_REGISTRATION_CODE.get(student.course_type)
        if not expected:
            return False

        extra = dict(student.extra_data or {})
        pid_str = extra.get("primary_instance_id")

        if pid_str:
            try:
                pid = uuid.UUID(str(pid_str))
            except ValueError:
                pid = None
            if pid:
                stmt = select(ProcessInstance).where(ProcessInstance.id == pid)
                result = await self.db.execute(stmt)
                inst = result.scalars().first()
                if inst and inst.student_id == student.id:
                    return False
            extra = dict(student.extra_data or {})
            extra.pop("primary_instance_id", None)
            student.extra_data = extra

        stmt = (
            select(ProcessInstance)
            .where(
                ProcessInstance.student_id == student.id,
                ProcessInstance.process_code == expected,
            )
            .order_by(ProcessInstance.started_at.desc())
        )
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        chosen: Optional[ProcessInstance] = None
        for inst in rows:
            if not inst.is_completed and not inst.is_cancelled:
                chosen = inst
                break
        if chosen is None and rows:
            chosen = rows[0]

        if chosen:
            await self.set_primary_instance_for_student(student, chosen.id)
            return True

        try:
            await self.start_initial_process_for_student(student, actor)
            return True
        except Exception:
            logger.exception(
                "ensure_primary_registration_path: failed to start initial process for %s",
                getattr(student, "student_code", student.id),
            )
            return False

    async def set_primary_instance_for_student(self, student: Student, instance_id: uuid.UUID) -> None:
        """
        Store the primary process instance for a student.

        To avoid schema migrations, this is stored in student.extra_data["primary_instance_id"].
        """
        extra = dict(student.extra_data or {})
        extra["primary_instance_id"] = str(instance_id)
        student.extra_data = extra
        flag_modified(student, "extra_data")

    async def start_initial_process_for_student(self, student: Student, actor: User):
        """
        Start the initial registration process for a newly registered student and
        mark it as the primary instance in the student's extra_data.

        The process_code is chosen based on course_type:
        - introductory -> introductory_course_registration
        - comprehensive -> comprehensive_course_registration
        """
        if not student or not actor:
            return None

        if student.course_type == "introductory":
            process_code = "introductory_course_registration"
        else:
            process_code = "comprehensive_course_registration"

        service = ProcessService(self.db)
        instance = await service.start_process_for_student(
            process_code=process_code,
            student_id=student.id,
            actor_id=actor.id,
            actor_role=actor.role or "student",
            initial_context={"source": "auto_start_on_registration"},
        )
        await self.set_primary_instance_for_student(student, instance.id)
        return instance

    async def _resolve_system_actor_id(self, preferred: Optional[uuid.UUID]) -> uuid.UUID:
        if preferred:
            return preferred
        stmt = select(User.id).where(User.role == "admin").limit(1)
        result = await self.db.execute(stmt)
        uid = result.scalars().first()
        if uid:
            return uid
        stmt = select(User.id).limit(1)
        result = await self.db.execute(stmt)
        uid = result.scalars().first()
        if uid:
            return uid
        raise RuntimeError("No user found to attribute system transition")

    _START_THERAPY_TERMINAL = frozenset(
        {"therapy_active", "already_completed", "ineligible", "week9_blocked"}
    )

    async def _advance_start_therapy_eligibility(
        self,
        therapy_instance_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> None:
        """از eligibility_check با تریگرهای سیستمی یکی از مسیرهای مجاز را باز کند."""
        from app.core.engine import StateMachineEngine

        engine = StateMachineEngine(self.db)
        for trigger in ("duplicate_attempt", "eligible", "week9_deadline_exceeded", "not_eligible"):
            result = await engine.execute_transition(
                instance_id=therapy_instance_id,
                trigger_event=trigger,
                actor_id=actor_id,
                actor_role="system",
                payload=None,
            )
            if result.success:
                logger.info(
                    "start_therapy advanced: %s -> %s",
                    trigger,
                    result.to_state,
                )
                return
        logger.warning(
            "start_therapy eligibility could not advance automatically (instance=%s)",
            therapy_instance_id,
        )

    async def maybe_start_followup_after_intro_registration(
        self,
        registration_instance: ProcessInstance,
    ) -> None:
        """
        پس از تکمیل ثبت‌نام دوره آشنایی (registration_complete)، فرایند «آغاز درمان آموزشی»
        را در صورت نبودن نمونهٔ فعال باز می‌کند، از مرحلهٔ بررسی صلاحیت عبور می‌دهد
        و primary_instance_id دانشجو را به آن نمونه می‌چسباند تا مسیر اصلی پورتال ادامه داشته باشد.
        """
        if registration_instance.process_code != "introductory_course_registration":
            return
        if registration_instance.current_state_code != "registration_complete":
            return
        if not registration_instance.is_completed:
            return

        stmt = select(Student).where(Student.id == registration_instance.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return

        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.process_code == "start_therapy",
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        result = await self.db.execute(stmt)
        active = result.scalars().first()
        if active:
            actor_id = await self._resolve_system_actor_id(registration_instance.started_by)
            if active.current_state_code == "eligibility_check":
                await self._advance_start_therapy_eligibility(active.id, actor_id)
            await self.set_primary_instance_for_student(student, active.id)
            return

        stmt = (
            select(ProcessInstance)
            .where(
                ProcessInstance.student_id == student.id,
                ProcessInstance.process_code == "start_therapy",
                ProcessInstance.is_completed == True,
            )
            .order_by(ProcessInstance.started_at.desc())
        )
        result = await self.db.execute(stmt)
        latest_done = result.scalars().first()
        if latest_done and latest_done.current_state_code in self._START_THERAPY_TERMINAL:
            return

        ctx = dict(registration_instance.context_data or {})
        initial = {
            "parent_registration_instance_id": str(registration_instance.id),
            "source": "after_introductory_registration_complete",
            **{k: ctx[k] for k in ("interview_result", "admission_type", "allowed_course_count") if k in ctx},
        }

        service = ProcessService(self.db)
        actor_id = await self._resolve_system_actor_id(registration_instance.started_by)
        try:
            sub = await service.start_process_for_student(
                process_code="start_therapy",
                student_id=student.id,
                actor_id=actor_id,
                actor_role="system",
                initial_context=initial,
            )
        except Exception:
            logger.exception(
                "maybe_start_followup_after_intro_registration: start_therapy failed for student %s",
                student.id,
            )
            return

        await self.db.flush()
        await self._advance_start_therapy_eligibility(sub.id, actor_id)
        await self.set_primary_instance_for_student(student, sub.id)

    async def maybe_start_session_payment_after_start_therapy(self, therapy_instance: ProcessInstance) -> None:
        """
        پس از تکمیل موفق start_therapy (حالت پایانی therapy_active)، فرایند «پرداخت جلسات آتی»
        را در صورت نبودن نمونهٔ فعال باز می‌کند و primary_instance_id را به آن می‌چسباند
        (ادامهٔ مسیر درمان طبق زنجیرهٔ session_payment در INDEX / مسیر دانشجو).
        """
        if therapy_instance.process_code != "start_therapy":
            return
        if not therapy_instance.is_completed or therapy_instance.is_cancelled:
            return
        if therapy_instance.current_state_code != "therapy_active":
            return

        stmt = select(Student).where(Student.id == therapy_instance.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return

        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.process_code == "session_payment",
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        result = await self.db.execute(stmt)
        active = result.scalars().first()
        if active:
            await self.set_primary_instance_for_student(student, active.id)
            return

        ctx = dict(therapy_instance.context_data or {})
        initial = {
            "source": "after_start_therapy_complete",
            "parent_start_therapy_instance_id": str(therapy_instance.id),
            **{k: ctx[k] for k in ("therapist_id", "weekly_sessions") if k in ctx},
        }

        service = ProcessService(self.db)
        actor_id = await self._resolve_system_actor_id(therapy_instance.started_by)
        try:
            pay = await service.start_process_for_student(
                process_code="session_payment",
                student_id=student.id,
                actor_id=actor_id,
                actor_role="system",
                initial_context=initial,
            )
        except Exception:
            logger.exception(
                "maybe_start_session_payment_after_start_therapy: session_payment failed for student %s",
                student.id,
            )
            return

        await self.db.flush()
        await self.set_primary_instance_for_student(student, pay.id)

    async def update_therapy_status(self, student_id: uuid.UUID, started: bool):
        """Update the therapy_started status of a student."""
        stmt = select(Student).where(Student.id == student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if student:
            student.therapy_started = started

    async def update_intern_status(self, student_id: uuid.UUID, is_intern: bool):
        """Update the intern status of a student."""
        stmt = select(Student).where(Student.id == student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if student:
            student.is_intern = is_intern

    async def get_students_by_course_type(self, course_type: str) -> list[Student]:
        """Get all students of a specific course type."""
        stmt = select(Student).where(Student.course_type == course_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
