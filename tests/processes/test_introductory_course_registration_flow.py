"""Test introductory_course_registration as جریان بزرگ (BUILD_TODO item ۸ — ه: سایر جریان‌های بزرگ)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from tests.helpers.registration_gate_fixture import open_intro_registration_gate


@pytest.mark.asyncio
class TestIntroductoryCourseRegistrationFlow:

    async def test_introductory_course_registration_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ثبت‌نام دوره آشنایی لود و استارت می‌شود؛ state اول application_submitted است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "introductory_course_registration.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        assert instance.process_code == "introductory_course_registration"
        assert instance.current_state_code == "application_submitted"
        assert instance.is_completed is False

    async def test_introductory_student_portal_no_manual_timeslot_trigger(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """پورتال دانشجو نباید timeslot_selected را به‌صورت دستی ببیند — فقط مسیر رزرو اسلات."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "introductory_course_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            "student",
        )
        trigger_events = [t["trigger_event"] for t in transitions]
        assert "timeslot_selected" not in trigger_events

    async def test_introductory_course_registration_transition_timeslot_selected(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """اجرای timeslot_selected باعث رفتن مستقیم به interview_payment می‌شود."""
        await open_intro_registration_gate(db_session)
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "introductory_course_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="timeslot_selected",
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "application_submitted"
        assert result.to_state == "interview_payment"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "interview_payment"

    async def test_admission_result_auto_proceeds_to_documents_upload(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """پس از ثبت نتیجهٔ پذیرش، سیستم خودکار به documents_upload و پیامک مدارک می‌رود."""
        await open_intro_registration_gate(db_session)
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "introductory_course_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        for trigger, role in [
            ("timeslot_selected", "applicant"),
            ("payment_success", "system"),
            ("interview_time_reached", "system"),
        ]:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role=role,
                payload={"selected_timeslot": "2026-05-01T10:00:00"} if trigger == "timeslot_selected" else None,
            )
            await db_session.commit()
            assert r.success, f"{trigger}: {getattr(r, 'error', None)}"

        r = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="interview_result_submitted",
            actor_id=sample_user.id,
            actor_role="interviewer",
            payload={
                "interview_result": "full_admission",
                "to_state": "result_full_admission",
                "allowed_course_count": 3,
            },
        )
        await db_session.commit()
        assert r.success, r.error

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "documents_upload"
        ctx = instance.context_data or {}
        assert ctx.get("documents_upload_deadline")

    async def test_interviewer_result_not_blocked_by_closed_gate(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """قفل ثبت‌نام (تقویم منتشرنشده) نباید ثبت نتیجهٔ مصاحبه‌گر را مسدود کند."""
        from app.core.engine import InvalidTransitionError

        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "introductory_course_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_course_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="applicant",
        )
        await db_session.commit()

        # Gate بسته است (open_intro_registration_gate صدا زده نشده) — مسیر دانشجو باید مسدود شود.
        with pytest.raises(InvalidTransitionError):
            await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="timeslot_selected",
                actor_id=sample_user.id,
                actor_role="applicant",
                payload={"selected_timeslot": "2026-05-01T10:00:00"},
            )

        # اقدام مصاحبه‌گر نباید با پیام قفل ثبت‌نام رد شود (هر خطایی غیر از gate قابل قبول است).
        try:
            await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="interview_result_submitted",
                actor_id=sample_user.id,
                actor_role="interviewer",
                payload={"interview_result": "full_admission", "to_state": "result_full_admission"},
            )
        except InvalidTransitionError as exc:
            assert "تقویم" not in str(exc), f"interviewer blocked by gate: {exc}"
