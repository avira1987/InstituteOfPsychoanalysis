"""مرحلهٔ یکپارچهٔ «مصاحبه‌ها» در آماده‌سازی ترم (ادغام گام‌های ۷ و ۸)."""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.main import app

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.models.operational_models import InterviewSlot, User
from app.services.semester_prep_interview_setup_service import (
    GENERATED_SLOT_LABEL_FA,
    SemesterPrepInterviewSetupError,
    apply_semester_prep_interview_setup,
    build_interview_slot_specs,
    interview_setup_errors,
    interview_scheduling_form_values,
    interviewer_assignment_form_values,
    normalize_interview_setup_payload,
    parse_time_hhmm,
)

PROCESSES_DIR = Path(__file__).resolve().parents[2] / "metadata" / "processes"


def _future_dates(count: int = 2) -> list[str]:
    today = datetime.now(timezone.utc).date()
    return [(today + timedelta(days=7 + i)).isoformat() for i in range(count)]


def _payload(interviewer_ids: list[str], **overrides) -> dict:
    dates = overrides.pop("dates", _future_dates())
    group = {
        "interviewer_ids": interviewer_ids,
        "dates": dates,
        "start_time": "09:00",
        "end_time": "11:00",
        "session_minutes": 30,
    }
    base = {
        "interview_mode": "آنلاین",
        "interview_location_fa": "",
        "comprehensive": dict(group),
        "introductory": dict(group),
    }
    base.update(overrides)
    return base


def _per_interviewer_payload(
    schedules: list[dict],
    *,
    session_minutes: int = 30,
    **overrides,
) -> dict:
    """فرمت جدید: هر مصاحبه‌گر روز/ساعت مستقل."""
    group = {
        "interviewers": schedules,
        "session_minutes": session_minutes,
    }
    base = {
        "interview_mode": "آنلاین",
        "interview_location_fa": "",
        "comprehensive": dict(group),
        "introductory": dict(group),
    }
    base.update(overrides)
    return base


class TestPlanHelpers:
    def test_parse_time_accepts_persian_digits(self):
        assert parse_time_hhmm("۰۹:۳۰") == time(9, 30)
        assert parse_time_hhmm("23:59") == time(23, 59)
        assert parse_time_hhmm("24:00") is None
        assert parse_time_hhmm("") is None

    def test_slots_are_tiled_per_interviewer_and_day(self):
        payload = normalize_interview_setup_payload(
            _payload(["a", "b"], dates=["2026-09-01", "2026-09-02"])
        )
        specs = build_interview_slot_specs(payload)
        # ۲ روز × ۲ مصاحبه‌گر × ۴ نوبت ۳۰ دقیقه‌ای، برای هر دو نوع دوره
        assert len(specs) == 2 * 2 * 4 * 2
        assert {s["course_type"] for s in specs} == {"comprehensive", "introductory"}
        assert all(s["mode"] == "online" for s in specs)
        assert all(s["starts_at"].tzinfo is not None for s in specs)

    def test_per_interviewer_schedules_use_independent_days_and_hours(self):
        payload = normalize_interview_setup_payload(
            _per_interviewer_payload(
                [
                    {
                        "interviewer_id": "alice",
                        "dates": ["2026-09-05"],
                        "start_time": "09:00",
                        "end_time": "12:00",
                    },
                    {
                        "interviewer_id": "bob",
                        "dates": ["2026-09-06"],
                        "start_time": "14:00",
                        "end_time": "17:00",
                    },
                ]
            )
        )
        specs = build_interview_slot_specs(payload)
        # هر نفر: ۱ روز × ۶ نوبت ۳۰ دقیقه‌ای؛ دو دوره
        assert len(specs) == 2 * 6 * 2
        alice = [s for s in specs if s["interviewer_user_id"] == "alice"]
        bob = [s for s in specs if s["interviewer_user_id"] == "bob"]
        assert len(alice) == 12
        assert len(bob) == 12
        assert all(s["starts_at"].date().isoformat() == "2026-09-05" for s in alice)
        assert all(s["starts_at"].date().isoformat() == "2026-09-06" for s in bob)
        # ۰۹:۰۰ تهران = ۰۵:۳۰ UTC ؛ ۱۴:۰۰ تهران = ۱۰:۳۰ UTC
        assert alice[0]["starts_at"] == datetime(2026, 9, 5, 5, 30, tzinfo=timezone.utc)
        assert bob[0]["starts_at"] == datetime(2026, 9, 6, 10, 30, tzinfo=timezone.utc)

    def test_legacy_shared_payload_expands_to_per_interviewer_schedules(self):
        payload = normalize_interview_setup_payload(
            _payload(["a", "b"], dates=["2026-09-01"])
        )
        group = payload["comprehensive"]
        assert len(group["interviewers"]) == 2
        assert {s["interviewer_id"] for s in group["interviewers"]} == {"a", "b"}
        assert all(s["dates"] == [date(2026, 9, 1)] for s in group["interviewers"])
        assert all(s["start_time"] == time(9, 0) for s in group["interviewers"])

    def test_tehran_local_times_are_converted_to_utc(self):
        payload = normalize_interview_setup_payload(
            _payload(["a"], dates=["2026-09-01"])
        )
        first = build_interview_slot_specs(payload)[0]
        # ۰۹:۰۰ تهران = ۰۵:۳۰ UTC
        assert first["starts_at"] == datetime(2026, 9, 1, 5, 30, tzinfo=timezone.utc)

    def test_in_person_mode_requires_location(self):
        payload = normalize_interview_setup_payload(
            _payload(["a"], interview_mode="حضوری", interview_location_fa="")
        )
        errors = interview_setup_errors(payload)
        assert any("محل برگزاری" in e for e in errors)

        payload["interview_location_fa"] = "سالن ۲"
        assert interview_setup_errors(payload) == []

    def test_missing_interviewer_or_day_is_reported_per_course(self):
        raw = _payload([])
        raw["introductory"] = {
            "interviewers": [
                {
                    "interviewer_id": "x",
                    "dates": [],
                    "start_time": "09:00",
                    "end_time": "11:00",
                }
            ],
            "session_minutes": 30,
        }
        errors = interview_setup_errors(normalize_interview_setup_payload(raw))
        assert any("دوره جامع" in e and "مصاحبه‌گر" in e for e in errors)
        assert any("دوره آشنایی" in e and "روز" in e for e in errors)

    def test_end_time_before_start_is_rejected(self):
        raw = _payload(["a"])
        raw["comprehensive"]["end_time"] = "08:00"
        errors = interview_setup_errors(normalize_interview_setup_payload(raw))
        assert any("بعد از ساعت شروع" in e for e in errors)

    def test_per_interviewer_end_time_error_names_that_interviewer(self):
        raw = _per_interviewer_payload(
            [
                {
                    "interviewer_id": "ok",
                    "dates": ["2026-09-01"],
                    "start_time": "09:00",
                    "end_time": "11:00",
                },
                {
                    "interviewer_id": "bad",
                    "dates": ["2026-09-02"],
                    "start_time": "16:00",
                    "end_time": "14:00",
                },
            ]
        )
        errors = interview_setup_errors(normalize_interview_setup_payload(raw))
        assert any("مصاحبه‌گر 2" in e and "بعد از ساعت شروع" in e for e in errors)

    def test_form_values_derived_from_plan(self):
        payload = normalize_interview_setup_payload(
            _payload(["a"], dates=["2026-09-03", "2026-09-01"], interview_mode="حضوری",
                     interview_location_fa="سالن ۱")
        )
        assignment = interviewer_assignment_form_values(payload)
        assert assignment["comprehensive_date_range_start"] == "2026-09-01"
        assert assignment["comprehensive_date_range_end"] == "2026-09-03"
        assert assignment["introductory_interviewers"] == ["a"]

        scheduling = interview_scheduling_form_values(payload)
        assert scheduling == {"interview_mode": "حضوری", "interview_location_fa": "سالن ۱"}

    def test_slot_count_cap_is_enforced(self):
        raw = _payload(["a", "b", "c"], dates=_future_dates(20))
        raw["comprehensive"]["session_minutes"] = 10
        raw["introductory"]["session_minutes"] = 10
        errors = interview_setup_errors(normalize_interview_setup_payload(raw))
        assert any("سقف" in e for e in errors)


@pytest.mark.asyncio
class TestApplyInterviewSetup:
    async def _instance_at_interview_step(self, db_session, sample_student, sample_user):
        await load_process(db_session, PROCESSES_DIR / "fall_semester_preparation.json")
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
        ):
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role=role,
            )
            await db_session.commit()
            assert result.success is True, result.error
        return await engine.get_process_instance(instance.id)

    async def _employee(self, db_session: AsyncSession, *, role: str = "staff") -> User:
        user = User(
            id=uuid.uuid4(),
            username=f"emp-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            full_name_fa="کارمند نمونه",
            role=role,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        return user

    async def test_single_submit_creates_slots_and_publishes(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        instance = await self._instance_at_interview_step(db_session, sample_student, sample_user)
        assert instance.current_state_code == "interviewer_assignment"
        employee = await self._employee(db_session)

        result = await apply_semester_prep_interview_setup(
            db_session,
            instance_id=str(instance.id),
            payload=_payload([str(employee.id)], dates=_future_dates(1)),
            actor=sample_user,
        )
        await db_session.commit()

        # یک اقدام، هر دو گام: نوبت‌ها ساخته و تقویم منتشر شد
        assert result["current_state"] == "published"
        assert result["created_slots"]["total"] == 8
        assert result["created_slots"]["comprehensive"] == 4

        slots = list((await db_session.execute(select(InterviewSlot))).scalars().all())
        assert len(slots) == 8
        assert all(s.interviewer_user_id == employee.id for s in slots)
        assert all(s.label_fa == GENERATED_SLOT_LABEL_FA for s in slots)

        ctx = instance.context_data or {}
        assert ctx["comprehensive_interviewers"] == [str(employee.id)]
        assert ctx["interview_mode"] == "آنلاین"
        assert ctx["interview_setup_plan"]["comprehensive"]["start_time"] == "09:00"
        assert ctx["interview_setup_plan"]["comprehensive"]["interviewers"][0]["interviewer_id"] == str(
            employee.id
        )

    async def test_per_interviewer_schedules_create_distinct_slots(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        instance = await self._instance_at_interview_step(db_session, sample_student, sample_user)
        first = await self._employee(db_session)
        second = await self._employee(db_session)
        day_a, day_b = _future_dates(2)

        result = await apply_semester_prep_interview_setup(
            db_session,
            instance_id=str(instance.id),
            payload=_per_interviewer_payload(
                [
                    {
                        "interviewer_id": str(first.id),
                        "dates": [day_a],
                        "start_time": "09:00",
                        "end_time": "10:00",
                    },
                    {
                        "interviewer_id": str(second.id),
                        "dates": [day_b],
                        "start_time": "14:00",
                        "end_time": "15:00",
                    },
                ]
            ),
            actor=sample_user,
        )
        await db_session.commit()

        # هر نفر: ۱ روز × ۲ نوبت ۳۰ دقیقه‌ای × ۲ دوره = ۴ نوبت؛ جمع ۸
        assert result["created_slots"]["total"] == 8
        slots = list((await db_session.execute(select(InterviewSlot))).scalars().all())
        by_interviewer = {}
        for slot in slots:
            by_interviewer.setdefault(slot.interviewer_user_id, []).append(slot)
        assert set(by_interviewer) == {first.id, second.id}
        assert len(by_interviewer[first.id]) == 4
        assert len(by_interviewer[second.id]) == 4

        plan = (instance.context_data or {})["interview_setup_plan"]["comprehensive"]["interviewers"]
        assert plan[0]["start_time"] == "09:00"
        assert plan[1]["start_time"] == "14:00"
        assert plan[0]["dates"] == [day_a]
        assert plan[1]["dates"] == [day_b]

    async def test_only_slots_generated_by_this_step_are_replaced(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        instance = await self._instance_at_interview_step(db_session, sample_student, sample_user)
        employee = await self._employee(db_session)

        soon = datetime.now(timezone.utc) + timedelta(days=3)
        stale = InterviewSlot(
            id=uuid.uuid4(),
            starts_at=soon,
            ends_at=soon + timedelta(minutes=30),
            mode="online",
            label_fa=GENERATED_SLOT_LABEL_FA,
        )
        manual = InterviewSlot(
            id=uuid.uuid4(),
            starts_at=soon,
            ends_at=soon + timedelta(minutes=30),
            mode="online",
            label_fa="نوبت دستی کارمند دفتر",
        )
        db_session.add_all([stale, manual])
        await db_session.flush()

        await apply_semester_prep_interview_setup(
            db_session,
            instance_id=str(instance.id),
            payload=_payload([str(employee.id)], dates=_future_dates(1)),
            actor=sample_user,
        )
        await db_session.commit()

        labels = [
            s.label_fa
            for s in (await db_session.execute(select(InterviewSlot))).scalars().all()
        ]
        assert "نوبت دستی کارمند دفتر" in labels
        assert labels.count(GENERATED_SLOT_LABEL_FA) == 8

    async def test_deputy_can_complete_both_merged_steps_alone(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        instance = await self._instance_at_interview_step(db_session, sample_student, sample_user)
        deputy = await self._employee(db_session, role="deputy_education")
        employee = await self._employee(db_session)

        result = await apply_semester_prep_interview_setup(
            db_session,
            instance_id=str(instance.id),
            payload=_payload([str(employee.id)], dates=_future_dates(1)),
            actor=deputy,
        )
        await db_session.commit()
        assert result["current_state"] == "published"

    async def test_non_employee_cannot_be_selected(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        instance = await self._instance_at_interview_step(db_session, sample_student, sample_user)
        outsider = await self._employee(db_session, role="course_committee")

        with pytest.raises(SemesterPrepInterviewSetupError):
            await apply_semester_prep_interview_setup(
                db_session,
                instance_id=str(instance.id),
                payload=_payload([str(outsider.id)], dates=_future_dates(1)),
                actor=sample_user,
            )

    async def test_validation_errors_are_returned_before_any_write(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        instance = await self._instance_at_interview_step(db_session, sample_student, sample_user)

        with pytest.raises(SemesterPrepInterviewSetupError) as exc:
            await apply_semester_prep_interview_setup(
                db_session,
                instance_id=str(instance.id),
                payload=_payload([], dates=[]),
                actor=sample_user,
            )
        assert exc.value.detail["error"] == "validation_failed"

        slots = list((await db_session.execute(select(InterviewSlot))).scalars().all())
        assert slots == []
        refreshed = await StateMachineEngine(db_session).get_process_instance(instance.id)
        assert refreshed.current_state_code == "interviewer_assignment"


@pytest_asyncio.fixture
async def prep_api_client(db_session: AsyncSession, sample_user):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
class TestInterviewSetupApi:
    async def test_candidates_endpoint_lists_only_employees(
        self, db_session: AsyncSession, prep_api_client, sample_user
    ):
        keep = User(
            id=uuid.uuid4(),
            username=f"iv-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            full_name_fa="مصاحبه‌گر فعال",
            role="interviewer",
            is_active=True,
        )
        skip = User(
            id=uuid.uuid4(),
            username=f"cc-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="x",
            full_name_fa="عضو کمیته",
            role="course_committee",
            is_active=True,
        )
        db_session.add_all([keep, skip])
        await db_session.flush()

        res = await prep_api_client.get("/api/admin/semester-prep/interview-candidates")
        assert res.status_code == 200
        ids = {c["id"] for c in res.json()["candidates"]}
        assert str(keep.id) in ids
        assert str(skip.id) not in ids

    async def test_setup_endpoint_returns_validation_errors(
        self, db_session: AsyncSession, prep_api_client, sample_student, sample_user
    ):
        await load_process(db_session, PROCESSES_DIR / "fall_semester_preparation.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        res = await prep_api_client.post(
            "/api/admin/semester-prep/interview-setup",
            json={"instance_id": str(instance.id), **_payload([], dates=[])},
        )
        # مرحلهٔ فعلی هنوز مصاحبه‌ها نیست
        assert res.status_code == 400
        assert "مصاحبه" in str(res.json()["detail"])
