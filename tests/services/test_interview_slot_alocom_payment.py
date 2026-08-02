"""مصاحبهٔ آنلاین: ساخت لینک الوکام پس از پرداخت موفق."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.interview_slot_service import (
    interview_meeting_link_provision_status,
    maybe_provision_interview_slot_alocom_link,
)


def _online_slot(*, deadline_set: bool) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        mode="online",
        meeting_link=None,
        assigned_student_id=uuid.uuid4(),
        assigned_instance_id=uuid.uuid4(),
        booking_payment_deadline_at=(
            datetime.now(timezone.utc) + timedelta(minutes=15) if deadline_set else None
        ),
        interviewer_user_id=None,
        alocom_event_id=None,
    )


@pytest.mark.asyncio
async def test_maybe_provision_skips_while_payment_deadline_active() -> None:
    slot = _online_slot(deadline_set=True)
    ok = await maybe_provision_interview_slot_alocom_link(None, slot)  # type: ignore[arg-type]
    assert ok is False


@pytest.mark.asyncio
async def test_maybe_provision_after_payment_confirmed_ignores_deadline() -> None:
    slot = _online_slot(deadline_set=True)
    async def _provision(*_a, **_kw):
        slot.meeting_link = "https://alocom.test/room?token=student"
        return {"meeting_link": "https://alocom.test/room?token=student"}

    provision = AsyncMock(side_effect=_provision)
    db = AsyncMock()
    db.get = AsyncMock(return_value=SimpleNamespace(student_code="ST-1"))
    with (
        patch(
            "app.services.interview_slot_service.is_alocom_configured",
            return_value=(True, 42),
        ),
        patch(
            "app.services.interview_slot_service.provision_interview_slot_alocom",
            provision,
        ),
        patch(
            "app.services.interview_slot_service.ensure_interview_slot_host_meeting_link",
            new_callable=AsyncMock,
        ),
        patch(
            "app.services.interview_slot_service.sync_registration_interview_context_from_slot",
            new_callable=AsyncMock,
        ),
    ):
        ok = await maybe_provision_interview_slot_alocom_link(
            db, slot, payment_confirmed=True
        )
    assert ok is True
    provision.assert_awaited_once()


def test_provision_status_alocom_not_configured() -> None:
    slot = _online_slot(deadline_set=False)
    with patch(
        "app.services.interview_slot_service.is_alocom_configured",
        return_value=(False, 0),
    ):
        assert interview_meeting_link_provision_status(slot) == "alocom_not_configured"


def test_provision_status_ok_when_token_link_present() -> None:
    slot = _online_slot(deadline_set=False)
    slot.meeting_link = "https://alocom.test/room?token=abc"
    assert interview_meeting_link_provision_status(slot) is None
