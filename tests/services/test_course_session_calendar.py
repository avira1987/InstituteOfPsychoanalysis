"""Tests for course session calendar + enrollment learning path."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_password_hash
from app.main import app
from app.models.operational_models import (
    InstituteCalendar,
    ProcessInstance,
    Student,
    TermCourseOffering,
    User,
)
from app.services.course_session_calendar_service import (
    build_course_sessions_for_offering,
    iter_session_dates,
    parse_fa_weekday,
    parse_time_text,
    seed_course_sessions_for_student,
    session_attendance_already_recorded,
)
from app.services.institute_calendar_service import deactivate_all_calendars
from app.services.student_enrolled_courses_service import list_student_enrolled_courses
from app.services.student_online_sessions_service import list_student_online_sessions
from app.services.workflow import lms_service


def test_parse_fa_weekday():
    assert parse_fa_weekday("شنبه") == 5
    assert parse_fa_weekday("یکشنبه") == 6
    assert parse_fa_weekday("دوشنبه") == 0
    assert parse_fa_weekday("سه‌شنبه") == 1
    assert parse_fa_weekday("unknown") is None


def test_parse_time_text():
    assert parse_time_text("10:30") == (10, 30)
    assert parse_time_text("۱۰:۰۰-۱۲:۰۰") == (10, 0)
    assert parse_time_text("") == (10, 0)


def test_iter_session_dates_weekly():
    # 2026-03-01 is Sunday; want Mondays
    start = date(2026, 3, 1)
    end = date(2026, 3, 31)
    mondays = iter_session_dates(weekday=0, term_start=start, term_end=end)
    assert all(d.weekday() == 0 for d in mondays)
    assert mondays[0] == date(2026, 3, 2)
    assert len(mondays) == 5


def test_session_attendance_already_recorded():
    lms = {
        "lesson_attendance": {
            "theory_1": {
                "sessions": [{"date": "2026-03-10", "status": "present"}],
            }
        }
    }
    assert session_attendance_already_recorded(lms, "theory_1", "2026-03-10") is True
    assert session_attendance_already_recorded(lms, "theory_1", "2026-03-17") is False


@pytest.mark.asyncio
async def test_build_and_seed_course_sessions(
    db_session: AsyncSession,
    sample_student: Student,
):
    now = datetime.now(timezone.utc)
    await deactivate_all_calendars(db_session)
    term_start = date(2026, 3, 1)  # Sunday
    term_end = date(2026, 4, 30)
    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code=f"t-{uuid.uuid4().hex[:6]}",
        is_active=True,
        term_start_date=term_start,
        term_end_date=term_end,
        published_at=now,
    )
    db_session.add(cal)
    offering = TermCourseOffering(
        id=uuid.uuid4(),
        term_code=cal.term_code,
        course_code="theory_psychoanalysis_1",
        course_name_fa="تئوری روانکاوی ۱",
        program_kind="introductory",
        term_number=1,
        day="شنبه",
        time_text="09:00",
        classroom_location="A1",
        instructor_name="مدرس تست",
        is_active=True,
        published_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(offering)
    await db_session.flush()

    built = build_course_sessions_for_offering(
        offering, term_start=term_start, term_end=term_end
    )
    assert len(built) >= 4
    assert all(s["course_code"] == "theory_psychoanalysis_1" for s in built)
    assert all(date.fromisoformat(s["session_date"]).weekday() == 5 for s in built)

    extra = dict(sample_student.extra_data or {})
    extra["lms"] = {"enrolled_courses": ["theory_psychoanalysis_1"]}
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.flush()

    n = await seed_course_sessions_for_student(
        db_session, sample_student, course_codes=["theory_psychoanalysis_1"]
    )
    assert n >= 4
    await db_session.commit()
    await db_session.refresh(sample_student)
    sessions = (sample_student.extra_data or {}).get("lms", {}).get("course_sessions") or []
    assert len(sessions) >= 4


@pytest.mark.asyncio
async def test_enrollment_seeds_portal_links_and_sessions(
    db_session: AsyncSession,
    sample_student: Student,
    sample_user: User,
):
    now = datetime.now(timezone.utc)
    await deactivate_all_calendars(db_session)
    term_start = date(2026, 3, 1)
    term_end = date(2026, 4, 30)
    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code=f"t-{uuid.uuid4().hex[:6]}",
        is_active=True,
        term_start_date=term_start,
        term_end_date=term_end,
        published_at=now,
    )
    db_session.add(cal)
    code = "theory_psychoanalysis_1"
    offering = TermCourseOffering(
        id=uuid.uuid4(),
        term_code=cal.term_code,
        course_code=code,
        course_name_fa="تئوری روانکاوی ۱",
        program_kind="introductory",
        term_number=1,
        day="دوشنبه",
        time_text="10:00",
        instructor_name="مدرس",
        online_meeting_url="https://meet.example/class-1",
        is_active=True,
        published_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add(offering)

    instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        process_code="introductory_course_registration",
        current_state_code="payment",
        is_completed=False,
        is_cancelled=False,
        started_at=now,
        context_data={"selected_courses": [code]},
    )
    db_session.add(instance)
    await db_session.flush()

    result = await lms_service.handle(
        db_session,
        instance,
        {"type": "register_courses_in_portal"},
        {},
    )
    await db_session.commit()
    await db_session.refresh(sample_student)

    assert "enrolled" in (result or "")
    lms = (sample_student.extra_data or {}).get("lms") or {}
    assert code in (lms.get("enrolled_courses") or [])
    assert code in (lms.get("portal_course_links") or {})
    assert "https://meet.example/class-1" in str(lms.get("portal_course_links", {}).get(code))
    assert isinstance(lms.get("lesson_attendance", {}).get(code), dict)
    assert len(lms.get("course_sessions") or []) >= 1


@pytest.mark.asyncio
async def test_list_sessions_from_enrolled_without_portal_links(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
):
    now = datetime.now(timezone.utc)
    await deactivate_all_calendars(db_session)
    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code=f"t-{uuid.uuid4().hex[:6]}",
        is_active=True,
        term_start_date=now.date(),
        term_end_date=(now + timedelta(days=60)).date(),
        published_at=now,
    )
    db_session.add(cal)
    code = "skills_1"
    db_session.add(
        TermCourseOffering(
            id=uuid.uuid4(),
            term_code=cal.term_code,
            course_code=code,
            course_name_fa="مهارت‌ها ۱",
            program_kind="introductory",
            term_number=1,
            day="سه‌شنبه",
            time_text="14:00",
            instructor_name="استاد مهارت",
            online_meeting_url="https://skyroom.example/skills",
            is_active=True,
            published_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    extra = dict(sample_student.extra_data or {})
    # فقط enrollment — بدون portal_course_links
    extra["lms"] = {"enrolled_courses": [code]}
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    out = await list_student_online_sessions(
        db_session, sample_student, sample_student_user, include_past=False
    )
    courses = [x for x in out["items"] if x["kind"] == "course"]
    assert len(courses) == 1
    assert courses[0]["meeting_link"] == "https://skyroom.example/skills"
    assert courses[0]["day"] == "سه‌شنبه"
    assert "/panel/portal/student" not in (courses[0]["meeting_link"] or "")

    enrolled = await list_student_enrolled_courses(db_session, sample_student)
    assert len(enrolled["courses"]) == 1
    assert enrolled["courses"][0]["meeting_link"] == "https://skyroom.example/skills"


@pytest.mark.asyncio
async def test_instructor_meeting_link_and_attendance_api(
    db_session: AsyncSession,
    sample_student: Student,
):
    from httpx import ASGITransport, AsyncClient

    from app.api.auth import get_current_user
    from app.database import get_db

    now = datetime.now(timezone.utc)
    await deactivate_all_calendars(db_session)
    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code=f"t-{uuid.uuid4().hex[:6]}",
        is_active=True,
        term_start_date=now.date(),
        term_end_date=(now + timedelta(days=60)).date(),
        published_at=now,
    )
    db_session.add(cal)
    code = "theory_api_1"
    db_session.add(
        TermCourseOffering(
            id=uuid.uuid4(),
            term_code=cal.term_code,
            course_code=code,
            course_name_fa="تئوری API",
            program_kind="introductory",
            term_number=1,
            day="چهارشنبه",
            time_text="11:00",
            is_active=True,
            published_at=now,
            created_at=now,
            updated_at=now,
        )
    )

    uid = uuid.uuid4().hex[:10]
    instructor = User(
        id=uuid.uuid4(),
        username=f"inst_{uid}",
        email=f"inst_{uid}@test.com",
        hashed_password=get_password_hash("testpass"),
        role="instructor",
        is_active=True,
        full_name_fa="مدرس API",
        profile_meta={
            "semester_course_assignments": [
                {"course_code": code, "course_name": "تئوری API", "role_kind": "instructor"}
            ]
        },
    )
    other = User(
        id=uuid.uuid4(),
        username=f"other_{uid}",
        email=f"other_{uid}@test.com",
        hashed_password=get_password_hash("testpass"),
        role="instructor",
        is_active=True,
        profile_meta={"semester_course_assignments": []},
    )
    db_session.add(instructor)
    db_session.add(other)

    extra = dict(sample_student.extra_data or {})
    extra["lms"] = {
        "enrolled_courses": [code],
        "lesson_attendance": {
            code: {
                "course_code": code,
                "students": [
                    {
                        "student_id": str(sample_student.id),
                        "student_code": sample_student.student_code,
                        "name_fa": "دانشجو",
                    }
                ],
                "sessions": [],
                "absence_count": 0,
            }
        },
    }
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        app.dependency_overrides[get_current_user] = lambda: instructor
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.patch(
                f"/api/panel/instructor/courses/{code}/meeting-link",
                json={"online_meeting_url": "https://meet.example/theory"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["online_meeting_url"] == "https://meet.example/theory"

            app.dependency_overrides[get_current_user] = lambda: other
            r2 = await ac.patch(
                f"/api/panel/instructor/courses/{code}/meeting-link",
                json={"online_meeting_url": "https://meet.example/hack"},
            )
            assert r2.status_code == 403

            app.dependency_overrides[get_current_user] = lambda: instructor
            r3 = await ac.post(
                f"/api/panel/instructor/courses/{code}/attendance",
                json={
                    "session_date": "2026-03-18",
                    "rows": [
                        {
                            "student_id": str(sample_student.id),
                            "status": "present",
                            "person_name": "دانشجو",
                        }
                    ],
                },
            )
            assert r3.status_code == 200, r3.text
            assert r3.json()["summary"]["present"] == 1

        await db_session.refresh(sample_student)
        lms = (sample_student.extra_data or {}).get("lms") or {}
        assert session_attendance_already_recorded(lms, code, "2026-03-18") is True
        links = lms.get("portal_course_links") or {}
        assert links.get(code) == "https://meet.example/theory"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_scheduler_skips_class_attendance_when_already_recorded(
    db_session: AsyncSession,
    sample_student: Student,
):
    from app.services.process_scheduler import dispatch_lms_session_hooks

    today = date.today()
    extra = dict(sample_student.extra_data or {})
    extra["lms"] = {
        "enrolled_courses": ["theory_sched_1"],
        "course_sessions": [
            {
                "course_id": "theory_sched_1",
                "session_index": 1,
                "session_date": today.isoformat(),
            }
        ],
        "lesson_attendance": {
            "theory_sched_1": {
                "sessions": [{"date": today.isoformat(), "status": "present"}],
            }
        },
    }
    extra["scheduler_fingerprints"] = {}
    sample_student.extra_data = extra
    sample_student.is_sample_data = False
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    out = await dispatch_lms_session_hooks(db_session, datetime.now(timezone.utc))
    await db_session.commit()
    await db_session.refresh(sample_student)

    # should not start a new class_attendance instance for that date
    started = [x for x in out if x.get("trigger") == "session_time_reached" and x.get("process_code") == "class_attendance"]
    # fingerprint should be set
    fps = (sample_student.extra_data or {}).get("scheduler_fingerprints") or {}
    assert fps.get(f"class_att:theory_sched_1:{today.isoformat()}")
    assert not any(
        x.get("process_code") == "class_attendance" and "theory_sched_1" in str(x)
        for x in started
    )
