"""Test winter_semester_preparation as جریان بزرگ (BUILD_TODO item ۱۶ — ه: آماده‌سازی ترم زمستان)."""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine, UnauthorizedError
from app.meta.seed import load_process
from app.meta.student_step_forms import apply_register_to_context
from app.models.operational_models import InstituteCalendar, InterviewSlot
from app.services.interview_slot_service import (
    apply_semester_prep_interview_defaults_to_open_slots,
    interview_mode_fa_to_slot_mode,
    resolve_semester_prep_interview_location,
)


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"

WINTER_COURSE_ROW = {
    "course_name": "عملی زمستان",
    "track": "جامع",
    "proposed_day": "دوشنبه",
    "proposed_time": "17:30",
    "instructor": "دکتر ب",
    "teaching_assistant": "",
}

CALENDAR_CTX = {
    "fall_start_date": "2026-09-15",
    "fall_end_date": "2026-12-20",
    "winter_start_date": "2027-01-10",
    "winter_end_date": "2027-04-15",
    "registration_payment_window_start": "2026-08-01",
    "registration_payment_window_end": "2026-09-01",
    "intern_interview_deadline": "2026-11-01",
    "teaching_assistant_interview_deadline": "2026-11-15",
    "nowruz_holiday_start": "2027-03-20",
    "nowruz_holiday_end": "2027-04-05",
    "winter_break_periods": [{"start": "2027-02-20", "end": "2027-02-25"}],
}


async def _load_winter(db_session: AsyncSession) -> None:
    await load_process(db_session, PROCESSES_DIR / "winter_semester_preparation.json")
    await db_session.commit()


async def _start_winter(
    db_session: AsyncSession, sample_student, sample_user, *, actor_role: str = "admin"
):
    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="winter_semester_preparation",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role=actor_role,
    )
    await db_session.commit()
    return engine, instance



@pytest.mark.asyncio
class TestWinterSemesterPreparationFlow:

    async def test_winter_semester_preparation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند آماده‌سازی ترم زمستان لود و استارت می‌شود؛ state اول license_check است."""
        process_file = PROCESSES_DIR / "winter_semester_preparation.json"
        assert process_file.exists()

        await _load_winter(db_session)
        _, instance = await _start_winter(db_session, sample_student, sample_user)

        assert instance.process_code == "winter_semester_preparation"
        assert instance.current_state_code == "license_check"
        assert instance.is_completed is False

    async def test_winter_semester_preparation_full_flow_to_published(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان کامل: license_check → ... → published (با نقش admin برای همه transitionها)."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        triggers = [
            "license_reviewed",
            "course_list_reviewed",
            "courses_finalized",
            "marketing_started",
            "interviewers_assigned",
            "interview_times_set",
        ]
        for trigger in triggers:
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role="admin",
            )
            await db_session.commit()
            assert result.success is True, f"transition {trigger} failed: {result.error}"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "published"
        assert instance.is_completed is True

    async def test_deputy_education_can_review_license_step(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """نقش پنل deputy_education باید بتواند license_reviewed را اجرا کند (RBAC فرایند ۳۰)."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="license_reviewed",
            actor_id=sample_user.id,
            actor_role="deputy_education",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "course_list_review"

    async def test_deputy_education_cannot_submit_course_list_review(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """معاون آموزش نباید مرحلهٔ بازبینی لیست دروس (کمیته دروس) را ثبت کند."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="license_reviewed",
            actor_id=sample_user.id,
            actor_role="deputy_education",
        )
        await db_session.commit()
        assert result.success is True

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "course_list_review"

        transitions = await engine.get_available_transitions(instance.id, "deputy_education")
        assert "course_list_reviewed" not in [t["trigger_event"] for t in transitions]

        with pytest.raises(UnauthorizedError):
            await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="course_list_reviewed",
                actor_id=sample_user.id,
                actor_role="deputy_education",
            )

    async def test_course_committee_portal_role_can_advance_course_list_review(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """نقش پنل course_committee باید بتواند course_list_review را جلو ببرد."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="license_reviewed",
            actor_id=sample_user.id,
            actor_role="deputy_education",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(instance.id, "course_committee")
        assert "course_list_reviewed" in [t["trigger_event"] for t in transitions]

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="course_list_reviewed",
            actor_id=sample_user.id,
            actor_role="course_committee",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "course_finalization"

    async def test_course_finalization_only_course_committee_can_advance(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """مرحلهٔ نهایی‌سازی مکان‌ها فقط برای کمیته دروس (نه معاون آموزش)."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        for trigger, role in (
            ("license_reviewed", "deputy_education"),
            ("course_list_reviewed", "course_committee"),
        ):
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role=role,
            )
            await db_session.commit()
            assert result.success is True, f"{trigger} failed: {result.error}"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "course_finalization"

        deputy_transitions = await engine.get_available_transitions(instance.id, "deputy_education")
        assert "courses_finalized" not in [t["trigger_event"] for t in deputy_transitions]

        committee_transitions = await engine.get_available_transitions(instance.id, "course_committee")
        assert "courses_finalized" in [t["trigger_event"] for t in committee_transitions]

    async def test_course_finalization_prefills_from_course_list_on_transition(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """ورود به course_finalization باید جدول نهایی را از لیست دروس مرحلهٔ قبل پر کند."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="license_reviewed",
            actor_id=sample_user.id,
            actor_role="deputy_education",
        )
        await db_session.commit()

        instance = await engine.get_process_instance(instance.id)
        ctx = dict(instance.context_data or {})
        ctx["courses"] = [WINTER_COURSE_ROW]
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="course_list_reviewed",
            actor_id=sample_user.id,
            actor_role="course_committee",
        )
        await db_session.commit()
        assert result.success is True, result.error

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "course_finalization"
        out = instance.context_data or {}
        assert out["courses_finalized"][0]["course_name"] == "عملی زمستان"
        assert out["courses_finalized"][0]["day"] == "دوشنبه"

    async def test_sla_expired_records_warning_for_education_director(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """گذشتن مهلت مرحلهٔ license_check باید هشدار برای «مدیر آموزش» را در context ثبت کند."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="sla_expired",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True

        instance = await engine.get_process_instance(instance.id)
        log = (instance.context_data or {}).get("__sla_warning_log") or []
        assert len(log) >= 1
        roles = {
            r.get("recipient_role")
            for entry in log
            for r in (entry.get("recipients") or [])
        }
        assert "education_director" in roles

        from app.services.semester_prep_service import _extract_sla_warning_rows

        rows = _extract_sla_warning_rows(instance, "winter_semester_preparation")
        assert any(
            any(rec.get("role_fa") == "مدیر آموزش" for rec in row["recipients"])
            for row in rows
        )

    async def test_winter_semester_preparation_publish_merges_institute_calendar(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """پس از انتشار زمستان، تقویم فعال با فیلدهای زمستان به‌روز می‌شود."""
        from app.models.operational_models import ProcessInstance

        await load_process(db_session, PROCESSES_DIR / "fall_semester_preparation.json")
        await _load_winter(db_session)

        now = datetime.now(timezone.utc)
        fall_instance = ProcessInstance(
            id=uuid.uuid4(),
            student_id=sample_student.id,
            process_code="fall_semester_preparation",
            current_state_code="published",
            is_completed=True,
            is_cancelled=False,
            started_at=now - timedelta(days=90),
            completed_at=now - timedelta(days=60),
            context_data=dict(CALENDAR_CTX),
        )
        db_session.add(fall_instance)

        from app.services.institute_calendar_service import publish_calendar_from_instance_context

        await publish_calendar_from_instance_context(db_session, fall_instance, CALENDAR_CTX)
        await db_session.commit()

        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        triggers = [
            "license_reviewed",
            "course_list_reviewed",
            "courses_finalized",
            "marketing_started",
            "interviewers_assigned",
            "interview_times_set",
        ]
        for trigger in triggers:
            if trigger == "interview_times_set":
                inst = await engine.get_process_instance(instance.id)
                inst.context_data = {**(inst.context_data or {}), **CALENDAR_CTX}
                flag_modified(inst, "context_data")
                await db_session.flush()
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role="admin",
            )
            await db_session.commit()
            assert result.success is True, f"transition {trigger} failed: {result.error}"

        cal = (
            await db_session.execute(
                select(InstituteCalendar).where(InstituteCalendar.is_active.is_(True))
            )
        ).scalars().first()
        assert cal is not None
        extra = cal.extra_data or {}
        assert extra.get("winter_start_date") == "2027-01-10"
        assert extra.get("winter_end_date") == "2027-04-15"

    async def test_staff_can_complete_interview_scheduling_step(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """مدیر داخلی (staff) باید مرحلهٔ زمان‌بندی مصاحبه زمستان را به انتشار برساند."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        for trigger, role in (
            ("license_reviewed", "deputy_education"),
            ("course_list_reviewed", "course_committee"),
            ("courses_finalized", "course_committee"),
            ("marketing_started", "staff"),
            ("interviewers_assigned", "deputy_education"),
        ):
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role=role,
            )
            await db_session.commit()
            assert result.success is True, f"{trigger} failed: {result.error}"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "interview_scheduling"

        transitions = await engine.get_available_transitions(instance.id, "staff")
        assert "interview_times_set" in [t["trigger_event"] for t in transitions]

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="interview_times_set",
            actor_id=sample_user.id,
            actor_role="staff",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "published"

        instance = await engine.get_process_instance(instance.id)
        assert instance.is_completed is True

    async def test_interview_scheduling_form_values_sync_open_slots(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """ثبت فرم مرحلهٔ زمان‌بندی زمستان باید اسلات‌های آزاد را با نوع مصاحبه همگام کند."""
        await _load_winter(db_session)
        engine, instance = await _start_winter(db_session, sample_student, sample_user)

        for trigger, role in (
            ("license_reviewed", "deputy_education"),
            ("course_list_reviewed", "course_committee"),
            ("courses_finalized", "course_committee"),
            ("marketing_started", "staff"),
            ("interviewers_assigned", "deputy_education"),
        ):
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role=role,
            )
            await db_session.commit()
            assert result.success is True, result.error

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "interview_scheduling"

        t0 = datetime.now(timezone.utc) + timedelta(days=4)
        open_slot = InterviewSlot(
            id=uuid.uuid4(),
            starts_at=t0,
            ends_at=t0 + timedelta(minutes=30),
            mode="in_person",
            location_fa="قدیم",
        )
        db_session.add(open_slot)
        await db_session.flush()

        form_values = {
            "interview_mode": "آنلاین",
        }
        instance.context_data = apply_register_to_context(
            instance.context_data or {},
            "interview_scheduling",
            form_values,
        )
        slot_mode = interview_mode_fa_to_slot_mode(form_values["interview_mode"])
        await apply_semester_prep_interview_defaults_to_open_slots(
            db_session,
            mode=slot_mode,
            location_fa=resolve_semester_prep_interview_location(form_values),
        )
        await db_session.commit()
        await db_session.refresh(open_slot)

        assert open_slot.mode == "online"
        assert open_slot.location_fa is None
