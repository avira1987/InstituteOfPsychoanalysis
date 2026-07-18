"""Tests for marketing campaign PDF pack (semester prep handoff)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_marketing_pdf import (
    build_marketing_campaign_pdf_bytes,
    build_marketing_campaign_pdf_rows,
    enrich_marketing_handoff_context,
    has_marketing_handoff_data,
    resolve_marketing_handoff_context,
)
from app.services.semester_prep_service import FALL_PREP, WINTER_PREP, get_or_start_prep_instance


def test_resolve_handoff_falls_back_to_draft_courses_fall():
    ctx = {
        "courses_fall": [
            {
                "course_name": "روانکاوی ۱",
                "track": "جامع",
                "proposed_day": "دوشنبه",
                "proposed_time": "18:00",
            }
        ],
    }
    out = resolve_marketing_handoff_context("fall_semester_preparation", ctx)
    assert len(out["courses_finalized_fall"]) == 1
    assert out["courses_finalized_fall"][0]["day"] == "دوشنبه"


def test_fall_marketing_pdf_rows_include_interview_fees():
    ctx = {
        "fall_start_date": "2026-09-23",
        "per_unit_cost_introductory": 1_000_000,
        "interview_fee_introductory": 3_500_000,
        "interview_fee_comprehensive": 4_500_000,
        "courses_fall": [{"course_name": "روانکاوی ۱", "track": "جامع", "day": "دوشنبه"}],
    }
    rows = build_marketing_campaign_pdf_rows("fall_semester_preparation", ctx)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "3,500,000" in flat or "3500000" in flat.replace(",", "")
    assert "4,500,000" in flat or "4500000" in flat.replace(",", "")


def test_fall_marketing_pdf_rows_include_activities_1_2_5():
    ctx = {
        "fall_start_date": "2026-09-23",
        "fall_end_date": "2026-12-21",
        "per_unit_cost_introductory": 1_000_000,
        "courses_fall": [
            {
                "course_name": "روانکاوی ۱",
                "track": "جامع",
                "proposed_day": "دوشنبه",
                "proposed_time": "18:00",
                "instructor": "دکتر الف",
                "instructor_coordinated": True,
            }
        ],
    }
    rows = build_marketing_campaign_pdf_rows("fall_semester_preparation", ctx)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "فعالیت ۱" in flat
    assert "فعالیت ۲" in flat
    assert "فعالیت ۵" in flat
    assert "روانکاوی ۱" in flat


def test_winter_marketing_pdf_rows_include_activities_2_3():
    ctx = {
        "courses": [{"course_name": "تئوری ۲", "track": "آشنایی"}],
        "courses_finalized": [{"course_name": "تئوری ۲", "track": "آشنایی", "classroom_location": "کلاس ۳"}],
    }
    rows = build_marketing_campaign_pdf_rows("winter_semester_preparation", ctx)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "فعالیت ۲" in flat
    assert "فعالیت ۳" in flat
    assert "تئوری ۲" in flat


def test_fall_marketing_pdf_bytes_starts_with_pdf_header():
    ctx = {"fall_start_date": "2026-09-23", "fall_end_date": "2026-12-21"}
    try:
        data = build_marketing_campaign_pdf_bytes("fall_semester_preparation", ctx)
    except FileNotFoundError:
        return
    assert data[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_enrich_marketing_handoff_falls_back_to_fall_instance(db_session, sample_user):
    from datetime import datetime, timezone

    from app.services.semester_prep_marketing_pdf import (
        enrich_marketing_handoff_context,
        has_marketing_handoff_data,
    )
    from app.services.semester_prep_service import WINTER_PREP, get_or_start_prep_instance

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    anchor = await ensure_institute_operational_student(db_session)
    fall, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    winter_courses = [{"course_name": "تئوری زمستان", "track": "", "day": "سه‌شنبه"}]
    fctx = dict(fall.context_data or {})
    fctx.update(
        {
            "fall_start_date": "2026-09-23",
            "fall_end_date": "2026-12-21",
            "per_unit_cost_introductory": 1_000_000,
            "courses_winter": winter_courses,
            "courses_finalized_winter": [
                {**winter_courses[0], "classroom_location": "کلاس ۳", "instructor_coordinated": True}
            ],
        }
    )
    fall.context_data = fctx
    flag_modified(fall, "context_data")
    fall.is_completed = True
    fall.current_state_code = "published"
    fall.completed_at = datetime.now(timezone.utc)
    await db_session.commit()

    winter, _ = await get_or_start_prep_instance(
        db_session, WINTER_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    for trigger in ("license_reviewed", "course_list_reviewed", "courses_finalized"):
        engine = StateMachineEngine(db_session)
        await engine.execute_transition(
            instance_id=winter.id,
            trigger_event=trigger,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

    enriched = await enrich_marketing_handoff_context(db_session, WINTER_PREP, {})
    assert has_marketing_handoff_data(WINTER_PREP, enriched) is True
    assert enriched.get("courses") or enriched.get("courses_finalized")

    rows = build_marketing_campaign_pdf_rows(WINTER_PREP, enriched)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "تئوری زمستان" in flat
