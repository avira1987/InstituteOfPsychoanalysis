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
    from app.services.course_committee_roster_service import (
        list_course_catalog_options,
        reload_catalog_cache,
        resolve_track_for_course,
    )

    reload_catalog_cache()
    opts = list_course_catalog_options()
    labels = [o["label_fa"] for o in opts]
    assert "تئوری وراثت" in labels
    inheritance = next(o for o in opts if o["label_fa"] == "تئوری وراثت")
    assert inheritance.get("track") == "analytic_psychotherapy"
    assert resolve_track_for_course("theory_inheritance") == "analytic_psychotherapy"
    assert resolve_track_for_course("تئوری وراثت") == "analytic_psychotherapy"
    assert resolve_track_for_course("theory_technique_1") == "technique_theory_1_3"


def test_add_course_to_catalog(tmp_path, monkeypatch):
    from app.services import course_committee_roster_service as svc

    catalog_file = tmp_path / "course_catalog.json"
    catalog_file.write_text('{"courses": []}', encoding="utf-8")
    monkeypatch.setattr(svc, "_CATALOG_PATH", catalog_file)
    svc.reload_catalog_cache()

    created = svc.add_course_to_catalog("درس آزمایشی جدید")
    assert created["label_fa"] == "درس آزمایشی جدید"
    assert created["value"]

    opts = svc.list_course_catalog_options()
    assert any(o["label_fa"] == "درس آزمایشی جدید" for o in opts)

    again = svc.add_course_to_catalog("درس آزمایشی جدید")
    assert again["label_fa"] == "درس آزمایشی جدید"


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


@pytest.mark.asyncio
async def test_list_members_filters_ta_by_authorized_course(db_session):
    uid_ta1 = uuid.uuid4()
    uid_ta2 = uuid.uuid4()
    db_session.add(
        User(
            id=uid_ta1,
            username="ta_course_a",
            email="ta_a@test.local",
            hashed_password=get_password_hash("demo123"),
            full_name_fa="کمک‌مدرس درس الف",
            role="teaching_assistant",
            is_active=True,
            profile_meta={
                "course_committee_tracks": ["analytic_psychotherapy"],
                "member_kind": "teaching_assistant",
                "ta_authorized_courses": ["theory_inheritance"],
            },
        )
    )
    db_session.add(
        User(
            id=uid_ta2,
            username="ta_course_b",
            email="ta_b@test.local",
            hashed_password=get_password_hash("demo123"),
            full_name_fa="کمک‌مدرس درس ب",
            role="teaching_assistant",
            is_active=True,
            profile_meta={
                "course_committee_tracks": ["analytic_psychotherapy"],
                "member_kind": "teaching_assistant",
                "ta_authorized_courses": ["theory_psychoanalysis_1"],
            },
        )
    )
    await db_session.commit()

    for_course_a = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="teaching_assistant",
        course="theory_inheritance",
    )
    labels_a = {m["label_fa"] for m in for_course_a}
    assert "کمک‌مدرس درس الف" in labels_a
    assert "کمک‌مدرس درس ب" not in labels_a


@pytest.mark.asyncio
async def test_list_members_filters_instructor_by_authorized_course(db_session):
    uid_inst = uuid.uuid4()
    db_session.add(
        User(
            id=uid_inst,
            username="inst_course_only",
            email="inst@test.local",
            hashed_password=get_password_hash("demo123"),
            full_name_fa="مدرس فرایند ۴۹",
            role="instructor",
            is_active=True,
            profile_meta={
                "course_committee_tracks": ["analytic_psychotherapy"],
                "member_kind": "instructor",
                "instructor_authorized_courses": ["theory_psychoanalysis_2"],
            },
        )
    )
    await db_session.commit()

    allowed = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="instructor",
        course="theory_psychoanalysis_2",
    )
    blocked = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="instructor",
        course="theory_inheritance",
    )
    assert any(m["label_fa"] == "مدرس فرایند ۴۹" for m in allowed)
    assert not any(m["label_fa"] == "مدرس فرایند ۴۹" for m in blocked)
