"""تست سرویس چارت مدرسین/کمک‌مدرسین کمیته دروس."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.api.auth import get_password_hash
from app.models.operational_models import User
from app.services.course_committee_roster_service import (
    enrich_course_table_rows,
    list_members,
    list_track_options,
    reload_roster_cache,
)


@pytest.fixture(autouse=True)
def _fresh_roster_cache():
    reload_roster_cache()
    yield
    reload_roster_cache()


def test_list_track_options_includes_analytic_track():
    opts = list_track_options()
    codes = [o["value"] for o in opts]
    assert "analytic_psychotherapy" in codes


@pytest.mark.asyncio
async def test_list_instructors_for_track_without_users(db_session):
    members = await list_members(
        db_session, track="analytic_psychotherapy", kind="instructor"
    )
    assert len(members) >= 8
    names = {m["label_fa"] for m in members}
    assert "ادريس صالحي" in names
    assert "اسرا شريفي" in names


@pytest.mark.asyncio
async def test_list_members_merges_seeded_user(db_session):
    uid = uuid.uuid4()
    user = User(
        id=uid,
        username="cc_extra_instructor_test",
        email="cc_extra@test.local",
        hashed_password=get_password_hash("demo123"),
        full_name_fa="مدرس اضافه تست",
        role="instructor",
        is_active=True,
        profile_meta={
            "course_committee_tracks": ["analytic_psychotherapy"],
            "member_kind": "instructor",
            "tier": 2,
        },
    )
    db_session.add(user)
    await db_session.commit()

    members = await list_members(
        db_session, track="analytic_psychotherapy", kind="instructor"
    )
    values = {m["value"] for m in members}
    assert str(uid) in values


@pytest.mark.asyncio
async def test_list_teaching_assistants_filtered(db_session):
    members = await list_members(
        db_session, track="analytic_psychotherapy", kind="teaching_assistant"
    )
    assert len(members) >= 1
    for m in members:
        assert m.get("label_fa")


@pytest.mark.asyncio
async def test_enrich_course_table_rows_resolves_uuid(db_session):
    uid = uuid.uuid4()
    user = User(
        id=uid,
        username="cc_enrich_test",
        email="cc_enrich@test.local",
        hashed_password=get_password_hash("demo123"),
        full_name_fa="نام مدرس تست",
        role="instructor",
        is_active=True,
        profile_meta={
            "course_committee_tracks": ["analytic_psychotherapy"],
            "member_kind": "instructor",
        },
    )
    db_session.add(user)
    await db_session.commit()

    forms = [
        {
            "fields": [
                {
                    "type": "table",
                    "name": "courses",
                    "columns": [
                        {"name": "track"},
                        {"name": "instructor"},
                        {"name": "teaching_assistant"},
                    ],
                }
            ]
        }
    ]
    values = {
        "courses": [
            {
                "track": "analytic_psychotherapy",
                "instructor": str(uid),
                "teaching_assistant": "",
            }
        ]
    }
    out = await enrich_course_table_rows(db_session, forms, values)
    row = out["courses"][0]
    assert row["instructor"] == "نام مدرس تست"
    assert row["instructor_id"] == str(uid)


def test_list_course_catalog_options():
    from app.services.course_committee_roster_service import list_course_catalog_options, reload_catalog_cache

    reload_catalog_cache()
    opts = list_course_catalog_options()
    labels = [o["label_fa"] for o in opts]
    assert "تئوری وراثت" in labels


@pytest.mark.asyncio
async def test_sync_semester_course_assignments(db_session):
    from app.services.course_committee_roster_service import sync_semester_course_assignments

    uid = uuid.uuid4()
    user = User(
        id=uid,
        username="cc_sync_test",
        email="cc_sync@test.local",
        hashed_password=get_password_hash("demo123"),
        full_name_fa="مدرس همگام‌سازی",
        role="instructor",
        is_active=True,
        profile_meta={
            "course_committee_tracks": ["analytic_psychotherapy"],
            "member_kind": "instructor",
        },
    )
    db_session.add(user)
    await db_session.commit()

    n = await sync_semester_course_assignments(
        db_session,
        courses_rows=[
            {
                "course_name": "تئوری وراثت",
                "track": "analytic_psychotherapy",
                "proposed_day": "شنبه",
                "proposed_time": "18:00",
                "instructor_id": str(uid),
                "instructor": "مدرس همگام‌سازی",
            }
        ],
        process_code="fall_semester_preparation",
    )
    assert n >= 1
    await db_session.refresh(user)
    items = (user.profile_meta or {}).get("semester_course_assignments") or []
    assert any(i.get("course_name") == "تئوری وراثت" for i in items)
