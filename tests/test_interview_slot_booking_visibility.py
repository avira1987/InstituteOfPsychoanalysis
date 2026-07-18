"""قوانین نمایش رزرو مصاحبه برای نقش interviewer (pool vs اختصاصی)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Optional

from datetime import datetime, timezone

from app.api.interview_slots_routes import (
    SLOT_DEFINE_ROLES,
    _can_define_interview_slots,
    _interviewer_can_view_booking,
    _interviewer_owns_slot,
    _is_meeting_link_visible_for_user,
    _meeting_link_for_viewer,
)


def _user(uid: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=uid)


def _slot(*, created_by: uuid.UUID, interviewer_user_id: Optional[uuid.UUID]) -> SimpleNamespace:
    return SimpleNamespace(
        created_by=created_by,
        interviewer_user_id=interviewer_user_id,
        assigned_student_id=uuid.uuid4(),
        booking_payment_deadline_at=None,
        mode="online",
        meeting_link="https://meeting.example.com/room/1",
        starts_at=datetime(2026, 5, 7, 15, 0, tzinfo=timezone.utc),
    )


def test_staff_admin_and_site_manager_can_define_interview_slots() -> None:
    staff = SimpleNamespace(id=uuid.uuid4(), role="staff")
    interviewer = SimpleNamespace(id=uuid.uuid4(), role="interviewer")
    admin = SimpleNamespace(id=uuid.uuid4(), role="admin")
    site_manager = SimpleNamespace(id=uuid.uuid4(), role="site_manager")
    assert _can_define_interview_slots(staff) is True
    assert _can_define_interview_slots(admin) is True
    assert _can_define_interview_slots(site_manager) is True
    assert _can_define_interview_slots(interviewer) is False
    assert SLOT_DEFINE_ROLES == ("staff", "admin", "site_manager")


def test_interviewer_does_not_own_staff_pool_slot_but_can_view_booking() -> None:
    interviewer_id = uuid.uuid4()
    staff_id = uuid.uuid4()
    u = _user(interviewer_id)
    s = _slot(created_by=staff_id, interviewer_user_id=None)
    assert _interviewer_owns_slot(u, s) is False
    assert _interviewer_can_view_booking(u, s) is True


def test_interviewer_owns_self_created_pool_slot() -> None:
    uid = uuid.uuid4()
    u = _user(uid)
    s = _slot(created_by=uid, interviewer_user_id=None)
    assert _interviewer_owns_slot(u, s) is True
    assert _interviewer_can_view_booking(u, s) is True


def test_interviewer_sees_slot_assigned_to_self_even_if_created_by_other() -> None:
    interviewer_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    u = _user(interviewer_id)
    s = _slot(created_by=admin_id, interviewer_user_id=interviewer_id)
    assert _interviewer_owns_slot(u, s) is True
    assert _interviewer_can_view_booking(u, s) is True


def test_interviewer_cannot_view_booking_for_slot_assigned_to_colleague() -> None:
    self_id = uuid.uuid4()
    colleague_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    u = _user(self_id)
    s = _slot(created_by=admin_id, interviewer_user_id=colleague_id)
    assert _interviewer_can_view_booking(u, s) is False


def test_online_link_hidden_for_student_before_window() -> None:
    slot = _slot(created_by=uuid.uuid4(), interviewer_user_id=None)
    slot.assigned_student_id = None
    student = SimpleNamespace(id=uuid.uuid4(), role="student")
    now = datetime(2026, 5, 7, 14, 20, tzinfo=timezone.utc)
    assert _is_meeting_link_visible_for_user(slot, student, now) is False


def test_online_link_visible_for_student_inside_window() -> None:
    slot = _slot(created_by=uuid.uuid4(), interviewer_user_id=None)
    student = SimpleNamespace(id=uuid.uuid4(), role="student")
    now = datetime(2026, 5, 7, 14, 31, tzinfo=timezone.utc)
    assert _is_meeting_link_visible_for_user(slot, student, now) is True


def test_paid_student_cannot_see_link_before_interview_window() -> None:
    slot = _slot(created_by=uuid.uuid4(), interviewer_user_id=None)
    slot.booking_payment_deadline_at = None
    student = SimpleNamespace(id=uuid.uuid4(), role="student")
    now = datetime(2026, 5, 7, 14, 20, tzinfo=timezone.utc)
    assert _is_meeting_link_visible_for_user(slot, student, now) is False


def test_student_join_open_allows_link_before_interview_window() -> None:
    slot = _slot(created_by=uuid.uuid4(), interviewer_user_id=None)
    slot.booking_payment_deadline_at = None
    slot.student_join_open = True
    student = SimpleNamespace(id=uuid.uuid4(), role="student")
    now = datetime(2026, 5, 7, 14, 20, tzinfo=timezone.utc)
    assert _is_meeting_link_visible_for_user(slot, student, now) is True


def test_admin_gets_host_link_not_student_participant_link() -> None:
    slot = SimpleNamespace(
        mode="online",
        meeting_link="https://alocom.test/student-token",
        host_meeting_link="https://alocom.test/host-room",
        interviewer_meeting_link="https://alocom.test/teacher-token",
        interviewer_user_id=uuid.uuid4(),
    )
    admin = SimpleNamespace(id=uuid.uuid4(), role="admin")
    assert _meeting_link_for_viewer(slot, admin) == "https://alocom.test/host-room"


def test_interviewer_gets_teacher_link() -> None:
    iv_id = uuid.uuid4()
    slot = SimpleNamespace(
        mode="online",
        meeting_link="https://alocom.test/student-token",
        host_meeting_link="https://alocom.test/host-room",
        interviewer_meeting_link="https://alocom.test/teacher-token",
        interviewer_user_id=iv_id,
    )
    interviewer = SimpleNamespace(id=iv_id, role="interviewer")
    assert _meeting_link_for_viewer(slot, interviewer) == "https://alocom.test/teacher-token"


def test_legacy_slot_admin_prefers_interviewer_link_over_student() -> None:
    slot = SimpleNamespace(
        mode="online",
        meeting_link="https://alocom.test/student-token",
        host_meeting_link=None,
        interviewer_meeting_link="https://alocom.test/teacher-token",
        interviewer_user_id=uuid.uuid4(),
    )
    admin = SimpleNamespace(id=uuid.uuid4(), role="admin")
    assert _meeting_link_for_viewer(slot, admin) == "https://alocom.test/teacher-token"
