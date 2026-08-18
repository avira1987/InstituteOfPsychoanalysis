"""Tests for semester preparation institute workflow."""

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_service import (
    FALL_PREP,
    WINTER_PREP,
    ensure_fall_prep_started,
    get_active_prep_instance,
    get_or_start_prep_instance,
    should_auto_start_winter,
)


@pytest.mark.asyncio
async def test_ensure_institute_operational_student_idempotent(db_session: AsyncSession):
    from app.services.institute_operational_anchor import (
        anchor_public_info,
        is_institute_operational_student,
    )

    a = await ensure_institute_operational_student(db_session)
    b = await ensure_institute_operational_student(db_session)
    assert a.id == b.id
    assert a.student_code == "INST-OPS"
    assert is_institute_operational_student(a) is True
    info = anchor_public_info(a)
    assert info["is_system"] is True
    assert info["student_code"] == "INST-OPS"
    assert "student_id" in info


@pytest.mark.asyncio
async def test_build_prep_status_includes_anchor_panel_fields(db_session: AsyncSession):
    from app.services.semester_prep_service import build_prep_status

    status = await build_prep_status(db_session)
    assert status["anchor_student_code"] == "INST-OPS"
    assert status["anchor"]["student_code"] == "INST-OPS"
    assert status["anchor"]["is_system"] is True
    assert status["anchor"]["hub_path"] == "/panel/semester-prep"
    assert "active_count" in status["anchor"]
    assert "readiness_ready" in status["anchor"]



@pytest.mark.asyncio
async def test_get_or_start_fall_prep_idempotent(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst1, created1 = await get_or_start_prep_instance(
        db_session,
        FALL_PREP,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    assert created1 is True
    assert inst1.current_state_code == "calendar_entry"
    ctx = dict(inst1.context_data or {})
    assert ctx.get("calendar_sla_deadline_at")

    inst2, created2 = await get_or_start_prep_instance(
        db_session,
        FALL_PREP,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    assert created2 is False
    assert inst2.id == inst1.id


@pytest.mark.asyncio
async def test_winter_requires_fall_published(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    with pytest.raises(ValueError, match="fall_semester_preparation"):
        await get_or_start_prep_instance(
            db_session,
            WINTER_PREP,
            actor_id=sample_user.id,
            actor_role="admin",
        )


@pytest.mark.asyncio
async def test_should_auto_start_winter_within_window(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    anchor = await ensure_institute_operational_student(db_session)
    engine = StateMachineEngine(db_session)
    fall = await engine.start_process(
        process_code=FALL_PREP,
        student_id=anchor.id,
        actor_id=sample_user.id,
        actor_role="admin",
        initial_context={
            "winter_start_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )
    fall.is_completed = True
    fall.current_state_code = "published"
    fall.completed_at = datetime.now(timezone.utc)
    await db_session.commit()

    assert await should_auto_start_winter(db_session, today=date.today()) is True
    assert await get_active_prep_instance(db_session, WINTER_PREP) is None


@pytest.mark.asyncio
async def test_ensure_fall_prep_started(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    hit = await ensure_fall_prep_started(db_session, actor_id=sample_user.id, actor_role="admin")
    assert hit["process_code"] == FALL_PREP
    assert hit["created"] is True


@pytest.mark.asyncio
async def test_build_prep_status_includes_step_sla_deadline(db_session: AsyncSession, sample_user):
    from app.services.semester_prep_service import build_prep_status

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    await db_session.commit()

    status = await build_prep_status(db_session)
    entry = status["processes"][FALL_PREP]
    assert entry["active"] is True
    assert entry.get("sla_deadline_at")
    assert entry.get("calendar_sla_deadline_at")
    assert "اعضای کمیته دروس" in (entry.get("sla_warning_recipients_fa") or [])


@pytest.mark.asyncio
async def test_build_prep_status_tuition_sla_after_transition(db_session: AsyncSession, sample_user):
    from app.services.semester_prep_service import build_prep_status

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    engine = StateMachineEngine(db_session)
    await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="calendar_submitted",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()

    status = await build_prep_status(db_session)
    entry = status["processes"][FALL_PREP]
    assert entry["current_state"] == "tuition_entry"
    assert entry.get("sla_deadline_at")
    assert "مدیر آموزش" in (entry.get("sla_warning_recipients_fa") or [])


@pytest.mark.asyncio
async def test_apply_pre_filled_from_fall_courses(db_session: AsyncSession, sample_user):
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.semester_prep_service import (
        FALL_PREP,
        WINTER_PREP,
        apply_pre_filled_fields,
        get_or_start_prep_instance,
    )

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    fall, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    sample_courses = [
        {
            "course_name": "تئوری روانکاوی ۲",
            "track": "analytic_psychotherapy",
            "proposed_day": "شنبه",
            "proposed_time": "18:00",
            "instructor": "علي علوي",
            "teaching_assistant": "",
        }
    ]
    ctx = dict(fall.context_data or {})
    ctx["courses_winter"] = sample_courses
    fall.context_data = ctx
    flag_modified(fall, "context_data")
    fall.is_completed = True
    fall.current_state_code = "published"
    fall.completed_at = datetime.now(timezone.utc)
    await db_session.commit()

    merged = await apply_pre_filled_fields(
        db_session,
        WINTER_PREP,
        "course_list_review",
        {},
    )
    courses = merged.get("courses") or []
    assert isinstance(courses, list)
    assert courses, "جداول باید از چارت پیش‌آماده‌سازی پر شوند"
    # روز/ساعت ردیف همگام با پاییز برای جفت درس↔مدرس حفظ شده باشد
    matched = [
        r
        for r in courses
        if (r.get("course_name") or "").strip() in ("تئوری روانکاوی ۲", "theory_psychoanalysis_2")
        and "علو" in (r.get("instructor") or "")
    ]
    assert matched, courses
    assert matched[0].get("proposed_day") == "شنبه"
    assert matched[0].get("proposed_time") == "18:00"

def test_apply_course_finalization_prefill_from_fall_course_lists():
    from app.services.semester_prep_service import (
        FALL_PREP,
        _apply_course_finalization_prefill,
    )

    draft_fall = [
        {
            "course_name": "تئوری ۱",
            "track": "analytic_psychotherapy",
            "proposed_day": "شنبه",
            "proposed_time": "18:00",
            "instructor": "دکتر الف",
            "teaching_assistant": "خانم ب",
        }
    ]
    draft_winter = [
        {
            "course_name": "عملی ۲",
            "track": "analytic_psychotherapy",
            "day": "دوشنبه",
            "time": "17:30",
            "instructor": "دکتر ج",
        }
    ]
    ctx = {"courses_fall": draft_fall, "courses_winter": draft_winter}
    merged = _apply_course_finalization_prefill(FALL_PREP, "course_finalization", ctx)
    assert merged["courses_finalized_fall"][0]["course_name"] == "تئوری ۱"
    assert merged["courses_finalized_fall"][0]["day"] == "شنبه"
    assert merged["courses_finalized_fall"][0]["time"] == "18:00"
    # رسته فارسی برای نمایش اپراتور
    assert merged["courses_finalized_fall"][0]["track"] != "analytic_psychotherapy"
    assert "روان" in merged["courses_finalized_fall"][0]["track"]
    assert merged["courses_finalized_winter"][0]["course_name"] == "عملی ۲"
    assert merged["courses_finalized_winter"][0]["day"] == "دوشنبه"
    assert merged["courses_finalized_winter"][0]["track"] != "analytic_psychotherapy"


def test_apply_course_finalization_prefill_over_placeholder_rows():
    from app.services.semester_prep_service import (
        FALL_PREP,
        _apply_course_finalization_prefill,
    )

    draft_fall = [
        {
            "course_name": "تئوری ۱",
            "track": "آشنایی",
            "proposed_day": "شنبه",
            "proposed_time": "18:00",
            "instructor": "دکتر الف",
        }
    ]
    ctx = {
        "courses_fall": draft_fall,
        "courses_finalized_fall": [
            {
                "course_name": "",
                "track": "",
                "day": "",
                "time": "",
                "instructor": "",
                "teaching_assistant": "",
                "classroom_location": "",
                "instructor_coordinated": False,
            }
        ],
    }
    merged = _apply_course_finalization_prefill(FALL_PREP, "course_finalization", ctx)
    assert merged["courses_finalized_fall"][0]["course_name"] == "تئوری ۱"
    assert merged["courses_finalized_fall"][0]["day"] == "شنبه"


def test_apply_course_finalization_prefill_skips_blank_draft_rows():
    from app.services.semester_prep_service import (
        FALL_PREP,
        _apply_course_finalization_prefill,
    )

    ctx = {
        "courses_fall": [
            {
                "course_name": "تئوری ۱",
                "track": "آشنایی",
                "proposed_day": "شنبه",
                "instructor": "دکتر الف",
            },
            {"course_name": "", "proposed_day": "", "instructor": ""},
        ],
        "courses_winter": [
            {
                "course_name": "عملی ۲",
                "proposed_day": "دوشنبه",
                "instructor": "دکتر ب",
            }
        ],
    }
    merged = _apply_course_finalization_prefill(FALL_PREP, "course_finalization", ctx)
    assert [r["course_name"] for r in merged["courses_finalized_fall"]] == ["تئوری ۱"]
    assert merged["courses_finalized_fall"][0]["instructor"] == "دکتر الف"
    assert [r["course_name"] for r in merged["courses_finalized_winter"]] == ["عملی ۲"]


def test_apply_course_finalization_prefill_resyncs_after_step4_edit():
    """ویرایش لیست/ساعات مرحلهٔ ۴ باید جدول مرحلهٔ ۵ را جایگزین کند، نه دادهٔ قدیمی را نگه دارد."""
    from app.services.semester_prep_service import (
        FALL_PREP,
        WINTER_PREP,
        _apply_course_finalization_prefill,
    )

    ctx = {
        "courses_fall": [
            {
                "course_name": "تئوری ۱ ویرایش‌شده",
                "course_code": "theory_1",
                "track": "آشنایی",
                "proposed_day": "یکشنبه",
                "proposed_time": "19:00",
                "instructor": "دکتر جدید",
            },
            {
                "course_name": "درس تازه‌اضافه‌شده",
                "track": "آشنایی",
                "proposed_day": "سه‌شنبه",
                "proposed_time": "16:00",
                "instructor": "دکتر ج",
            },
        ],
        "courses_winter": [
            {
                "course_name": "عملی ۲ جدید",
                "track": "جامع",
                "proposed_day": "چهارشنبه",
                "proposed_time": "18:30",
                "instructor": "دکتر د",
            }
        ],
        "courses_finalized_fall": [
            {
                "course_name": "تئوری ۱",
                "course_code": "theory_1",
                "track": "آشنایی",
                "day": "شنبه",
                "time": "18:00",
                "instructor": "دکتر الف",
                "classroom_location": "کلاس ۱",
                "instructor_coordinated": True,
            },
            {
                "course_name": "درس حذف‌شده",
                "track": "آشنایی",
                "day": "دوشنبه",
                "time": "10:00",
                "instructor": "دکتر قدیم",
                "classroom_location": "کلاس قدیم",
                "instructor_coordinated": True,
            },
        ],
        "courses_finalized_winter": [
            {
                "course_name": "عملی ۲",
                "track": "جامع",
                "day": "دوشنبه",
                "time": "17:30",
                "instructor": "دکتر ب",
                "classroom_location": "کلاس زمستان",
                "instructor_coordinated": True,
            }
        ],
    }
    merged = _apply_course_finalization_prefill(FALL_PREP, "course_finalization", ctx)
    fall_rows = merged["courses_finalized_fall"]
    assert [r["course_name"] for r in fall_rows] == ["تئوری ۱ ویرایش‌شده", "درس تازه‌اضافه‌شده"]
    assert fall_rows[0]["day"] == "یکشنبه"
    assert fall_rows[0]["time"] == "19:00"
    assert fall_rows[0]["instructor"] == "دکتر جدید"
    assert fall_rows[0]["classroom_location"] == "کلاس ۱"
    assert fall_rows[0]["instructor_coordinated"] is True
    assert fall_rows[1]["day"] == "سه‌شنبه"
    assert fall_rows[1]["classroom_location"] == ""
    assert fall_rows[1]["instructor_coordinated"] is False

    winter_rows = merged["courses_finalized_winter"]
    assert len(winter_rows) == 1
    assert winter_rows[0]["course_name"] == "عملی ۲ جدید"
    assert winter_rows[0]["day"] == "چهارشنبه"
    assert winter_rows[0]["time"] == "18:30"
    assert winter_rows[0]["instructor"] == "دکتر د"

    winter_ctx = {
        "courses": [
            {
                "course_name": "عملی زمستان ویرایش",
                "course_code": "winter_prac",
                "proposed_day": "پنجشنبه",
                "proposed_time": "11:00",
                "instructor": "دکتر و",
            }
        ],
        "courses_finalized": [
            {
                "course_name": "عملی زمستان",
                "course_code": "winter_prac",
                "day": "دوشنبه",
                "time": "09:00",
                "instructor": "دکتر قدیم",
                "classroom_location": "سالن ۲",
                "instructor_coordinated": True,
            }
        ],
    }
    winter_merged = _apply_course_finalization_prefill(
        WINTER_PREP, "course_finalization", winter_ctx
    )
    wrow = winter_merged["courses_finalized"][0]
    assert wrow["course_name"] == "عملی زمستان ویرایش"
    assert wrow["day"] == "پنجشنبه"
    assert wrow["time"] == "11:00"
    assert wrow["instructor"] == "دکتر و"
    assert wrow["classroom_location"] == "سالن ۲"
    assert wrow["instructor_coordinated"] is True


def test_apply_course_finalization_form_save_keeps_edited_hours_and_writes_back():
    """ذخیرهٔ مرحلهٔ ۵ باید روز/ساعت ویرایش‌شده را نگه دارد و به پیش‌نویس ۴ برگرداند."""
    from app.services.semester_prep_service import (
        FALL_PREP,
        WINTER_PREP,
        apply_course_finalization_form_save,
    )

    ctx = {
        "courses_fall": [
            {
                "course_name": "تئوری ۱",
                "course_code": "theory_1",
                "track": "آشنایی",
                "proposed_day": "شنبه",
                "proposed_time": "18:00",
                "instructor": "دکتر الف",
            }
        ],
        "courses_winter": [
            {
                "course_name": "عملی ۲",
                "proposed_day": "دوشنبه",
                "proposed_time": "17:30",
                "instructor": "دکتر ب",
            }
        ],
        # جدول نهایی پس از prefill از مرحلهٔ ۴ (ساعت قدیم)
        "courses_finalized_fall": [
            {
                "course_name": "تئوری ۱",
                "course_code": "theory_1",
                "track": "آشنایی",
                "day": "شنبه",
                "time": "18:00",
                "instructor": "دکتر الف",
                "classroom_location": "",
                "instructor_coordinated": False,
            }
        ],
        "courses_finalized_winter": [
            {
                "course_name": "عملی ۲",
                "day": "دوشنبه",
                "time": "17:30",
                "instructor": "دکتر ب",
                "classroom_location": "",
                "instructor_coordinated": False,
            }
        ],
    }
    submitted = {
        "courses_finalized_fall": [
            {
                "course_name": "تئوری ۱",
                "course_code": "theory_1",
                "track": "آشنایی",
                "day": "یکشنبه",
                "time": "19:30",
                "instructor": "دکتر الف",
                "classroom_location": "کلاس ۱",
                "instructor_coordinated": True,
            }
        ],
        "courses_finalized_winter": [
            {
                "course_name": "عملی ۲",
                "day": "سه‌شنبه",
                "time": "16:00",
                "instructor": "دکتر ب",
                "classroom_location": "",
                "instructor_coordinated": True,
            }
        ],
    }
    saved = apply_course_finalization_form_save(FALL_PREP, ctx, submitted)
    assert saved["courses_finalized_fall"][0]["day"] == "یکشنبه"
    assert saved["courses_finalized_fall"][0]["time"] == "19:30"
    assert saved["courses_finalized_fall"][0]["classroom_location"] == "کلاس ۱"
    assert saved["courses_finalized_fall"][0]["instructor_coordinated"] is True
    assert saved["courses_fall"][0]["proposed_day"] == "یکشنبه"
    assert saved["courses_fall"][0]["proposed_time"] == "19:30"
    assert saved["courses_winter"][0]["proposed_day"] == "سه‌شنبه"
    assert saved["courses_winter"][0]["proposed_time"] == "16:00"

    winter_ctx = {
        "courses": [
            {
                "course_name": "عملی زمستان",
                "course_code": "winter_prac",
                "proposed_day": "دوشنبه",
                "proposed_time": "09:00",
                "instructor": "دکتر و",
            }
        ],
        "courses_finalized": [
            {
                "course_name": "عملی زمستان",
                "course_code": "winter_prac",
                "day": "دوشنبه",
                "time": "09:00",
                "instructor": "دکتر و",
            }
        ],
    }
    winter_saved = apply_course_finalization_form_save(
        WINTER_PREP,
        winter_ctx,
        {
            "courses_finalized": [
                {
                    "course_name": "عملی زمستان",
                    "course_code": "winter_prac",
                    "day": "چهارشنبه",
                    "time": "14:00",
                    "instructor": "دکتر و",
                    "classroom_location": "سالن ۲",
                    "instructor_coordinated": True,
                }
            ]
        },
    )
    assert winter_saved["courses_finalized"][0]["day"] == "چهارشنبه"
    assert winter_saved["courses_finalized"][0]["time"] == "14:00"
    assert winter_saved["courses"][0]["proposed_day"] == "چهارشنبه"
    assert winter_saved["courses"][0]["proposed_time"] == "14:00"


def test_merge_course_finalization_draft_writeback_survives_form_sanitize():
    """پس از sanitize فرم مرحلهٔ ۵، پیش‌نویس مرحلهٔ ۴ باید دوباره به payload برگردد."""
    from app.meta.process_forms import get_process_forms
    from app.meta.student_step_forms import sanitize_operator_form_values
    from app.services.semester_prep_service import merge_course_finalization_draft_writeback

    forms = get_process_forms("fall_semester_preparation", state_code="course_finalization")
    form_values = {
        "courses_finalized_fall": [{"course_name": "تئوری ۱", "day": "یکشنبه"}],
        "courses_finalized_winter": [{"course_name": "عملی ۲", "day": "سه‌شنبه"}],
        "courses_fall": [{"course_name": "تئوری ۱", "proposed_day": "یکشنبه"}],
        "courses_winter": [{"course_name": "عملی ۲", "proposed_day": "سه‌شنبه"}],
    }
    sanitized = sanitize_operator_form_values(forms, form_values)
    assert "courses_fall" not in sanitized
    assert "courses_winter" not in sanitized
    merged = merge_course_finalization_draft_writeback(sanitized, form_values)
    assert merged["courses_fall"][0]["proposed_day"] == "یکشنبه"
    assert merged["courses_winter"][0]["proposed_day"] == "سه‌شنبه"
    assert merged["courses_finalized_fall"][0]["course_name"] == "تئوری ۱"


def test_course_finalization_prefill_still_takes_hours_from_step4_after_step5_edit():
    """ورود مجدد به مرحلهٔ ۵ بعد از ویرایش مرحلهٔ ۴ باید ساعت جدید ۴ را بیاورد."""
    from app.services.semester_prep_service import (
        FALL_PREP,
        _apply_course_finalization_prefill,
    )

    ctx = {
        "courses_fall": [
            {
                "course_name": "تئوری ۱",
                "course_code": "theory_1",
                "proposed_day": "پنجشنبه",
                "proposed_time": "12:00",
                "instructor": "دکتر جدید",
            }
        ],
        "courses_winter": [],
        "courses_finalized_fall": [
            {
                "course_name": "تئوری ۱",
                "course_code": "theory_1",
                "day": "یکشنبه",
                "time": "19:30",
                "instructor": "دکتر الف",
                "classroom_location": "کلاس ۱",
                "instructor_coordinated": True,
            }
        ],
    }
    merged = _apply_course_finalization_prefill(FALL_PREP, "course_finalization", ctx)
    row = merged["courses_finalized_fall"][0]
    assert row["day"] == "پنجشنبه"
    assert row["time"] == "12:00"
    assert row["instructor"] == "دکتر جدید"
    assert row["classroom_location"] == "کلاس ۱"
    assert row["instructor_coordinated"] is True


@pytest.mark.asyncio
async def test_build_prep_status_after_rollback_from_published(
    db_session: AsyncSession, sample_user
):
    """پس از rollback از published، status باید فرایند را فعال با current_state قبلی برگرداند."""
    from app.services.semester_prep_service import build_prep_status

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    engine = StateMachineEngine(db_session)
    triggers = [
        "calendar_submitted",
        "tuition_submitted",
        "license_reviewed",
        "course_list_submitted",
        "courses_finalized",
        "marketing_started",
        "interviewers_assigned",
        "interview_times_set",
    ]
    for trigger in triggers:
        result = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event=trigger,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        assert result.success is True, f"transition {trigger} failed: {result.error}"
        await db_session.commit()

    inst = await engine.get_process_instance(inst.id)
    assert inst.current_state_code == "published"
    assert inst.is_completed is True

    status_before = await build_prep_status(db_session)
    entry_before = status_before["processes"][FALL_PREP]
    assert entry_before["active"] is False
    assert entry_before.get("completed_current_state") == "published"

    rollback = await engine.rollback_to_previous_state(
        instance_id=inst.id,
        actor_id=sample_user.id,
        actor_role="admin",
        reason="تست بازگشت برای ویرایش",
    )
    assert rollback.success is True
    assert rollback.to_state == "interview_scheduling"
    await db_session.commit()

    inst = await engine.get_process_instance(inst.id)
    assert inst.current_state_code == "interview_scheduling"
    assert inst.is_completed is False

    status_after = await build_prep_status(db_session)
    entry_after = status_after["processes"][FALL_PREP]
    assert entry_after["active"] is True
    assert entry_after["current_state"] == "interview_scheduling"
    assert entry_after.get("completed_current_state") is None
    assert str(entry_after["instance_id"]) == str(inst.id)

    rollback2 = await engine.rollback_to_previous_state(
        instance_id=inst.id,
        actor_id=sample_user.id,
        actor_role="admin",
        reason="تست بازگشت زنجیره‌ای",
    )
    assert rollback2.success is True
    assert rollback2.to_state == "interviewer_assignment"
    await db_session.commit()

    inst = await engine.get_process_instance(inst.id)
    assert inst.current_state_code == "interviewer_assignment"

    status_after2 = await build_prep_status(db_session)
    assert status_after2["processes"][FALL_PREP]["current_state"] == "interviewer_assignment"


@pytest.mark.asyncio
async def test_build_marketing_handoff_diagnostic(db_session: AsyncSession, sample_user):
    from app.meta.student_step_forms import apply_register_to_context
    from app.services.semester_prep_service import (
        build_marketing_handoff_diagnostic,
        get_or_start_prep_instance,
    )
    from sqlalchemy.orm.attributes import flag_modified

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    calendar_values = {
        "fall_start_date": "2026-09-23",
        "fall_end_date": "2026-12-21",
        "winter_start_date": "2026-12-22",
        "winter_end_date": "2027-03-20",
        "registration_payment_window_start": "2026-08-01",
        "registration_payment_window_end": "2026-09-01",
        "intern_interview_deadline_start": "2026-08-10",
        "intern_interview_deadline_end": "2026-08-15",
        "teaching_assistant_interview_deadline_start": "2026-08-15",
        "teaching_assistant_interview_deadline_end": "2026-08-20",
        "nowruz_holiday_start": "2027-03-21",
        "nowruz_holiday_end": "2027-04-02",
    }
    inst.context_data = apply_register_to_context(
        dict(inst.context_data or {}), "calendar_entry", calendar_values
    )
    flag_modified(inst, "context_data")
    await db_session.commit()

    diag = await build_marketing_handoff_diagnostic(db_session, process_code=FALL_PREP)
    entry = diag["processes"][FALL_PREP]
    assert entry["active"] is True
    assert entry["submitted_states"]["calendar_entry"] is True
    assert entry["marketing_keys_present"]["fall_start_date"] is True
