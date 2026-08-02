"""بستن لینک ورود به جلسهٔ مصاحبه پس از ثبت نتیجه."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.interview_slots_routes import _slot_to_dict
from app.services.interview_slot_service import (
    INTERVIEW_LINK_ACTIVE_STATES,
    interview_result_recorded_for_instance,
    interview_slot_result_recorded,
)

_NOW = datetime(2026, 5, 7, 15, 10, tzinfo=timezone.utc)


def _slot() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        interviewer_user_id=None,
        assigned_student_id=uuid.uuid4(),
        assigned_instance_id=uuid.uuid4(),
        booking_payment_deadline_at=None,
        mode="online",
        meeting_link="https://event.alocom.co/class/x?token=stu",
        host_meeting_link="https://event.alocom.co/class/x?token=host",
        interviewer_meeting_link=None,
        starts_at=datetime(2026, 5, 7, 15, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 5, 7, 16, 0, tzinfo=timezone.utc),
        course_type="introductory",
        location_fa=None,
        label_fa=None,
        student_join_open=True,
        alocom_event_id="1448405",
        reminder_sent_at=None,
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
    )


def _instance(state: str, process_code: str = "introductory_course_registration") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        process_code=process_code,
        current_state_code=state,
        context_data={},
    )


@pytest.mark.parametrize("state", sorted(INTERVIEW_LINK_ACTIVE_STATES))
def test_result_not_recorded_while_interview_states(state: str) -> None:
    assert interview_result_recorded_for_instance(_instance(state)) is False


@pytest.mark.parametrize(
    "state",
    [
        "result_full_admission",
        "result_conditional_therapy",
        "result_single_course",
        "rejected",
        "documents_upload",
        "registration_complete",
    ],
)
def test_result_recorded_after_interview_states(state: str) -> None:
    assert interview_result_recorded_for_instance(_instance(state)) is True


def test_unrelated_process_never_closes_link() -> None:
    inst = _instance("some_other_state", process_code="therapy_referral")
    assert interview_result_recorded_for_instance(inst) is False


def test_missing_instance_keeps_link_open() -> None:
    assert interview_result_recorded_for_instance(None) is False


def test_student_link_hidden_after_result_recorded() -> None:
    slot = _slot()
    student = SimpleNamespace(id=uuid.uuid4(), role="student")

    open_dict = _slot_to_dict(slot, viewer=student, now=_NOW, result_recorded=False)
    assert open_dict["meeting_link"] == slot.meeting_link
    assert open_dict["meeting_link_ready"] is True
    assert open_dict["interview_result_recorded"] is False

    closed = _slot_to_dict(slot, viewer=student, now=_NOW, result_recorded=True)
    assert closed["meeting_link"] is None
    assert closed["meeting_link_ready"] is False
    assert closed["meeting_link_is_visible"] is False
    assert closed["interview_result_recorded"] is True
    assert closed["meeting_link_locked_reason"] == "interview_result_recorded"


def test_operator_link_hidden_after_result_recorded() -> None:
    slot = _slot()
    staff = SimpleNamespace(id=uuid.uuid4(), role="staff")

    assert _slot_to_dict(slot, viewer=staff, now=_NOW)["meeting_link"] is not None

    closed = _slot_to_dict(slot, viewer=staff, now=_NOW, result_recorded=True)
    assert closed["meeting_link"] is None
    assert closed["meeting_link_ready"] is False
    assert closed["meeting_link_provision_status"] is None


@pytest.mark.asyncio
async def test_interview_slot_result_recorded_loads_instance() -> None:
    slot = _slot()
    inst = _instance("result_full_admission")

    class FakeDb:
        def __init__(self, value):
            self._value = value
            self.calls = 0

        async def get(self, _model, _pk):
            self.calls += 1
            return self._value

    db = FakeDb(inst)
    assert await interview_slot_result_recorded(db, slot) is True
    assert db.calls == 1

    slot.assigned_instance_id = None
    assert await interview_slot_result_recorded(FakeDb(inst), slot) is False
