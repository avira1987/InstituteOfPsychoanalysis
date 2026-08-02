"""Unit tests for interview Alocom provisioning helpers."""

from __future__ import annotations

import types
import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.alocom_client import AlocomAPIError
from app.services.alocom_interview_provision import (
    build_interview_alocom_title,
    build_interview_event_slug,
    provision_interview_slot_alocom,
)


def test_build_interview_event_slug_contains_slot_hint() -> None:
    sid = uuid.uuid4()
    out = build_interview_event_slug("ST-1029", sid)
    assert out.startswith("st-1029-iv-")
    assert sid.hex[:10] in out


def test_build_interview_alocom_title_is_unique_per_slot() -> None:
    sid = uuid.uuid4()
    sid2 = uuid.uuid4()
    t1 = build_interview_alocom_title("ST-1029", sid)
    t2 = build_interview_alocom_title("ST-1029", sid2)
    assert t1 != t2
    assert sid.hex[:8] in t1


@pytest.mark.asyncio
async def test_provision_interview_slot_raises_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = types.SimpleNamespace(ALOCOM_ENABLED=False)
    monkeypatch.setattr("app.services.alocom_interview_provision.get_settings", lambda: settings)
    slot = types.SimpleNamespace(mode="online", assigned_student_id=uuid.uuid4())
    with pytest.raises(AlocomAPIError):
        await provision_interview_slot_alocom(
            db=None,  # type: ignore[arg-type]
            slot=slot,  # type: ignore[arg-type]
            agent_service_id=1,
            title="Interview",
        )


@pytest.mark.asyncio
async def test_provision_creates_event_without_users_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = types.SimpleNamespace(ALOCOM_ENABLED=True)
    monkeypatch.setattr("app.services.alocom_interview_provision.get_settings", lambda: settings)

    slot_id = uuid.uuid4()
    student_id = uuid.uuid4()
    user_id = uuid.uuid4()
    slot = types.SimpleNamespace(
        id=slot_id,
        mode="online",
        assigned_student_id=student_id,
        interviewer_user_id=None,
        meeting_link=None,
        host_meeting_link=None,
        interviewer_meeting_link=None,
        alocom_event_id=None,
    )
    student = types.SimpleNamespace(id=student_id, student_code="ST-1", user_id=user_id)
    student_user = types.SimpleNamespace(id=user_id, full_name_fa="Ali Test", username="ali", phone=None, email=None)

    class FakeResult:
        def __init__(self, value):
            self._value = value

        def scalars(self):
            return self

        def first(self):
            return self._value

    async def fake_execute(stmt):
        sql = str(stmt)
        if "students" in sql.lower():
            return FakeResult(student)
        if "users" in sql.lower():
            return FakeResult(student_user)
        return FakeResult(None)

    db = types.SimpleNamespace(execute=fake_execute, flush=AsyncMock())

    client = AsyncMock()
    client.create_event = AsyncMock(
        return_value={"data": {"event": {"id": "99", "alocom_link": "https://class.test/host?token=hosttok"}}}
    )
    client.register_user_in_event = AsyncMock(
        return_value={"eventLink": "https://class.test/student?token=studenttok"}
    )
    monkeypatch.setattr(
        "app.services.alocom_interview_provision.AlocomClient",
        lambda _settings: client,
    )

    out = await provision_interview_slot_alocom(
        db=db,  # type: ignore[arg-type]
        slot=slot,  # type: ignore[arg-type]
        agent_service_id=138048,
        title="مصاحبه",
    )

    assert out["meeting_link"] == "https://class.test/student?token=studenttok"
    assert slot.meeting_link == "https://class.test/student?token=studenttok"
    assert slot.alocom_event_id == "99"
    client.create_event.assert_awaited_once()
    kwargs = client.create_event.await_args.kwargs
    assert kwargs.get("users") is None


@pytest.mark.asyncio
async def test_build_links_persists_staff_when_student_enroll_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.alocom_interview_provision import _build_links_for_event

    settings = types.SimpleNamespace(ALOCOM_ENABLED=True)
    monkeypatch.setattr("app.services.alocom_interview_provision.get_settings", lambda: settings)

    student_user = types.SimpleNamespace(
        id=uuid.uuid4(), full_name_fa="Student", username="stu", phone="09120000000"
    )
    interviewer_user = types.SimpleNamespace(
        id=uuid.uuid4(), full_name_fa="Teacher", username="tch", phone="09121111111"
    )
    client = AsyncMock()

    async def fake_register(event_id, **kwargs):
        role = kwargs.get("role")
        if role == "teacher":
            return {"eventLink": "https://class.test/host?token=teachertok"}
        return None

    client.register_user_in_event = AsyncMock(side_effect=fake_register)

    meeting_link, host_link, iv_link = await _build_links_for_event(
        client,
        event_id="77",
        default_link="https://class.test/default?token=defaulttok",
        student_user=student_user,
        interviewer_user=interviewer_user,
        fetch_student_event_link=True,
    )

    assert meeting_link == ""
    assert host_link == "https://class.test/host?token=teachertok"
    assert iv_link == "https://class.test/host?token=teachertok"


@pytest.mark.asyncio
async def test_maybe_provision_clears_bare_link_and_reprovisions(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.interview_slot_service import maybe_provision_interview_slot_alocom_link

    slot = types.SimpleNamespace(
        id=uuid.uuid4(),
        mode="online",
        meeting_link="https://class.test/bare-without-token",
        assigned_student_id=uuid.uuid4(),
        assigned_instance_id=uuid.uuid4(),
        booking_payment_deadline_at=None,
        interviewer_user_id=None,
        alocom_event_id="stale-event",
    )

    refresh = AsyncMock(return_value=False)
    provision = AsyncMock(
        side_effect=lambda *_a, **_kw: setattr(
            slot, "meeting_link", "https://class.test/student?token=new"
        )
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=types.SimpleNamespace(student_code="ST-1"))
    db.flush = AsyncMock()

    monkeypatch.setattr(
        "app.services.interview_slot_service.refresh_interview_slot_alocom_links",
        refresh,
    )
    monkeypatch.setattr(
        "app.services.interview_slot_service.is_alocom_configured",
        lambda: (True, 42),
    )
    monkeypatch.setattr(
        "app.services.interview_slot_service.provision_interview_slot_alocom",
        provision,
    )
    monkeypatch.setattr(
        "app.services.interview_slot_service.ensure_interview_slot_host_meeting_link",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.interview_slot_service.sync_registration_interview_context_from_slot",
        AsyncMock(),
    )

    ok = await maybe_provision_interview_slot_alocom_link(db, slot, payment_confirmed=True)

    assert ok is True
    assert slot.alocom_event_id is None
    assert slot.meeting_link == "https://class.test/student?token=new"
    provision.assert_awaited_once()
