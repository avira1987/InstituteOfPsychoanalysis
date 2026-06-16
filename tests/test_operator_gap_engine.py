"""موتور کمبود — تست سبک."""

import pytest

from types import SimpleNamespace

from app.models.operational_models import Student, User
from app.services.operator_gap_engine import compute_operator_gaps, _student_matches_filter


def test_student_matches_filter():
    st = SimpleNamespace(course_type="introductory")
    assert _student_matches_filter(st, {"course_type": "introductory"})
    assert not _student_matches_filter(st, {"course_type": "comprehensive"})


@pytest.mark.asyncio
async def test_compute_gaps_empty_when_rules_disabled(db_session):
    """قواعد پیش‌فرض در JSON غیرفعال‌اند — خروجی خالی."""
    from app.api.auth import get_password_hash

    u = User(
        username="gap_test_user",
        email="gap@test.com",
        hashed_password=get_password_hash("x"),
        role="student",
    )
    db_session.add(u)
    await db_session.flush()
    st = Student(
        user_id=u.id,
        student_code="GAP-TEST-001",
        course_type="introductory",
        term_count=1,
        current_term=1,
        weekly_sessions=1,
    )
    db_session.add(st)
    await db_session.commit()

    gaps = await compute_operator_gaps(db_session, limit=50, student_id=st.id)
    assert gaps == []
