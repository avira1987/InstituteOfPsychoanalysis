"""
تست سطح A (اسموک) برای همهٔ فرایندهای metadata/processes/*.json

برای هر فایل: لود قوانین + sync فرایند از JSON + start_process + تطابق state اول با initial_state.
هدف: پوشش یکسان برای ~۶۷ فرایند بدون تکرار دستی تست‌های تک‌فایل.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules


def _process_json_paths():
    root = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    return sorted(root.glob("*.json"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "process_file",
    _process_json_paths(),
    ids=lambda p: p.stem,
)
async def test_process_level_a_load_sync_start_matches_initial_state(
    db_session: AsyncSession,
    sample_student,
    sample_user,
    process_file: Path,
):
    """هر فرایند باید در DB قابل sync، قابل start و state اول مطابق متادیتا باشد."""
    with open(process_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    proc = data.get("process") or {}
    code = proc.get("code")
    initial = proc.get("initial_state")
    assert code, f"{process_file.name}: missing process.code"
    assert initial, f"{process_file.name}: missing process.initial_state"

    await load_rules(db_session)
    await load_process(db_session, process_file)
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code=code,
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()

    assert instance.process_code == code
    assert instance.current_state_code == initial
    assert instance.is_completed is False
    assert instance.is_cancelled is False


# با اضافه کردن فرایند جدید به metadata/processes این عدد را به‌روز کنید.
EXPECTED_PROCESS_JSON_COUNT = 67


def test_metadata_process_count_matches_level_a_parametrize():
    """تعداد فایل‌های JSON با تعداد پارامترهای تست یکی باشد (گارد در برابر حذف/اضافه بدون به‌روزرسانی تست)."""
    paths = _process_json_paths()
    assert len(paths) == EXPECTED_PROCESS_JSON_COUNT, (
        f"expected {EXPECTED_PROCESS_JSON_COUNT} process JSON files, got {len(paths)} — "
        "update EXPECTED_PROCESS_JSON_COUNT when adding/removing metadata/processes/*.json"
    )
