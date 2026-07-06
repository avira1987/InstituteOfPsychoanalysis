"""Test fall_semester_preparation as first جریان بزرگ (BUILD_TODO section 5 — ه)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestFallSemesterPreparationFlow:

    async def test_fall_semester_preparation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند آماده‌سازی ترم پاییز لود و استارت می‌شود؛ state اول calendar_entry است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "fall_semester_preparation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="course_committee_executive",
        )
        await db_session.commit()

        assert instance.process_code == "fall_semester_preparation"
        assert instance.current_state_code == "calendar_entry"
        assert instance.is_completed is False

    async def test_fall_semester_preparation_has_forward_transition_from_calendar(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از state calendar_entry نقش course_committee_executive می‌تواند با calendar_submitted به tuition_entry برود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="course_committee_executive",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            "course_committee_executive",
        )
        trigger_events = [t["trigger_event"] for t in transitions]
        assert "calendar_submitted" in trigger_events

    async def test_fall_semester_preparation_transition_to_tuition_entry(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """اجرای transition calendar_submitted باعث رفتن به tuition_entry می‌شود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="course_committee_executive",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="calendar_submitted",
            actor_id=sample_user.id,
            actor_role="course_committee_executive",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "calendar_entry"
        assert result.to_state == "tuition_entry"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "tuition_entry"

    async def test_deputy_education_cannot_advance_calendar_step(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """معاون آموزش نباید مرحلهٔ تقویم (کمیته دروس) را ثبت کند."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        from app.core.engine import UnauthorizedError

        with pytest.raises(UnauthorizedError):
            await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="calendar_submitted",
                actor_id=sample_user.id,
                actor_role="deputy_education",
            )

    async def test_course_committee_portal_role_can_advance_calendar_step(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """نقش پنل course_committee باید بتواند مرحلهٔ calendar_entry را جلو ببرد."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            "course_committee",
        )
        assert "calendar_submitted" in [t["trigger_event"] for t in transitions]

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="calendar_submitted",
            actor_id=sample_user.id,
            actor_role="course_committee",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "tuition_entry"

    async def test_course_committee_portal_role_sees_scientific_officer_transitions(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """نقش پنل course_committee باید در course_list_creation هم transition ببیند."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        for trigger, role in (
            ("calendar_submitted", "course_committee"),
            ("tuition_submitted", "deputy_education"),
            ("license_reviewed", "deputy_education"),
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
        assert instance.current_state_code == "course_list_creation"

        transitions = await engine.get_available_transitions(
            instance.id,
            "course_committee",
        )
        assert "course_list_submitted" in [t["trigger_event"] for t in transitions]

    async def test_deputy_education_cannot_submit_course_list(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """معاون آموزش نباید مرحلهٔ لیست دروس (کمیته دروس) را ثبت کند."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        for trigger, role in (
            ("calendar_submitted", "course_committee"),
            ("tuition_submitted", "deputy_education"),
            ("license_reviewed", "deputy_education"),
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
        assert instance.current_state_code == "course_list_creation"

        transitions = await engine.get_available_transitions(
            instance.id,
            "deputy_education",
        )
        assert "course_list_submitted" not in [t["trigger_event"] for t in transitions]

        from app.core.engine import UnauthorizedError

        with pytest.raises(UnauthorizedError):
            await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="course_list_submitted",
                actor_id=sample_user.id,
                actor_role="deputy_education",
            )

    async def test_course_finalization_only_course_committee_can_advance(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """مرحلهٔ نهایی‌سازی مکان‌ها فقط برای کمیته دروس (نه معاون آموزش)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        for trigger, role in (
            ("calendar_submitted", "course_committee"),
            ("tuition_submitted", "deputy_education"),
            ("license_reviewed", "deputy_education"),
            ("course_list_submitted", "course_committee"),
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

        deputy_transitions = await engine.get_available_transitions(
            instance.id,
            "deputy_education",
        )
        assert "courses_finalized" not in [t["trigger_event"] for t in deputy_transitions]

        committee_transitions = await engine.get_available_transitions(
            instance.id,
            "course_committee",
        )
        assert "courses_finalized" in [t["trigger_event"] for t in committee_transitions]

    async def test_sla_expired_records_warning_for_education_director(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """گذشتن مهلت مرحلهٔ tuition_entry باید هشدار برای «مدیر آموزش» را در context ثبت کند."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="calendar_submitted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

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

        rows = _extract_sla_warning_rows(instance, "fall_semester_preparation")
        assert any(
            any(rec.get("role_fa") == "مدیر آموزش" for rec in row["recipients"])
            for row in rows
        )

    async def test_fall_semester_preparation_full_flow_to_published(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان کامل: calendar_entry → ... → published (با نقش admin برای همه transitionها)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        triggers = [
            "calendar_submitted",
            "tuition_submitted",
            "license_reviewed",
            "course_list_submitted",
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

    async def test_staff_can_complete_interview_scheduling_step(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """مدیر داخلی (staff) باید مرحلهٔ ۸ — زمان‌بندی مصاحبه — را به انتشار برساند."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        for trigger, role in (
            ("calendar_submitted", "course_committee"),
            ("tuition_submitted", "deputy_education"),
            ("license_reviewed", "deputy_education"),
            ("course_list_submitted", "course_committee"),
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
