"""
پوشش اکشن‌های متادیتا:
۱) هر نوع اکشن در transitions باید در ActionHandler._registry ثبت شده باشد.
۲) هر نوع با یک نمونهٔ فرایند و context غنی اجرا شود و handle_actions بدون success=False برگردد.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance
from app.services.action_handler import ActionHandler

from tests.processes.test_all_processes_level_a_smoke import _process_json_paths


def _metadata_action_types() -> set[str]:
    out: set[str] = set()
    root = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    for p in root.glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        for t in data.get("transitions") or []:
            for a in t.get("actions") or []:
                ty = a.get("type")
                if ty:
                    out.add(ty)
    return out


def test_all_metadata_action_types_are_registered():
    meta = _metadata_action_types()
    reg = set(ActionHandler._registry.keys())
    missing = sorted(meta - reg)
    assert not missing, f"اکشن‌های متادیتا بدون هندلر در registry: {missing}"


def _smoke_action_dict(action_type: str) -> dict:
    """حداقل فیلدهایی که هندلر برای اجرای موفق نیاز دارد (مثل start_process)."""
    if action_type == "start_process":
        return {
            "type": "start_process",
            "process_code": "violation_registration",
            "payload": {},
        }
    if action_type == "redirect_to_process":
        return {
            "type": "redirect_to_process",
            "process_code": "session_payment",
            "payload": {},
        }
    return {"type": action_type}


@pytest.fixture
async def db_with_all_process_definitions(db_session: AsyncSession):
    await load_rules(db_session)
    for path in _process_json_paths():
        await load_process(db_session, path)
    await db_session.commit()
    return db_session


@pytest.mark.asyncio
async def test_each_metadata_action_type_executes_successfully(
    db_with_all_process_definitions: AsyncSession,
    sample_student,
    sample_user,
):
    """یک بار اجرای هر نوع اکشن؛ نمونهٔ جدا برای جلوگیری از تداخل حالت."""
    handler = ActionHandler(db_with_all_process_definitions)
    action_types = sorted(_metadata_action_types())
    ctx = {
        "therapist_id": str(sample_user.id),
        "new_therapist_id": str(sample_user.id),
        "amount": 500_000.0,
        "weekly_sessions": 2,
    }
    base_ctx_data = {
        **ctx,
        "session_credit_balance": 1_000_000.0,
        "selected_sessions": [],
    }

    for action_type in action_types:
        iid = uuid.uuid4()
        inst = ProcessInstance(
            id=iid,
            process_code="therapy_session_reduction",
            student_id=sample_student.id,
            current_state_code="session_selection",
            context_data=dict(base_ctx_data),
            started_by=sample_user.id,
        )
        db_with_all_process_definitions.add(inst)
        await db_with_all_process_definitions.flush()

        results = await handler.handle_actions([_smoke_action_dict(action_type)], inst, ctx)
        assert len(results) == 1, action_type
        assert results[0]["success"] is True, (
            f"{action_type}: {results[0].get('error', results[0])}"
        )
        assert "no_handler_for_" not in str(results[0].get("detail", "")), action_type

        await db_with_all_process_definitions.commit()
