"""تست سرویس چارت مدرسین/کمک‌مدرسین کمیته دروس."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.api.auth import get_password_hash
from app.models.operational_models import User
from app.services.course_committee_roster_service import (
    _combined_member_grants,
    _course_refs,
    _grants_include_course,
    enrich_course_table_rows,
    link_user_to_roster,
    list_members,
    list_track_options,
    option_authorized_for_course,
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


def test_option_authorized_for_course_keeps_unticked_chart_members():
    allowed = {"value": "i1", "authorized_courses": ["theory_inheritance"]}
    blocked = {
        "value": "i2",
        "authorized_courses": ["theory_psychoanalysis_2"],
        "tier": 0,
        "roster_legacy": True,
    }
    empty = {"value": "i3", "authorized_courses": [], "tier": 1}
    assert option_authorized_for_course(allowed, "instructor", "theory_inheritance")
    assert not option_authorized_for_course(blocked, "instructor", "theory_inheritance")
    assert option_authorized_for_course(empty, "instructor", "theory_inheritance")


def test_combined_member_grants_unions_json_and_profile():
    class _User:
        profile_meta = {"instructor_authorized_courses": ["theory_2"]}

    entry = {
        "instructor_authorized_courses": ["theory_1"],
        "authorized_courses": ["theory_1"],
    }
    merged = _combined_member_grants(entry, _User(), "instructor")
    assert "theory_1" in merged
    assert "theory_2" in merged


def test_course_refs_include_catalog_aliases():
    refs = _course_refs("تئوری روانکاوی (1)")
    assert "theory_psychoanalysis_1" in refs
    assert _grants_include_course(["theory_psychoanalysis_1"], "تئوری روانکاوی (1)")


def test_add_member_writes_both_grant_keys(tmp_path, monkeypatch):
    from app.services import course_committee_roster_service as svc

    catalog_file = tmp_path / "course_catalog.json"
    catalog_file.write_text(
        '{"courses": [{"value": "c1", "label_fa": "درس یک", "track": "t1"}]}',
        encoding="utf-8",
    )
    roster_file = tmp_path / "course_committee_roster.json"
    roster_file.write_text(
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "instructors": [], "teaching_assistants": []}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_CATALOG_PATH", catalog_file)
    monkeypatch.setattr(svc, "_ROSTER_PATH", roster_file)
    svc.reload_catalog_cache()
    svc.reload_roster_cache()

    svc.add_member_to_roster(
        track="t1",
        kind="instructor",
        name_fa="مدرس جدید تست",
        authorized_courses=["c1"],
    )
    data = svc._load_roster_file()
    row = data["tracks"][0]["instructors"][0]
    assert row["instructor_authorized_courses"] == ["c1"]
    assert row["authorized_courses"] == ["c1"]


@pytest.mark.asyncio
async def test_list_members_includes_unticked_json_roster_member(db_session):
    members = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="instructor",
        course="theory_inheritance",
    )
    names = {m["label_fa"] for m in members}
    assert "پيمانه بهرامي" in names


@pytest.mark.asyncio
async def test_list_members_unions_profile_and_json_grants(db_session):
    db_session.add(
        User(
            id=uuid.uuid4(),
            username="union_grants_inst",
            email="union_grants@test.local",
            hashed_password=get_password_hash("demo123"),
            full_name_fa="علي علوي",
            role="instructor",
            is_active=True,
            profile_meta={
                "course_committee_tracks": ["analytic_psychotherapy"],
                "member_kind": "instructor",
                "instructor_authorized_courses": ["theory_inheritance"],
            },
        )
    )
    await db_session.commit()

    members = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="instructor",
        course="theory_inheritance",
    )
    hit = next((m for m in members if m["label_fa"] == "علي علوي"), None)
    assert hit is not None
    grants = hit.get("authorized_courses") or []
    assert "theory_inheritance" in grants
    assert "theory_psychoanalysis_2" in grants


@pytest.mark.asyncio
async def test_roster_detail_role_and_course_count(db_session):
    from app.services.course_committee_roster_service import list_track_roster_detail

    detail = await list_track_roster_detail(db_session, track="analytic_psychotherapy")
    instructors = detail["instructors"]
    assert instructors
    edu = next(
        (m for m in instructors if m.get("role_code") == "educational_instructor"),
        None,
    )
    assert edu is not None
    assert edu["role_label_fa"] == "مدرس آموزشی"
    assert "course_count" in edu
    assert isinstance(edu["course_count"], int)

    regular = next(
        (m for m in instructors if m.get("role_code") == "instructor"),
        None,
    )
    assert regular is not None
    assert regular["role_label_fa"] == "مدرس"

    tas = detail["teaching_assistants"]
    if tas:
        assert tas[0]["role_label_fa"] == "کمک‌مدرس"
        assert tas[0]["role_code"] == "teaching_assistant"


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
    theory1 = next(o for o in opts if o["value"] == "theory_psychoanalysis_1")
    assert theory1.get("units") == 2
    assert theory1.get("curriculum_term") == 1
    assert theory1.get("program_kind") == "introductory"


def test_add_course_to_catalog(tmp_path, monkeypatch):
    from app.services import course_committee_roster_service as svc

    catalog_file = tmp_path / "course_catalog.json"
    catalog_file.write_text('{"courses": []}', encoding="utf-8")
    roster_file = tmp_path / "course_committee_roster.json"
    roster_file.write_text(
        '{"tracks": [{"code": "analytic_psychotherapy", "name_fa": "روان‌درمانی تحلیلی",'
        ' "instructors": [], "teaching_assistants": []}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_CATALOG_PATH", catalog_file)
    monkeypatch.setattr(svc, "_ROSTER_PATH", roster_file)
    svc.reload_catalog_cache()
    svc.reload_roster_cache()

    with pytest.raises(ValueError, match="رسته"):
        svc.add_course_to_catalog("درس بدون رسته")

    with pytest.raises(ValueError, match="رسته"):
        svc.add_course_to_catalog("درس آزمایشی جدید", track="missing_track")

    created = svc.add_course_to_catalog("درس آزمایشی جدید", track="analytic_psychotherapy")
    assert created["label_fa"] == "درس آزمایشی جدید"
    assert created["value"]
    assert created["track"] == "analytic_psychotherapy"

    with_units = svc.add_course_to_catalog(
        "درس دو واحدی SOP",
        track="analytic_psychotherapy",
        units=2,
        curriculum_term=1,
        program_kind="introductory",
        class_hours="1:30",
        retake_exam=True,
    )
    assert with_units["units"] == 2
    assert with_units["curriculum_term"] == 1
    assert with_units["class_hours"] == "1:30"
    assert with_units["retake_exam"] is True

    opts = svc.list_course_catalog_options()
    assert any(o["label_fa"] == "درس آزمایشی جدید" and o.get("track") == "analytic_psychotherapy" for o in opts)

    again = svc.add_course_to_catalog("درس آزمایشی جدید", track="analytic_psychotherapy")
    assert again["label_fa"] == "درس آزمایشی جدید"
    assert again["track"] == "analytic_psychotherapy"


def test_update_and_remove_course_and_track(tmp_path, monkeypatch):
    from app.services import course_committee_roster_service as svc

    catalog_file = tmp_path / "course_catalog.json"
    catalog_file.write_text('{"courses": []}', encoding="utf-8")
    roster_file = tmp_path / "course_committee_roster.json"
    roster_file.write_text(
        '{"tracks": [{"code": "analytic_psychotherapy", "name_fa": "روان‌درمانی تحلیلی",'
        ' "instructors": [], "teaching_assistants": []}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_CATALOG_PATH", catalog_file)
    monkeypatch.setattr(svc, "_ROSTER_PATH", roster_file)
    svc.reload_catalog_cache()
    svc.reload_roster_cache()

    created = svc.add_course_to_catalog("درس موقت", track="analytic_psychotherapy")
    updated = svc.update_course_in_catalog(
        created["value"],
        name_fa="درس موقت ویرایش‌شده",
        track="analytic_psychotherapy",
        units=3,
        curriculum_term=2,
        program_kind="introductory",
    )
    assert updated["units"] == 3
    assert updated["curriculum_term"] == 2
    assert updated["label_fa"] == "درس موقت ویرایش‌شده"

    assert svc.remove_course_from_catalog(created["value"]) is True
    assert all(o["value"] != created["value"] for o in svc.list_course_catalog_options())

    extra = svc.add_track_to_roster("رسته موقت تست")
    assert svc.remove_track_from_roster(extra["value"]) is True

    with pytest.raises(ValueError, match="درس"):
        svc.add_course_to_catalog("وابسته", track="analytic_psychotherapy")
        svc.remove_track_from_roster("analytic_psychotherapy")


@pytest.mark.asyncio
async def test_update_member_courses_roster_only(tmp_path, monkeypatch, db_session):
    from app.services import course_committee_roster_service as svc

    catalog_file = tmp_path / "course_catalog.json"
    catalog_file.write_text(
        '{"courses": [{"value": "c1", "label_fa": "درس یک", "track": "t1"}]}',
        encoding="utf-8",
    )
    roster_file = tmp_path / "course_committee_roster.json"
    roster_file.write_text(
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "instructors": [{"roster_key": "i1", "name_fa": "مدرس تست"}],'
        ' "teaching_assistants": []}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_CATALOG_PATH", catalog_file)
    monkeypatch.setattr(svc, "_ROSTER_PATH", roster_file)
    svc.reload_catalog_cache()
    svc.reload_roster_cache()

    result = await svc.update_member_courses(
        db_session,
        track="t1",
        kind="instructor",
        name_fa="مدرس تست",
        authorized_courses=["c1"],
    )
    assert result["authorized_courses"] == ["c1"]
    detail = await svc.list_track_roster_detail(db_session, track="t1")
    inst = next(m for m in detail["instructors"] if m["label_fa"] == "مدرس تست")
    assert "c1" in (inst.get("authorized_courses") or [])


@pytest.mark.asyncio
async def test_change_member_kind_instructor_to_ta(tmp_path, monkeypatch, db_session):
    from app.services import course_committee_roster_service as svc

    catalog_file = tmp_path / "course_catalog.json"
    catalog_file.write_text(
        '{"courses": [{"value": "c1", "label_fa": "درس یک", "track": "t1"}]}',
        encoding="utf-8",
    )
    roster_file = tmp_path / "course_committee_roster.json"
    roster_file.write_text(
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "instructors": [{"roster_key": "i1", "name_fa": "مدرس تست",'
        ' "instructor_authorized_courses": ["c1"], "authorized_courses": ["c1"]}],'
        ' "teaching_assistants": []}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_CATALOG_PATH", catalog_file)
    monkeypatch.setattr(svc, "_ROSTER_PATH", roster_file)
    svc.reload_catalog_cache()
    svc.reload_roster_cache()

    result = await svc.change_member_kind(
        db_session,
        track="t1",
        kind="instructor",
        name_fa="مدرس تست",
        new_role="teaching_assistant",
    )
    assert result["role_code"] == "teaching_assistant"
    assert result["kind"] == "teaching_assistant"
    detail = await svc.list_track_roster_detail(db_session, track="t1")
    assert all(m["label_fa"] != "مدرس تست" for m in detail["instructors"])
    ta = next(m for m in detail["teaching_assistants"] if m["label_fa"] == "مدرس تست")
    assert ta["role_code"] == "teaching_assistant"
    assert "c1" in (ta.get("authorized_courses") or [])


@pytest.mark.asyncio
async def test_change_member_kind_to_educational_instructor(tmp_path, monkeypatch, db_session):
    from app.services import course_committee_roster_service as svc

    catalog_file = tmp_path / "course_catalog.json"
    catalog_file.write_text('{"courses": []}', encoding="utf-8")
    roster_file = tmp_path / "course_committee_roster.json"
    roster_file.write_text(
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "educational_instructor": {"roster_key": "educational_instructor",'
        ' "name_fa": "مدرس آموزشی قبلی", "tier": 0},'
        ' "instructors": [{"roster_key": "i1", "name_fa": "مدرس جدید", "tier": 2}],'
        ' "teaching_assistants": []}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_CATALOG_PATH", catalog_file)
    monkeypatch.setattr(svc, "_ROSTER_PATH", roster_file)
    svc.reload_catalog_cache()
    svc.reload_roster_cache()

    result = await svc.change_member_kind(
        db_session,
        track="t1",
        kind="instructor",
        name_fa="مدرس جدید",
        new_role="educational_instructor",
    )
    assert result["role_code"] == "educational_instructor"
    detail = await svc.list_track_roster_detail(db_session, track="t1")
    edu = next(m for m in detail["instructors"] if m.get("role_code") == "educational_instructor")
    assert edu["label_fa"] == "مدرس جدید"
    # مدرس آموزشی قبلی باید به لیست مدرسین عادی برود
    assert any(m["label_fa"] == "مدرس آموزشی قبلی" for m in detail["instructors"])


@pytest.mark.asyncio
async def test_add_member_as_educational_instructor(tmp_path, monkeypatch, db_session):
    from app.services import course_committee_roster_service as svc

    catalog_file = tmp_path / "course_catalog.json"
    catalog_file.write_text(
        '{"courses": [{"value": "c1", "label_fa": "درس یک", "track": "t1"}]}',
        encoding="utf-8",
    )
    roster_file = tmp_path / "course_committee_roster.json"
    roster_file.write_text(
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "educational_instructor": {"roster_key": "educational_instructor",'
        ' "name_fa": "مدرس آموزشی قبلی", "tier": 0},'
        ' "instructors": [], "teaching_assistants": []}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "_CATALOG_PATH", catalog_file)
    monkeypatch.setattr(svc, "_ROSTER_PATH", roster_file)
    svc.reload_catalog_cache()
    svc.reload_roster_cache()

    added = svc.add_member_to_roster(
        track="t1",
        kind="educational_instructor",
        name_fa="عضو جدید آموزشی",
        authorized_courses=["c1"],
    )
    assert added["label_fa"] == "عضو جدید آموزشی"
    assert added["value"] == "educational_instructor"

    detail = await svc.list_track_roster_detail(db_session, track="t1")
    edu = next(m for m in detail["instructors"] if m.get("role_code") == "educational_instructor")
    assert edu["label_fa"] == "عضو جدید آموزشی"
    assert "c1" in (edu.get("authorized_courses") or [])
    assert any(m["label_fa"] == "مدرس آموزشی قبلی" for m in detail["instructors"])


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


@pytest.mark.asyncio
async def test_list_members_legacy_ta_hidden_without_course_grant(db_session):
    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username="ta_legacy_test",
            email="ta_legacy@test.local",
            hashed_password=get_password_hash("demo123"),
            full_name_fa="کمک‌مدرس قدیمی",
            role="teaching_assistant",
            is_active=True,
            profile_meta={
                "course_committee_tracks": ["analytic_psychotherapy"],
                "member_kind": "teaching_assistant",
                "roster_legacy": True,
            },
        )
    )
    await db_session.commit()

    filtered = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="teaching_assistant",
        course="theory_inheritance",
    )
    labels = {m["label_fa"] for m in filtered}
    assert "کمک‌مدرس قدیمی" not in labels


@pytest.mark.asyncio
async def test_list_members_include_all_skips_course_filter(db_session):
    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username="ta_no_grants",
            email="ta_nog@test.local",
            hashed_password=get_password_hash("demo123"),
            full_name_fa="کمک‌مدرس بدون مجوز",
            role="teaching_assistant",
            is_active=True,
            profile_meta={
                "course_committee_tracks": ["analytic_psychotherapy"],
                "member_kind": "teaching_assistant",
            },
        )
    )
    await db_session.commit()

    blocked = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="teaching_assistant",
        course="theory_inheritance",
    )
    assert not any(m["label_fa"] == "کمک‌مدرس بدون مجوز" for m in blocked)

    all_members = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="teaching_assistant",
        course="theory_inheritance",
        include_all=True,
    )
    assert any(m["label_fa"] == "کمک‌مدرس بدون مجوز" for m in all_members)


@pytest.mark.asyncio
async def test_link_user_to_roster_sets_role_and_legacy(db_session):
    from app.models.operational_models import Student

    uid = uuid.uuid4()
    sid = uuid.uuid4()
    user = User(
        id=uid,
        username="student_link_roster",
        email="student_link@test.local",
        hashed_password=get_password_hash("demo123"),
        full_name_fa="دانشجوی کمک‌مدرس",
        role="student",
        is_active=True,
        profile_meta={},
    )
    student = Student(
        id=sid,
        user_id=uid,
        student_code="ST-LINK-001",
        course_type="comprehensive",
        extra_data={},
    )
    db_session.add(user)
    db_session.add(student)
    await db_session.commit()

    linked = await link_user_to_roster(
        db_session,
        user,
        track="analytic_psychotherapy",
        kind="teaching_assistant",
        roster_legacy=True,
        authorized_courses=[],
    )
    await db_session.commit()
    await db_session.refresh(linked)
    await db_session.refresh(student)

    assert linked.role == "teaching_assistant"
    assert (linked.profile_meta or {}).get("roster_legacy") is True
    assert "analytic_psychotherapy" in (linked.profile_meta or {}).get("course_committee_tracks", [])
    assert (student.extra_data or {}).get("is_teaching_assistant") is True
    assert (student.extra_data or {}).get("ta_registered") is True


def _write_tmp_roster(tmp_path, monkeypatch, payload: str):
    from app.services import course_committee_roster_service as svc

    roster_file = tmp_path / "course_committee_roster.json"
    roster_file.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(svc, "_ROSTER_PATH", roster_file)
    svc.reload_roster_cache()
    return svc


def test_remove_last_instructor_and_last_ta(tmp_path, monkeypatch):
    svc = _write_tmp_roster(
        tmp_path,
        monkeypatch,
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "educational_instructor": {"roster_key": "educational_instructor",'
        ' "name_fa": "مدرس آموزشی", "tier": 0},'
        ' "instructors": [{"roster_key": "i1", "name_fa": "تنها مدرس"}],'
        ' "teaching_assistants": [{"roster_key": "ta1", "name_fa": "تنها کمک‌مدرس"}]}]}',
    )

    assert svc.remove_member_from_roster(track="t1", kind="instructor", name_fa="تنها مدرس") is True
    assert svc.remove_member_from_roster(track="t1", kind="teaching_assistant", name_fa="تنها کمک‌مدرس") is True
    assert svc.remove_member_from_roster(track="t1", kind="instructor", name_fa="مدرس آموزشی") is True
    track = svc.get_track_by_code("t1")
    assert track.get("instructors") == []
    assert track.get("teaching_assistants") == []
    assert track.get("educational_instructor") is None


def test_remove_last_member_arabic_yeh_mismatch(tmp_path, monkeypatch):
    svc = _write_tmp_roster(
        tmp_path,
        monkeypatch,
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "instructors": [{"roster_key": "i1", "name_fa": "ادريس صالحي"}],'
        ' "teaching_assistants": []}]}',
    )

    assert svc.remove_member_from_roster(track="t1", kind="instructor", name_fa="ادریس صالحی") is True
    assert svc.get_track_by_code("t1").get("instructors") == []


@pytest.mark.asyncio
async def test_delete_last_db_only_member_unlinks_user(tmp_path, monkeypatch, db_session):
    svc = _write_tmp_roster(
        tmp_path,
        monkeypatch,
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "instructors": [], "teaching_assistants": []}]}',
    )
    uid = uuid.uuid4()
    user = User(
        id=uid,
        username="cc_last_member_del",
        email="cc_last_member_del@test.local",
        hashed_password=get_password_hash("demo123"),
        full_name_fa="مدرس فقط دیتابیس",
        role="instructor",
        is_active=True,
        profile_meta={
            "course_committee_tracks": ["t1"],
            "member_kind": "instructor",
            "tier": 2,
        },
    )
    db_session.add(user)
    await db_session.commit()

    detail = await svc.list_track_roster_detail(db_session, track="t1")
    assert any(m["label_fa"] == "مدرس فقط دیتابیس" for m in detail["instructors"])

    removed = await svc.delete_roster_member(
        db_session,
        track="t1",
        kind="instructor",
        name_fa="مدرس فقط دیتابیس",
        user_id=uid,
    )
    assert removed is True
    await db_session.commit()
    await db_session.refresh(user)
    assert "t1" not in (user.profile_meta or {}).get("course_committee_tracks", [])
    detail = await svc.list_track_roster_detail(db_session, track="t1")
    assert detail["instructors"] == []


@pytest.mark.asyncio
async def test_list_detail_merges_arabic_persian_duplicate_names(tmp_path, monkeypatch, db_session):
    svc = _write_tmp_roster(
        tmp_path,
        monkeypatch,
        '{"tracks": [{"code": "t1", "name_fa": "رسته تست",'
        ' "instructors": [{"roster_key": "i1", "name_fa": "ادريس صالحي", "tier": 1}],'
        ' "teaching_assistants": []}]}',
    )
    uid = uuid.uuid4()
    user = User(
        id=uid,
        username="cc_dup_name",
        email="cc_dup_name@test.local",
        hashed_password=get_password_hash("demo123"),
        full_name_fa="ادریس صالحی",
        role="instructor",
        is_active=True,
        profile_meta={
            "course_committee_tracks": ["t1"],
            "member_kind": "instructor",
        },
    )
    db_session.add(user)
    await db_session.commit()

    detail = await svc.list_track_roster_detail(db_session, track="t1")
    names = [m["label_fa"] for m in detail["instructors"]]
    assert len(names) == 1
    assert names[0] in {"ادريس صالحي", "ادریس صالحی"}
