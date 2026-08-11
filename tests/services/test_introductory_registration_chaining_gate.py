"""زنجیرهٔ ثبت‌نام آشنایی — defer گیت و student_next_action_fa."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.operational_models import ProcessInstance
from app.services.introductory_registration_chaining import chain_introductory_registration_after_transition


@pytest.mark.asyncio
async def test_chain_deferred_gate_sets_student_next_action_fa():
    instance = MagicMock(spec=ProcessInstance)
    instance.id = uuid.uuid4()
    instance.process_code = "introductory_course_registration"
    instance.context_data = {}

    engine = MagicMock()
    db = MagicMock()

    with patch(
        "app.services.registration_readiness_service.check_intro_registration_gate",
        new_callable=AsyncMock,
    ) as mock_gate, patch(
        "app.services.introductory_registration_chaining.flag_modified",
    ):
        mock_gate.return_value = MagicMock(allowed=False)
        await chain_introductory_registration_after_transition(
            db,
            engine,
            instance,
            "result_full_admission",
            uuid.uuid4(),
        )

    assert instance.context_data.get("student_next_action_fa")
    assert "آپلود مدارک" in instance.context_data["student_next_action_fa"]
    engine.execute_transition.assert_not_called()
