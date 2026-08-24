"""قفل سروری قسط معوق روی کلاس/جلسه/تکلیف و join بدون URL خام."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from starlette.testclient import TestClient

from app.main import app
from app.models.operational_models import Student, User
from app.services.installment_access import INSTALLMENT_LOCK_DETAIL
from app.services.student_enrolled_courses_service import (
    list_student_enrolled_courses,
    resolve_student_course_join_url,
)


COURSE_CODE = "THEORY101"
COURSE_URL = "https://skyroom.example/class-room"


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _login_headers(client: TestClient, username: str, password: str = "testpass") -> dict:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _enroll_with_meeting(student: Student) -> None:
    extra = dict(student.extra_data or {})
    extra["lms"] = {
        "enrolled_courses": [COURSE_CODE],
        "portal_course_links": {COURSE_CODE: COURSE_URL},
        "course_links": {COURSE_CODE: COURSE_URL},
        "course_link_meta": {COURSE_CODE: {"online_meeting_url": COURSE_URL}},
    }
    student.extra_data = extra
    flag_modified(student, "extra_data")


def _set_lock(student: Student, active: bool) -> None:
    extra = dict(student.extra_data or {})
    extra["installment_portal_lock"] = {"active": active}
    student.extra_data = extra
    flag_modified(student, "extra_data")


@pytest.mark.asyncio
async def test_enrolled_courses_hide_raw_url(
    db_session: AsyncSession,
    sample_student: Student,
):
    _enroll_with_meeting(sample_student)
    await db_session.commit()
    await db_session.refresh(sample_student)

    out = await list_student_enrolled_courses(db_session, sample_student)
    assert out["courses"]
    row = out["courses"][0]
    assert row["course_code"] == COURSE_CODE
    assert row["meeting_link"] is None
    assert row["join_path"] == f"/api/panel/courses/{COURSE_CODE}/join"
    assert row["meeting_link_ready"] is True
    assert COURSE_URL not in str(out)

    url = await resolve_student_course_join_url(db_session, sample_student, COURSE_CODE)
    assert url == COURSE_URL


@pytest.mark.asyncio
async def test_panel_lock_forbids_class_and_assignment_apis(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
    client: TestClient,
):
    _enroll_with_meeting(sample_student)
    _set_lock(sample_student, True)
    await db_session.commit()

    headers = _login_headers(client, sample_student_user.username)
    for path in (
        "/api/panel/my-online-sessions",
        "/api/panel/my-enrolled-courses",
        f"/api/panel/courses/{COURSE_CODE}/join",
        "/api/assignments/me",
    ):
        r = client.get(path, headers=headers)
        assert r.status_code == 403, path + " " + r.text
        assert r.json()["detail"] == INSTALLMENT_LOCK_DETAIL

    me = client.get("/api/students/me", headers=headers)
    assert me.status_code == 200, me.text
    finance = client.get("/api/students/me/finance", headers=headers)
    assert finance.status_code == 200, finance.text


@pytest.mark.asyncio
async def test_panel_join_returns_url_without_exposing_it_in_list(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
    client: TestClient,
):
    _enroll_with_meeting(sample_student)
    _set_lock(sample_student, False)
    await db_session.commit()

    headers = _login_headers(client, sample_student_user.username)
    listed = client.get("/api/panel/my-enrolled-courses", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["courses"][0]["meeting_link"] is None
    assert body["courses"][0]["join_path"]
    assert COURSE_URL not in listed.text

    sessions = client.get("/api/panel/my-online-sessions", headers=headers)
    assert sessions.status_code == 200, sessions.text
    course = next(x for x in sessions.json()["items"] if x["kind"] == "course")
    assert course["meeting_link"] is None
    assert course["join_path"] == f"/api/panel/courses/{COURSE_CODE}/join"

    joined = client.get(f"/api/panel/courses/{COURSE_CODE}/join", headers=headers)
    assert joined.status_code == 200, joined.text
    assert joined.json()["join_url"] == COURSE_URL
