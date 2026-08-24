"""Student Service - Business logic for student operations."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.loader import MetadataLoader
from app.models.operational_models import ProcessInstance, StateHistory, Student, TherapySession, User
from app.services.process_service import ProcessService
from app.services.student_tracker_summary import build_roadmap_states

logger = logging.getLogger(__name__)

EXPECTED_REGISTRATION_CODE = {
    "introductory": "introductory_course_registration",
    "comprehensive": "comprehensive_course_registration",
}

REGISTRATION_PROCESS_CODES = frozenset(EXPECTED_REGISTRATION_CODE.values())

# مقادیر فرم پذیرش در metadata با برچسب فارسی هم‌نام با ثبت‌نام عمومی (کدهای انگلیسی) هستند
_EDUCATION_CODE_TO_FA = {
    "bachelor": "کارشناسی",
    "master": "کارشناسی ارشد",
    "phd": "دکتری",
    "specialist": "تخصص/فوق تخصص",
}


def _admission_form_seed_context(user: User, student: Student) -> dict:
    """
    پر کردن context نمونهٔ فرایند ثبت‌نام با داده‌هایی که از همان مرحلهٔ ثبت‌نام وب‌سایت
    در User / Student ذخیره شده‌اند تا در پنل فرم پذیرش خالی نباشد.
    """
    extra = StateMachineEngine._as_mapping(student.extra_data) if student and student.extra_data else {}
    out: dict = {"source": "auto_start_on_registration"}
    fn = (user.full_name_fa or "").strip()
    if fn:
        out["full_name"] = fn
    ph = (user.phone or "").strip()
    if ph:
        out["phone"] = ph
    em = (user.email or "").strip()
    if em:
        out["email"] = em
    raw_el = extra.get("education_level")
    if raw_el is not None and str(raw_el).strip():
        s = str(raw_el).strip()
        out["education_level"] = _EDUCATION_CODE_TO_FA.get(s, s)
    fos = extra.get("field_of_study")
    if fos is not None and str(fos).strip():
        out["field_of_study"] = str(fos).strip()
    mot = extra.get("motivation")
    if mot is not None and str(mot).strip():
        out["motivation"] = str(mot).strip()
    nc = extra.get("national_code")
    if nc is not None and str(nc).strip():
        out["national_code"] = str(nc).strip()
    hp = extra.get("home_phone")
    if hp is not None and str(hp).strip():
        out["home_phone"] = str(hp).strip()
    wp = extra.get("work_phone")
    if wp is not None and str(wp).strip():
        out["work_phone"] = str(wp).strip()
    for key in (
        "first_name_fa",
        "last_name_fa",
        "age",
        "birth_certificate_number",
        "birth_date",
        "residence_city",
        "home_address",
        "work_address",
        "had_psychotherapy",
        "psychotherapy_approach",
        "psychotherapy_therapist_name",
        "psychotherapy_total_hours",
        "used_psychiatric_meds",
        "psychiatric_hospitalization_history",
        "has_work_permit",
        "work_permit_issuer",
        "work_permit_type",
        "has_university_degree",
        "university",
        "graduation_year",
        "course_participation_mode",
        "referral_source",
        "referral_inviter_name",
    ):
        val = extra.get(key)
        if val is not None and str(val).strip():
            out[key] = str(val).strip()
    return out


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

    async def _registration_completed_for_student(self, student: Student) -> bool:
        expected = EXPECTED_REGISTRATION_CODE.get((student.course_type or "").strip().lower())
        if not expected:
            return False
        stmt = (
            select(ProcessInstance.id)
            .where(
                ProcessInstance.student_id == student.id,
                ProcessInstance.process_code == expected,
                ProcessInstance.is_completed.is_(True),
                ProcessInstance.is_cancelled.is_(False),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def _registration_state_rank(self, process_code: str, state_code: Optional[str]) -> int:
        if not state_code:
            return -1
        loader = MetadataLoader(self.db)
        definition = await loader.load_process(process_code)
        if not definition:
            return -1
        roadmap = build_roadmap_states(definition)
        codes = [s.get("code") for s in roadmap if s.get("code")]
        try:
            return codes.index(state_code)
        except ValueError:
            return -1

    async def pick_best_active_registration_instance(
        self,
        student_id: uuid.UUID,
        process_code: str,
    ) -> Optional[ProcessInstance]:
        """بین چند نمونهٔ فعال ثبت‌نام، پیشرفته‌ترین را برمی‌گرداند."""
        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student_id,
            ProcessInstance.process_code == process_code,
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]

        ranked: list[tuple[int, datetime, ProcessInstance]] = []
        for inst in rows:
            rank = await self._registration_state_rank(process_code, inst.current_state_code)
            activity = inst.last_transition_at or inst.started_at or datetime.min.replace(tzinfo=timezone.utc)
            ranked.append((rank, activity, inst))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return ranked[0][2]

    async def ensure_primary_registration_path(self, student: Student, actor: User) -> bool:
        """
        If primary_instance_id is missing or invalid, attach an existing registration
        instance or start the initial registration process (same as post-registration).

        While registration is still in progress, always prefer the most advanced active
        registration instance so re-login does not jump back to a newer empty duplicate.

        Returns True if student.extra_data was updated (caller should commit).
        """
        if not student or not actor:
            return False
        expected = EXPECTED_REGISTRATION_CODE.get((student.course_type or "").strip().lower())
        if not expected:
            return False

        registration_done = await self._registration_completed_for_student(student)
        best_active = (
            await self.pick_best_active_registration_instance(student.id, expected)
            if not registration_done
            else None
        )

        extra = dict(StateMachineEngine._as_mapping(student.extra_data))
        pid_str = extra.get("primary_instance_id")
        current_primary: Optional[ProcessInstance] = None

        if pid_str:
            try:
                pid = uuid.UUID(str(pid_str))
            except ValueError:
                pid = None
            if pid:
                current_primary = (
                    await self.db.execute(select(ProcessInstance).where(ProcessInstance.id == pid))
                ).scalars().first()
                if current_primary and current_primary.student_id != student.id:
                    current_primary = None

        if not registration_done and best_active:
            if current_primary and current_primary.id == best_active.id:
                return False
            await self.set_primary_instance_for_student(student, best_active.id)
            return True

        if current_primary:
            return False

        if pid_str:
            extra = dict(StateMachineEngine._as_mapping(student.extra_data))
            extra.pop("primary_instance_id", None)
            student.extra_data = extra
            flag_modified(student, "extra_data")

        stmt = (
            select(ProcessInstance)
            .where(
                ProcessInstance.student_id == student.id,
                ProcessInstance.process_code == expected,
            )
            .order_by(ProcessInstance.started_at.desc())
        )
        rows = list((await self.db.execute(stmt)).scalars().all())

        chosen: Optional[ProcessInstance] = None
        if rows:
            chosen = await self.pick_best_active_registration_instance(student.id, expected)
            if chosen is None:
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
        extra = dict(StateMachineEngine._as_mapping(student.extra_data))
        extra["primary_instance_id"] = str(instance_id)
        student.extra_data = extra
        flag_modified(student, "extra_data")

    async def change_registration_course_type(
        self,
        student: Student,
        new_course_type: str,
        actor: User,
        reason: Optional[str] = None,
    ) -> dict:
        """
        تغییر نوع دورهٔ انتخاب‌شده در فرم اولیهٔ ثبت‌نام (آشنایی / جامع).

        فرایند ثبت‌نام نادرستِ در جریان لغو می‌شود و مسیر ثبت‌نام متناسب با دورهٔ جدید
        به primary_instance وصل یا از نو شروع می‌شود.
        """
        new_ct = (new_course_type or "").strip().lower()
        if new_ct not in ("introductory", "comprehensive"):
            raise ValueError("نوع دوره باید «آشنایی» (introductory) یا «جامع» (comprehensive) باشد.")

        old_ct = (student.course_type or "").strip().lower()
        if old_ct == new_ct:
            return {
                "changed": False,
                "course_type": new_ct,
                "previous_course_type": old_ct,
                "cancelled_instance_ids": [],
            }

        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.process_code.in_(REGISTRATION_PROCESS_CODES),
            ProcessInstance.is_completed.is_(True),
        )
        if (await self.db.execute(stmt)).scalars().first():
            raise ValueError(
                "ثبت‌نام یکی از دوره‌ها قبلاً تکمیل شده؛ تغییر نوع دوره از این مسیر مجاز نیست."
            )

        old_process = EXPECTED_REGISTRATION_CODE.get(old_ct)
        cancelled_ids: list[str] = []
        if old_process:
            active_old = await self.db.execute(
                select(ProcessInstance).where(
                    ProcessInstance.student_id == student.id,
                    ProcessInstance.process_code == old_process,
                    ProcessInstance.is_completed.is_(False),
                    ProcessInstance.is_cancelled.is_(False),
                )
            )
            for inst in active_old.scalars().all():
                inst.is_cancelled = True
                cancelled_ids.append(str(inst.id))

        student.course_type = new_ct
        extra = dict(StateMachineEngine._as_mapping(student.extra_data))
        extra.pop("primary_instance_id", None)
        history = list(extra.get("course_type_change_history") or [])
        history.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "from": old_ct,
                "to": new_ct,
                "by_user_id": str(actor.id),
                "by_role": (actor.role or "").strip().lower() or None,
                "reason": (reason or "").strip() or None,
                "cancelled_instances": cancelled_ids,
            }
        )
        extra["course_type_change_history"] = history[-20:]
        student.extra_data = extra
        flag_modified(student, "extra_data")
        await self.db.flush()

        await self.ensure_primary_registration_path(student, actor)

        return {
            "changed": True,
            "course_type": new_ct,
            "previous_course_type": old_ct,
            "cancelled_instance_ids": cancelled_ids,
        }

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
            from app.services.registration_readiness_service import check_intro_registration_gate

            gate = await check_intro_registration_gate(self.db)
            if not gate.allowed:
                logger.info(
                    "Deferred intro registration process for %s: %s",
                    student.student_code,
                    gate.reason_fa,
                )
                return None
        else:
            process_code = "comprehensive_course_registration"

        existing = await self.pick_best_active_registration_instance(student.id, process_code)
        if existing:
            await self.set_primary_instance_for_student(student, existing.id)
            return existing

        service = ProcessService(self.db)
        instance = await service.start_process_for_student(
            process_code=process_code,
            student_id=student.id,
            actor_id=actor.id,
            actor_role=actor.role or "student",
            initial_context=_admission_form_seed_context(actor, student),
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

    async def advance_intro_second_eligibility(
        self,
        instance_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> Optional[str]:
        """از eligibility_check با eligibility_check_result به مسیر مجاز برو."""
        engine = StateMachineEngine(self.db)
        result = await engine.execute_transition(
            instance_id=instance_id,
            trigger_event="eligibility_check_result",
            actor_id=actor_id,
            actor_role="system",
            payload=None,
        )
        if result.success:
            logger.info(
                "intro_second_semester eligibility: -> %s (instance=%s)",
                result.to_state,
                instance_id,
            )
            return result.to_state
        logger.warning(
            "intro_second eligibility_check_result failed instance=%s: %s",
            instance_id,
            result.error,
        )
        return None

    async def hydrate_admission_type(self, student: Student) -> bool:
        """اگر extra_data نوع پذیرش ندارد — یا تک‌درس در ثبت‌نام است و extra چیز دیگری است — همگام کن."""
        from app.services.admission_type_service import (
            ADMISSION_SINGLE_COURSE,
            admission_type_from_result_state,
            persist_admission_type_on_student,
            resolve_admission_type_from_context,
            normalize_admission_type,
        )

        extra = StateMachineEngine._as_mapping(student.extra_data)
        current = normalize_admission_type(extra.get("admission_type"))

        stmt = (
            select(ProcessInstance)
            .where(
                ProcessInstance.student_id == student.id,
                ProcessInstance.process_code == "introductory_course_registration",
            )
            .order_by(ProcessInstance.started_at.desc())
            .limit(1)
        )
        reg = (await self.db.execute(stmt)).scalars().first()
        if not reg:
            return False

        ctx = StateMachineEngine._as_mapping(reg.context_data)
        from_ctx = resolve_admission_type_from_context(ctx)
        result_state = None
        hist = (
            await self.db.execute(
                select(StateHistory)
                .where(StateHistory.instance_id == reg.id)
                .order_by(StateHistory.entered_at.desc())
            )
        ).scalars().all()
        for row in hist:
            found = admission_type_from_result_state(row.to_state_code)
            if found:
                result_state = row.to_state_code
                break
        derived = from_ctx or admission_type_from_result_state(
            result_state or reg.current_state_code
        )
        should_write = False
        if derived == ADMISSION_SINGLE_COURSE and current != ADMISSION_SINGLE_COURSE:
            should_write = True
        elif current is None and derived:
            should_write = True
        if not should_write:
            return False

        canonical = persist_admission_type_on_student(
            student,
            admission_type=derived,
            interview_result=ctx.get("interview_result") or ctx.get("result"),
            result_state=result_state or reg.current_state_code,
        )
        return bool(canonical)

    async def reconcile_start_therapy_for_admission(self, student: Student) -> bool:
        """نمونهٔ start_therapy را با نوع پذیرش هم‌تراز کن.

        تک‌درس: نمونهٔ فعال لغو می‌شود و از مسیر اصلی برداشته می‌شود.
        مشروط: تا وقتی دانشجو از کارت اختیاری شروع نکرده، primary به درمان نمی‌چسبد.
        """
        from app.services.admission_type_service import (
            ADMISSION_CONDITIONAL_THERAPY,
            ADMISSION_SINGLE_COURSE,
            SINGLE_COURSE_NO_START_THERAPY_FA,
            normalize_admission_type,
        )

        changed = await self.hydrate_admission_type(student)
        extra = dict(StateMachineEngine._as_mapping(student.extra_data))
        admission = normalize_admission_type(extra.get("admission_type"))

        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.process_code == "start_therapy",
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        active_rows = list((await self.db.execute(stmt)).scalars().all())
        pid_raw = extra.get("primary_instance_id")

        def _lookup_uuid(raw):
            try:
                return uuid.UUID(str(raw))
            except (TypeError, ValueError):
                return None

        if admission == ADMISSION_SINGLE_COURSE:
            now = datetime.now(timezone.utc)
            for inst in active_rows:
                live = inst
                if live.current_state_code == "eligibility_check":
                    actor_id = await self._resolve_system_actor_id(live.started_by)
                    await self._advance_start_therapy_eligibility(live.id, actor_id)
                    live = await StateMachineEngine(self.db).get_process_instance(live.id)
                if (
                    live
                    and not live.is_completed
                    and not live.is_cancelled
                    and live.current_state_code not in self._START_THERAPY_TERMINAL
                ):
                    ctx = dict(StateMachineEngine._as_mapping(live.context_data))
                    ctx["cancelled_reason"] = "single_course_admission"
                    ctx["student_next_action_fa"] = SINGLE_COURSE_NO_START_THERAPY_FA
                    live.is_cancelled = True
                    live.last_transition_at = now
                    live.context_data = ctx
                    flag_modified(live, "context_data")
                    changed = True
                if pid_raw and live and str(pid_raw) == str(live.id):
                    extra.pop("primary_instance_id", None)
                    pid_raw = None
                    changed = True
            if changed:
                student.extra_data = extra
                flag_modified(student, "extra_data")
            return changed

        if admission == ADMISSION_CONDITIONAL_THERAPY and not extra.get(
            "conditional_therapy_start_opted_in"
        ):
            if pid_raw:
                primary_inst = next(
                    (i for i in active_rows if str(i.id) == str(pid_raw)),
                    None,
                )
                if primary_inst is None:
                    uid = _lookup_uuid(pid_raw)
                    if uid is not None:
                        primary_inst = (
                            await self.db.execute(
                                select(ProcessInstance).where(ProcessInstance.id == uid)
                            )
                        ).scalars().first()
                src = ""
                if primary_inst is not None:
                    src = str(
                        StateMachineEngine._as_mapping(primary_inst.context_data).get("source") or ""
                    )
                if (
                    primary_inst is not None
                    and primary_inst.process_code == "start_therapy"
                    and src != "conditional_therapy_card_ensure"
                ):
                    extra.pop("primary_instance_id", None)
                    student.extra_data = extra
                    flag_modified(student, "extra_data")
                    changed = True
            return changed

        return changed

    async def maybe_start_followup_after_intro_registration(
        self,
        registration_instance: ProcessInstance,
    ) -> None:
        """
        پس از تکمیل ثبت‌نام دوره آشنایی (registration_complete):

        - تک‌درس: مسیر درمان موضوعیت ندارد — start_therapy ساخته نمی‌شود.
        - مشروط به درمان: درمان الان اجباری نیست؛ فقط یادآوری مهلت ترم دوم (SMS/hint).
          دانشجو از کارت اختیاری ensure می‌تواند start_therapy را شروع کند.
        - پذیرش کامل: فرایند «آغاز درمان آموزشی» را در صورت نبودن نمونهٔ فعال باز می‌کند،
          از مرحلهٔ بررسی صلاحیت عبور می‌دهد و primary_instance_id را می‌چسباند.
        """
        if registration_instance.process_code != "introductory_course_registration":
            return
        if registration_instance.current_state_code != "registration_complete":
            return
        if not registration_instance.is_completed:
            return

        from app.services.admission_type_service import (
            ADMISSION_CONDITIONAL_THERAPY,
            ADMISSION_SINGLE_COURSE,
            CONDITIONAL_THERAPY_TERM2_NOTICE_FA,
            normalize_admission_type,
            persist_admission_type_on_student,
            resolve_admission_type_from_context,
            should_auto_start_educational_therapy,
        )

        stmt = select(Student).where(Student.id == registration_instance.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return

        ctx = dict(StateMachineEngine._as_mapping(registration_instance.context_data))
        extra = StateMachineEngine._as_mapping(student.extra_data)
        admission = (
            normalize_admission_type(extra.get("admission_type"))
            or resolve_admission_type_from_context(ctx)
        )
        if admission:
            persist_admission_type_on_student(
                student,
                admission_type=admission,
                interview_result=ctx.get("interview_result") or admission,
            )
        else:
            await self.hydrate_admission_type(student)
            extra = StateMachineEngine._as_mapping(student.extra_data)
            admission = normalize_admission_type(extra.get("admission_type"))

        # —— تک‌درس: بدون مسیر درمان ——
        if admission == ADMISSION_SINGLE_COURSE:
            reg_ctx = dict(ctx)
            reg_ctx["intro_registration_next_step_fa"] = (
                "ثبت‌نام دوره آشنایی تکمیل شد. پذیرش شما تک‌درس است و مسیر "
                "آغاز درمان آموزشی برای شما فعال نمی‌شود؛ ادامه از پنل دروس و کلاس‌ها."
            )
            registration_instance.context_data = reg_ctx
            flag_modified(registration_instance, "context_data")
            await self.reconcile_start_therapy_for_admission(student)
            return

        # —— مشروط: یادآوری مهلت بدون اجبار start_therapy / دزدیدن primary ——
        if admission == ADMISSION_CONDITIONAL_THERAPY:
            reg_ctx = dict(ctx)
            reg_ctx["intro_registration_next_step_fa"] = CONDITIONAL_THERAPY_TERM2_NOTICE_FA
            registration_instance.context_data = reg_ctx
            flag_modified(registration_instance, "context_data")
            await self._notify_conditional_therapy_deadline_after_registration(
                student, registration_instance
            )
            await self.reconcile_start_therapy_for_admission(student)
            return

        if not should_auto_start_educational_therapy(admission, student.course_type):
            await self.reconcile_start_therapy_for_admission(student)
            return

        # —— پذیرش کامل: زنجیرهٔ فعلی start_therapy ——
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
            await self._notify_conditional_therapy_deadline_after_registration(
                student, registration_instance
            )
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
            await self._notify_conditional_therapy_deadline_after_registration(
                student, registration_instance
            )
            return

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

        reg_ctx = dict(StateMachineEngine._as_mapping(registration_instance.context_data))
        reg_ctx["intro_registration_next_step_fa"] = (
            "ثبت‌نام دوره آشنایی تکمیل شد. گام بعدی مسیر شما «آغاز درمان آموزشی» است؛ "
            "مسیر اصلی پرتال به این فرایند منتقل شده است."
        )
        registration_instance.context_data = reg_ctx
        flag_modified(registration_instance, "context_data")

        await self._notify_conditional_therapy_deadline_after_registration(
            student, registration_instance
        )

    async def _notify_conditional_therapy_deadline_after_registration(
        self,
        student: Student,
        registration_instance: ProcessInstance,
    ) -> None:
        """SMS مهلت آغاز درمان برای پذیرش مشروط — یک‌بار پس از registration_complete."""
        from app.services.admission_type_service import (
            ADMISSION_CONDITIONAL_THERAPY,
            normalize_admission_type,
            persist_admission_type_on_student,
            resolve_admission_type_from_context,
            therapy_deadline_hint_fa,
        )
        from app.services.manual_process_start_notification import _student_phone
        from app.services.notification_service import notification_service

        ctx = StateMachineEngine._as_mapping(registration_instance.context_data)
        extra = StateMachineEngine._as_mapping(student.extra_data)
        admission = (
            normalize_admission_type(extra.get("admission_type"))
            or resolve_admission_type_from_context(ctx)
        )
        if admission:
            persist_admission_type_on_student(
                student,
                admission_type=admission,
                interview_result=ctx.get("interview_result") or admission,
            )
        if admission != ADMISSION_CONDITIONAL_THERAPY:
            return
        if student.therapy_started:
            return
        if extra.get("conditional_therapy_deadline_sms_sent"):
            return

        phone = await _student_phone(self.db, student.id)
        if not phone:
            logger.info(
                "conditional therapy deadline SMS skipped (no phone) student=%s",
                student.id,
            )
            return
        try:
            await notification_service.send_notification(
                "sms",
                "conditional_therapy_deadline_after_registration",
                phone,
                {"deadline": ctx.get("term2_start_hint") or ""},
            )
        except Exception:
            logger.exception(
                "conditional therapy deadline SMS failed student=%s",
                student.id,
            )
            return

        extra = StateMachineEngine._as_mapping(student.extra_data)
        extra["conditional_therapy_deadline_sms_sent"] = True
        extra["conditional_therapy_deadline_hint_fa"] = therapy_deadline_hint_fa(
            deadline=ctx.get("term2_start_hint")
        )
        student.extra_data = extra
        flag_modified(student, "extra_data")

    def _mark_conditional_therapy_opted_in(self, student: Student) -> None:
        extra = dict(StateMachineEngine._as_mapping(student.extra_data))
        extra["conditional_therapy_start_opted_in"] = True
        student.extra_data = extra
        flag_modified(student, "extra_data")

    async def ensure_conditional_start_therapy(
        self,
        student: Student,
        actor_id: uuid.UUID,
    ) -> dict:
        """
        برای دانشجوی مشروط: نمونهٔ فعال start_therapy را ensure کند و primary را بچسباند.
        """
        from app.services.admission_type_service import (
            ADMISSION_CONDITIONAL_THERAPY,
            normalize_admission_type,
            resolve_admission_type_from_context,
        )

        extra = StateMachineEngine._as_mapping(student.extra_data)
        admission = normalize_admission_type(extra.get("admission_type"))
        if admission != ADMISSION_CONDITIONAL_THERAPY:
            await self.hydrate_admission_type(student)
            extra = StateMachineEngine._as_mapping(student.extra_data)
            admission = normalize_admission_type(extra.get("admission_type"))
        if admission != ADMISSION_CONDITIONAL_THERAPY:
            # try recover from latest intro registration context
            stmt = (
                select(ProcessInstance)
                .where(
                    ProcessInstance.student_id == student.id,
                    ProcessInstance.process_code == "introductory_course_registration",
                )
                .order_by(ProcessInstance.started_at.desc())
                .limit(1)
            )
            reg = (await self.db.execute(stmt)).scalars().first()
            if reg:
                admission = resolve_admission_type_from_context(
                    StateMachineEngine._as_mapping(reg.context_data)
                )
            if admission != ADMISSION_CONDITIONAL_THERAPY:
                return {
                    "ok": False,
                    "error": "only_conditional",
                    "detail_fa": "این اقدام فقط برای دانشجویان با پذیرش مشروط به درمان است.",
                }

        if student.therapy_started:
            return {
                "ok": False,
                "error": "therapy_already_started",
                "detail_fa": "درمان آموزشی شما قبلاً آغاز شده است.",
            }

        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.process_code == "start_therapy",
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        active = (await self.db.execute(stmt)).scalars().first()
        if active:
            if active.current_state_code == "eligibility_check":
                await self._advance_start_therapy_eligibility(active.id, actor_id)
                active = await StateMachineEngine(self.db).get_process_instance(active.id)
            await self.set_primary_instance_for_student(student, active.id)
            self._mark_conditional_therapy_opted_in(student)
            return {
                "ok": True,
                "already_existed": True,
                "instance_id": str(active.id),
                "current_state": active.current_state_code,
                "process_code": "start_therapy",
            }

        initial = {
            "source": "conditional_therapy_card_ensure",
            "admission_type": ADMISSION_CONDITIONAL_THERAPY,
            "interview_result": ADMISSION_CONDITIONAL_THERAPY,
        }
        service = ProcessService(self.db)
        try:
            sub = await service.start_process_for_student(
                process_code="start_therapy",
                student_id=student.id,
                actor_id=actor_id,
                actor_role="system",
                initial_context=initial,
            )
        except Exception as e:
            logger.exception("ensure_conditional_start_therapy failed student=%s", student.id)
            return {
                "ok": False,
                "error": "start_failed",
                "detail_fa": f"شروع فرایند آغاز درمان ممکن نشد: {e}",
            }

        await self.db.flush()
        await self._advance_start_therapy_eligibility(sub.id, actor_id)
        sub = await StateMachineEngine(self.db).get_process_instance(sub.id)
        await self.set_primary_instance_for_student(student, sub.id)
        self._mark_conditional_therapy_opted_in(student)
        return {
            "ok": True,
            "already_existed": False,
            "instance_id": str(sub.id),
            "current_state": sub.current_state_code,
            "process_code": "start_therapy",
        }

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
            therapy_ctx = dict(StateMachineEngine._as_mapping(therapy_instance.context_data))
            therapy_ctx["start_therapy_next_step_fa"] = (
                "درمان آموزشی فعال شد. گام بعدی مسیر شما «پرداخت جلسات آتی» است؛ "
                "مسیر اصلی پرتال به این فرایند منتقل شده است."
            )
            therapy_instance.context_data = therapy_ctx
            flag_modified(therapy_instance, "context_data")
            return

        ctx = dict(StateMachineEngine._as_mapping(therapy_instance.context_data))
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

        therapy_ctx = dict(StateMachineEngine._as_mapping(therapy_instance.context_data))
        therapy_ctx["start_therapy_next_step_fa"] = (
            "درمان آموزشی فعال شد. گام بعدی مسیر شما «پرداخت جلسات آتی» است؛ "
            "مسیر اصلی پرتال به این فرایند منتقل شده است."
        )
        therapy_instance.context_data = therapy_ctx
        flag_modified(therapy_instance, "context_data")

    _SESSION_PAYMENT_NEXT_STEP_FA = (
        "پرداخت جلسات ثبت شد. برای شرکت در جلسات به تب «جلسات آنلاین» بروید. "
        "جلسات تا پایان ترم در تقویم شما ثبت شده‌اند؛ برای جلسات unpaid بعدی دوباره "
        "«پرداخت جلسات» را باز کنید. پس از تکمیل حدنصاب ساعات، از «خاتمه درمان آموزشی» استفاده کنید."
    )

    _PRIMARY_PRIORITY = (
        "educational_leave",
        "session_payment",
        "extra_session",
        "start_therapy",
        "attendance_tracking",
        "therapy_session_increase",
        "therapy_session_reduction",
        "therapy_interruption",
        "student_session_cancellation",
    )

    async def repoint_primary_after_session_payment_completed(self, completed: ProcessInstance) -> None:
        """
        پس از پایان موفق session_payment (payment_confirmed)، اگر primary_instance_id همان نمونهٔ تمام‌شده است،
        به نمونهٔ فعال دیگر اشاره کن؛ در غیر این صورت primary را خالی کن و راهنمای داشبورد بگذار.
        """
        if completed.process_code != "session_payment":
            return
        if completed.current_state_code != "payment_confirmed" or not completed.is_completed:
            return

        stmt = select(Student).where(Student.id == completed.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return

        extra = dict(StateMachineEngine._as_mapping(student.extra_data))
        pid_raw = extra.get("primary_instance_id")
        if not pid_raw or str(pid_raw) != str(completed.id):
            return

        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        result = await self.db.execute(stmt)
        active = [p for p in result.scalars().all() if p.process_code != "fee_determination"]
        if active:
            rank = {c: i for i, c in enumerate(self._PRIMARY_PRIORITY)}
            active.sort(key=lambda p: (rank.get(p.process_code, 50), p.started_at or completed.started_at))
            await self.set_primary_instance_for_student(student, active[0].id)
            extra = dict(StateMachineEngine._as_mapping(student.extra_data))
            extra.pop("dashboard_therapy_hint_fa", None)
            student.extra_data = extra
            flag_modified(student, "extra_data")
            return

        extra.pop("primary_instance_id", None)
        extra["dashboard_therapy_hint_fa"] = self._SESSION_PAYMENT_NEXT_STEP_FA
        completed_ctx = dict(StateMachineEngine._as_mapping(completed.context_data))
        completed_ctx["session_payment_next_step_fa"] = self._SESSION_PAYMENT_NEXT_STEP_FA
        completed.context_data = completed_ctx
        flag_modified(completed, "context_data")
        student.extra_data = extra
        flag_modified(student, "extra_data")

    async def repoint_primary_after_therapy_completion_terminal(self, completed: ProcessInstance) -> None:
        """
        پس از پایان فرایند therapy_completion (هر دو شاخهٔ پایانی)، اگر primary به همین نمونه اشاره می‌کرد،
        به نمونهٔ فعال دیگر بچسبان یا primary را خالی کن و راهنمای داشبورد بگذار.
        """
        if completed.process_code != "therapy_completion":
            return
        if completed.current_state_code not in ("therapy_completed", "conditions_not_met"):
            return
        if not completed.is_completed:
            return

        stmt = select(Student).where(Student.id == completed.student_id)
        result = await self.db.execute(stmt)
        student = result.scalars().first()
        if not student:
            return

        extra = dict(StateMachineEngine._as_mapping(student.extra_data))
        pid_raw = extra.get("primary_instance_id")
        if pid_raw and str(pid_raw) != str(completed.id):
            return

        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        result = await self.db.execute(stmt)
        active = [p for p in result.scalars().all() if p.process_code != "fee_determination"]
        if active:
            rank = {c: i for i, c in enumerate(self._PRIMARY_PRIORITY)}
            active.sort(key=lambda p: (rank.get(p.process_code, 50), p.started_at or completed.started_at))
            await self.set_primary_instance_for_student(student, active[0].id)
            extra = dict(StateMachineEngine._as_mapping(student.extra_data))
            extra.pop("dashboard_therapy_hint_fa", None)
            student.extra_data = extra
            flag_modified(student, "extra_data")
            return

        extra.pop("primary_instance_id", None)
        if completed.current_state_code == "therapy_completed":
            extra["dashboard_therapy_hint_fa"] = (
                "درمان آموزشی شما با موفقیت خاتمه یافت. مسیر سوپرویژن، دروس و کارورزی را از داشبورد و فازهای مربوط دنبال کنید."
            )
        else:
            extra["dashboard_therapy_hint_fa"] = (
                "در حال حاضر همهٔ حدنصاب‌های لازم برای خاتمهٔ رسمی درمان تکمیل نشده است. پس از تکمیل ساعات، "
                "دوباره همین فرایند را از بخش فرایندها اجرا کنید."
            )
        student.extra_data = extra
        flag_modified(student, "extra_data")

    async def count_unpaid_therapy_sessions(self, student_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(TherapySession).where(
            TherapySession.student_id == student_id,
            TherapySession.payment_status == "pending",
            TherapySession.status.in_(["scheduled", "completed"]),
        )
        r = await self.db.execute(stmt)
        return int(r.scalar() or 0)

    async def ensure_active_session_payment_for_student(
        self, student_id: uuid.UUID
    ) -> dict:
        """اگر جلسه unpaid و بدون نمونهٔ فعال session_payment باشد، یکی باز کن و primary را بچسبان."""
        stu = await self.db.get(Student, student_id)
        if not stu or not stu.therapy_started:
            return {"started": False, "reason": "not_eligible"}

        stmt = select(ProcessInstance).where(
            ProcessInstance.student_id == student_id,
            ProcessInstance.process_code == "session_payment",
            ProcessInstance.is_completed == False,
            ProcessInstance.is_cancelled == False,
        )
        active = (await self.db.execute(stmt)).scalars().first()
        if active:
            await self.set_primary_instance_for_student(stu, active.id)
            return {"started": False, "reason": "already_active", "instance_id": str(active.id)}

        unpaid = await self.count_unpaid_therapy_sessions(student_id)
        if unpaid <= 0:
            return {"started": False, "reason": "no_unpaid", "unpaid": 0}

        service = ProcessService(self.db)
        actor_id = await self._resolve_system_actor_id(None)
        try:
            pay = await service.start_process_for_student(
                process_code="session_payment",
                student_id=student_id,
                actor_id=actor_id,
                actor_role="system",
                initial_context={
                    "source": "repair_therapy_continuity",
                    "unpaid_sessions_count": unpaid,
                },
            )
        except Exception:
            logger.exception(
                "ensure_active_session_payment_for_student failed student=%s", student_id
            )
            return {"started": False, "reason": "start_failed"}

        await self.db.flush()
        await self.set_primary_instance_for_student(stu, pay.id)
        return {"started": True, "instance_id": str(pay.id), "unpaid": unpaid}

    async def maybe_ensure_session_payment_for_unpaid_sessions(self) -> list[dict]:
        """
        اگر دانشجویی درمان شروع کرده، جلسهٔ درمان بدون پرداخت دارد و نمونهٔ فعال session_payment ندارد،
        نمونهٔ جدید باز می‌کند و در صورت primary خالی یا اشاره به فرایند تمام‌شده، primary را به آن می‌چسباند.
        """
        from app.services.therapy_session_schedule import ensure_therapy_sessions_until_term_end

        # ابتدا تقویم جلسات تا پایان ترم را برای دانشجویان با درمان فعال تکمیل کن
        started_stmt = select(Student.id).where(Student.therapy_started.is_(True))
        started_ids = list((await self.db.execute(started_stmt)).scalars().all())
        for sid in started_ids:
            try:
                await ensure_therapy_sessions_until_term_end(self.db, sid)
            except Exception:
                logger.exception(
                    "ensure_therapy_sessions_until_term_end failed student=%s", sid
                )

        out: list[dict] = []
        for sid in started_ids:
            try:
                res = await self.ensure_active_session_payment_for_student(sid)
            except Exception:
                logger.exception(
                    "ensure_active_session_payment_for_student failed student=%s", sid
                )
                continue
            if res.get("started"):
                out.append({"student_id": str(sid), "instance_id": res.get("instance_id")})
        return out

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
