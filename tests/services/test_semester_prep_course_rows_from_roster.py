"""ساخت و همگام‌سازی ردیف‌های لیست دروس از چارت پیش‌آماده‌سازی."""

from __future__ import annotations

import uuid

import pytest

from app.services.course_committee_roster_service import (
    merge_course_table_rows_with_roster,
    reload_catalog_cache,
    reload_roster_cache,
    validate_semester_prep_course_table_rows,
)


@pytest.fixture(autouse=True)
def _fresh_caches():
    reload_roster_cache()
    reload_catalog_cache()
    yield
    reload_roster_cache()
    reload_catalog_cache()


def test_merge_preserves_schedule_and_drops_foreign_rows():
    roster_rows = [
        {
            "course_name": "تئوری روانکاوی ۲",
            "track": "analytic_psychotherapy",
            "proposed_day": "",
            "proposed_time": "",
            "instructor": "علي علوي",
            "teaching_assistant": "",
        },
        {
            "course_name": "تئوری روانکاوی ۳",
            "track": "analytic_psychotherapy",
            "proposed_day": "",
            "proposed_time": "",
            "instructor": "علي علوي",
            "teaching_assistant": "",
        },
    ]
    existing = [
        {
            "course_name": "تئوری روانکاوی ۲",
            "track": "analytic_psychotherapy",
            "proposed_day": "شنبه",
            "proposed_time": "18:00",
            "instructor": "علي علوي",
            "teaching_assistant": "سارا طراوتي",
        },
        {
            # ردیف دمو / خارج از چارت باید حذف شود
            "course_name": "درس ساختگی",
            "instructor": "شخص ناشناس",
            "proposed_day": "یکشنبه",
        },
    ]
    merged = merge_course_table_rows_with_roster(existing, roster_rows)
    assert len(merged) == 2
    by_course = {r["course_name"]: r for r in merged}
    assert by_course["تئوری روانکاوی ۲"]["proposed_day"] == "شنبه"
    assert by_course["تئوری روانکاوی ۲"]["proposed_time"] == "18:00"
    assert by_course["تئوری روانکاوی ۲"]["teaching_assistant"] == "سارا طراوتي"
    assert by_course["تئوری روانکاوی ۳"]["proposed_day"] == ""
    assert "درس ساختگی" not in by_course


@pytest.mark.asyncio
async def test_operator_saved_course_table_is_not_overwritten_by_roster(db_session):
    from app.services.semester_prep_service import FALL_PREP, apply_pre_filled_fields

    custom = [
        {
            "course_name": "درس سفارشی اپراتور",
            "track": "روان‌درمانی تحلیلی",
            "proposed_day": "یکشنبه",
            "proposed_time": "10:00",
            "instructor": "مدرس آزمایشی",
            "teaching_assistant": "",
        }
    ]
    merged = await apply_pre_filled_fields(
        db_session,
        FALL_PREP,
        "course_list_creation",
        {"courses_fall": custom, "courses_winter": []},
    )
    fall_rows = merged.get("courses_fall") or []
    assert len(fall_rows) == 1
    assert fall_rows[0]["course_name"] == "درس سفارشی اپراتور"
    assert merged.get("courses_winter") == []


@pytest.mark.asyncio
async def test_build_rows_from_roster_includes_authorized_pairs(db_session):
    from app.services.course_committee_roster_service import build_course_table_rows_from_roster

    rows = await build_course_table_rows_from_roster(db_session)
    assert isinstance(rows, list)
    granted = [r for r in rows if r.get("course_name") and r.get("instructor")]
    assert granted, "انتظار می‌رود حداقل یک جفت درس↔مدرس از چارت ساخته شود"
    for r in granted:
        assert r.get("track")
        # رسته باید فارسی باشد، نه کد فنی
        assert "analytic_psychotherapy" not in str(r.get("track"))
        assert not str(r.get("track")).isascii() or "روان" in str(r.get("track"))
        assert "proposed_day" in r
        assert "proposed_time" in r
        # نام مدرس نباید UUID باشد
        assert not (
            len(str(r.get("instructor") or "")) == 36 and "-" in str(r.get("instructor") or "")
        )


def test_resolve_track_display_fa_uses_persian_label():
    from app.services.course_committee_roster_service import resolve_track_display_fa

    label = resolve_track_display_fa("analytic_psychotherapy")
    assert label
    assert label != "analytic_psychotherapy"
    assert "روان" in label or not label.isascii()
    # اگر قبلاً فارسی باشد همان بماند
    assert resolve_track_display_fa(label) == label


@pytest.mark.asyncio
async def test_validate_rejects_instructor_not_authorized_for_course(db_session):
    from app.api.auth import get_password_hash
    from app.models.operational_models import User

    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username="inst_other_course",
            email="inst_other@test.local",
            hashed_password=get_password_hash("demo123"),
            full_name_fa="مدرس درس دیگر",
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

    errors = await validate_semester_prep_course_table_rows(
        db_session,
        [
            {
                "course_name": "theory_inheritance",
                "track": "analytic_psychotherapy",
                "instructor": "مدرس درس دیگر",
            }
        ],
    )
    assert errors
    assert any("مجاز" in e for e in errors)


@pytest.mark.asyncio
async def test_list_members_without_course_includes_unauthorized_with_grants(db_session):
    from app.api.auth import get_password_hash
    from app.models.operational_models import User
    from app.services.course_committee_roster_service import list_members

    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username="inst_grants_payload",
            email="inst_grants@test.local",
            hashed_password=get_password_hash("demo123"),
            full_name_fa="مدرس با مجوز محدود",
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

    members = await list_members(
        db_session,
        track="analytic_psychotherapy",
        kind="instructor",
    )
    hit = next((m for m in members if m.get("label_fa") == "مدرس با مجوز محدود"), None)
    assert hit is not None
    assert "theory_psychoanalysis_2" in (hit.get("authorized_courses") or [])


@pytest.mark.asyncio
async def test_validate_rejects_unknown_course(db_session):
    errors = await validate_semester_prep_course_table_rows(
        db_session,
        [
            {
                "course_name": "درس کاملاً ساختگی که در کاتالوگ نیست",
                "track": "analytic_psychotherapy",
                "instructor": "علي علوي",
            }
        ],
    )
    assert errors
    assert any("کاتالوگ" in e for e in errors)
