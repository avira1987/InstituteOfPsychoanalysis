"""قفل پورتال قسط معوق و فیلدهای join بدون URL خام."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.installment_access import (
    INSTALLMENT_LOCK_DETAIL,
    course_join_path,
    raise_if_student_installment_locked,
    student_course_join_fields,
    student_installment_lock_active,
)


def test_lock_inactive_without_flag():
    assert student_installment_lock_active(None) is False
    assert student_installment_lock_active(SimpleNamespace(extra_data=None)) is False
    assert student_installment_lock_active(SimpleNamespace(extra_data={})) is False


def test_lock_active_from_extra_data():
    st = SimpleNamespace(extra_data={"installment_portal_lock": {"active": True}})
    assert student_installment_lock_active(st) is True
    with pytest.raises(HTTPException) as exc:
        raise_if_student_installment_locked(st)
    assert exc.value.status_code == 403
    assert exc.value.detail == INSTALLMENT_LOCK_DETAIL


def test_lock_inactive_when_flag_off():
    st = SimpleNamespace(extra_data={"installment_portal_lock": {"active": False}})
    assert student_installment_lock_active(st) is False
    raise_if_student_installment_locked(st)


def test_course_join_fields_never_expose_raw_url():
    fields = student_course_join_fields(course_code="THEORY101", has_external_url=True)
    assert fields["meeting_link"] is None
    assert fields["join_path"] == course_join_path("THEORY101")
    assert fields["meeting_link_ready"] is True
    assert fields["meeting_link_is_visible"] is True

    empty = student_course_join_fields(course_code="THEORY101", has_external_url=False)
    assert empty["meeting_link"] is None
    assert empty["join_path"] is None
    assert empty["meeting_link_ready"] is False
