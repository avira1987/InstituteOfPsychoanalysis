"""Test ta_track_change flow (process 51 — تغییر/اضافه رسته کمک‌مدرس)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.core.transition import TransitionManager
from app.meta.seed import load_process
from app.models.operational_models import Student
from app.services.ta_track_change_service import (
    apply_track_change,
    get_active_ta_tracks,
    validate_new_tracks,
)


def _form_submitted(**states: bool) -> dict:
    return {"__student_forms_submitted_states": dict(states)}


@pytest.mark.asyncio
class TestTaTrackChangeFlow:

    async def test_ta_track_change_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ta_track_change لود و استارت می‌شود؛ state اول ta_click است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_track_change.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_track_change",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "ta_track_change"
        assert instance.current_state_code == "ta_click"
        assert instance.is_completed is False

    async def test_path_chosen_chains_to_course_committee_review(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """پس از path_chosen، زنجیره request_sent به course_committee_review می‌رسد."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_track_change.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_track_change",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="teaching_assistant",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="path_chosen",
            actor_id=sample_user.id,
            actor_role="teaching_assistant",
            payload={"path": "add", **_form_submitted(ta_click=True)},
        )
        await db_session.commit()
        assert result.success is True

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "course_committee_review"

    async def test_ta_track_change_flow_to_track_applied(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریو کامل با payload تا track_applied."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_track_change.json")
        extra = dict(sample_student.extra_data or {})
        lms = dict(extra.get("lms") or {})
        lms["ta_active_tracks"] = ["psychoanalysis_theory_1_5"]
        extra["lms"] = lms
        sample_student.extra_data = extra
        db_session.add(sample_student)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_track_change",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance.id,
            "path_chosen",
            sample_user.id,
            "teaching_assistant",
            {"path": "add", **_form_submitted(ta_click=True)},
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "course_committee_review"

        await engine.execute_transition(
            instance.id,
            "meeting_registered",
            sample_user.id,
            "course_committee",
            {
                "meeting_date": "2026-07-15",
                "meeting_time": "10:30",
                "meeting_type": "in_person",
                "meeting_location_fa": "مکان انستیتو",
                **_form_submitted(ta_click=True, course_committee_review=True),
            },
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "meeting_scheduled"

        result = await engine.execute_transition(
            instance.id,
            "approved",
            sample_user.id,
            "course_committee",
            {
                "path": "add",
                "result": "approve",
                "new_tracks": ["film_observation_1_3_continuous"],
                **_form_submitted(
                    ta_click=True,
                    course_committee_review=True,
                    meeting_scheduled=True,
                ),
            },
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "track_applied"

        instance = await engine.get_process_instance(instance.id)
        assert instance.is_completed is True
        ctx = instance.context_data or {}
        assert "film_observation_1_3_continuous" in (ctx.get("applied_tracks") or [])

        st = await db_session.get(Student, sample_student.id)
        tracks = get_active_ta_tracks(st)
        assert "psychoanalysis_theory_1_5" in tracks
        assert "film_observation_1_3_continuous" in tracks

    async def test_validate_new_tracks_rejects_duplicate_on_add(
        self, db_session: AsyncSession, sample_student
    ):
        extra = {"lms": {"ta_active_tracks": ["technique_theory_1_3"]}}
        sample_student.extra_data = extra
        err = validate_new_tracks(sample_student, "add", ["technique_theory_1_3"])
        assert err is not None
        assert "فعال" in err or "تکراری" in err

    async def test_course_committee_role_can_trigger_meeting_registered(self):
        from app.models.meta_models import TransitionDefinition

        tm = TransitionManager(None, None)  # type: ignore[arg-type]
        tr = TransitionDefinition(
            required_role="course_committee_scientific",
            trigger_event="meeting_registered",
        )
        assert tm.validate_role(tr, "course_committee", "meeting_registered") is True
        assert tm.validate_role(tr, "staff", "meeting_registered") is True

    async def test_apply_track_change_replaces_on_change_path(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        sample_student.extra_data = {"lms": {"ta_active_tracks": ["psychoanalysis_theory_1_5"]}}
        db_session.add(sample_student)
        await db_session.flush()

        result = await apply_track_change(
            db_session,
            sample_student,
            path="change",
            new_tracks=["technique_theory_1_3"],
            ta_user=sample_user,
        )
        await db_session.flush()
        assert "technique_theory_1_3" in result["applied_tracks"]
        assert "psychoanalysis_theory_1_5" not in result["applied_tracks"]
