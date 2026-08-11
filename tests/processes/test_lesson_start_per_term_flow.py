"""Test lesson_start_per_term as جریان بزرگ (BUILD_TODO item ۱۵ — ه: آغاز هر درس در هر ترم)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.process_forms import get_process_forms
from app.meta.seed import load_process
from app.meta.student_step_forms import validate_student_step_forms
from app.models.operational_models import Student


@pytest.mark.asyncio
class TestLessonStartPerTermFlow:

    async def test_lesson_start_per_term_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند آغاز هر درس در هر ترم لود و استارت می‌شود؛ state اول student_enrollment است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "lesson_start_per_term.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="lesson_start_per_term",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "lesson_start_per_term"
        assert instance.current_state_code == "student_enrollment"
        assert instance.is_completed is False

    async def test_lesson_start_enrollment_form_defined(self):
        forms = get_process_forms("lesson_start_per_term", state_code="student_enrollment")
        assert len(forms) == 1
        assert forms[0]["code"] == "lesson_enrollment_form"

    async def test_lesson_start_form_validation_requires_course(self):
        forms = get_process_forms("lesson_start_per_term", state_code="student_enrollment")
        ok, missing = validate_student_step_forms(forms, {}, {"lms": {"available_courses": ["theory_1"]}})
        assert ok is False
        assert missing

    async def test_lesson_start_per_term_full_flow_to_lesson_active(
        self, db_session: AsyncSession, sample_student, sample_student_user, sample_user
    ):
        """جریان کامل با فرم، اتوماسیون سیستمی و lesson_active."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "lesson_start_per_term.json")
        await db_session.commit()

        st = await db_session.get(Student, sample_student.id)
        extra = dict(st.extra_data or {})
        extra["lms"] = {"available_courses": ["theory_psychoanalysis_2"]}
        st.extra_data = extra
        flag_modified(st, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="lesson_start_per_term",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
            initial_context={"lms": {"available_courses": ["theory_psychoanalysis_2"]}},
        )
        await db_session.commit()

        forms = get_process_forms("lesson_start_per_term", state_code="student_enrollment")
        values = {"selected_courses": ["theory_psychoanalysis_2"]}
        ok, missing = validate_student_step_forms(forms, values, instance.context_data or {})
        assert ok is True, missing

        from app.meta.student_step_forms import apply_register_to_context

        instance.context_data = apply_register_to_context(
            instance.context_data or {},
            "student_enrollment",
            values,
        )
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="enrolled",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "lesson_active"
        assert instance.is_completed is True

        st = await db_session.get(Student, sample_student.id)
        lms = (st.extra_data or {}).get("lms") or {}
        assert lms.get("links_placed") is True
        assert lms.get("attendance_list_ready") is True
        assert "theory_psychoanalysis_2" in (lms.get("enrolled_courses") or [])
        assert (instance.context_data or {}).get("online_class_link")
        link = (instance.context_data or {}).get("online_class_link") or ""
        assert "tab=sessions" in link or link.startswith("/panel/")

    async def test_lesson_start_scheduler_fires_for_string_enrollments(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """با enrolled_courses به‌صورت list[str] زمان‌بند باید lesson_start را بسازد."""
        from datetime import date, datetime, timedelta, timezone

        from sqlalchemy import select

        from app.models.operational_models import ProcessInstance
        from app.services.institute_calendar_service import upsert_active_calendar
        from app.services.process_scheduler import dispatch_academic_term_batch
        from app.meta.seed import load_rules

        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "lesson_start_per_term.json")
        await db_session.commit()

        now = datetime.now(timezone.utc)
        await upsert_active_calendar(
            db_session,
            payload={
                "term_code": "test-term-lesson-str",
                "term_start_date": date.today() - timedelta(days=1),
                "term_end_date": date.today() + timedelta(days=90),
                "evaluation_open_at": now + timedelta(days=60),
                "evaluation_close_at": now + timedelta(days=70),
            },
        )
        st = await db_session.get(Student, sample_student.id)
        extra = dict(st.extra_data or {})
        extra["lms"] = {"enrolled_courses": ["theory_psychoanalysis_2"]}
        st.extra_data = extra
        flag_modified(st, "extra_data")
        await db_session.commit()

        hits = await dispatch_academic_term_batch(db_session, now)
        await db_session.commit()
        assert any(
            h.get("trigger") == "term_start_lesson" and h.get("process_code") == "lesson_start_per_term"
            for h in hits
        )
        rows = (
            await db_session.execute(
                select(ProcessInstance).where(
                    ProcessInstance.student_id == sample_student.id,
                    ProcessInstance.process_code == "lesson_start_per_term",
                )
            )
        ).scalars().all()
        assert len(rows) >= 1

    async def test_lesson_start_ta_from_term_offering(
        self, db_session: AsyncSession, sample_student, sample_student_user, sample_user
    ):
        """کمک‌مدرس از TermCourseOffering وارد teaching_assistants_by_course می‌شود."""
        from app.models.operational_models import TermCourseOffering
        from app.services.institute_calendar_service import upsert_active_calendar
        from datetime import date, datetime, timedelta, timezone

        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "lesson_start_per_term.json")
        await db_session.commit()

        await upsert_active_calendar(
            db_session,
            payload={
                "term_code": "test-term-lesson-ta",
                "term_start_date": date.today(),
                "term_end_date": date.today() + timedelta(days=90),
            },
        )
        db_session.add(
            TermCourseOffering(
                term_code="test-term-lesson-ta",
                course_code="theory_psychoanalysis_2",
                course_name_fa="تئوری روانکاوی ۲",
                program_kind="introductory",
                term_number=1,
                teaching_assistant_name="کمک‌مدرس تست",
                instructor_name="مدرس تست",
                is_active=True,
                published_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="lesson_start_per_term",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
            initial_context={
                "selected_courses": ["theory_psychoanalysis_2"],
                "lms": {"available_courses": ["theory_psychoanalysis_2"]},
            },
        )
        await db_session.commit()

        from app.meta.student_step_forms import apply_register_to_context

        instance.context_data = apply_register_to_context(
            instance.context_data or {},
            "student_enrollment",
            {"selected_courses": ["theory_psychoanalysis_2"]},
        )
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="enrolled",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True

        st = await db_session.get(Student, sample_student.id)
        ta_map = ((st.extra_data or {}).get("lms") or {}).get("teaching_assistants_by_course") or {}
        assert ta_map.get("theory_psychoanalysis_2") == "کمک‌مدرس تست"

    async def test_lesson_start_active_template_exists(self):
        from app.services.notification_service import TEMPLATES

        assert "lesson_start_active" in TEMPLATES
        assert TEMPLATES["lesson_start_active"].get("in_app") or TEMPLATES["lesson_start_active"].get("sms")
