"""تست واحد و سبک API برای هشدارهای آمادگی اپراتور (operator_readiness)."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models.operational_models import TherapySession
from app.services.operator_readiness import _session_is_future_scheduled


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _ts(
    *,
    session_date: date,
    status: str = "scheduled",
    session_starts_at: datetime | None = None,
) -> TherapySession:
    return TherapySession(
        id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        therapist_id=uuid.uuid4(),
        session_date=session_date,
        status=status,
        session_starts_at=session_starts_at,
    )


def test_session_future_scheduled_uses_starts_at():
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
    today = now.date()
    fut = now + timedelta(hours=2)
    ts = _ts(session_date=today, session_starts_at=fut)
    assert _session_is_future_scheduled(ts, now, today) is True


def test_session_past_starts_at_not_future():
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
    today = now.date()
    past = now - timedelta(hours=1)
    ts = _ts(session_date=today, session_starts_at=past)
    assert _session_is_future_scheduled(ts, now, today) is False


def test_session_without_starts_at_uses_session_date():
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
    today = now.date()
    ts_ok = _ts(session_date=today)
    assert _session_is_future_scheduled(ts_ok, now, today) is True
    ts_old = _ts(session_date=today - timedelta(days=1))
    assert _session_is_future_scheduled(ts_old, now, today) is False


def test_non_scheduled_status_false():
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
    today = now.date()
    ts = _ts(session_date=today, status="completed")
    assert _session_is_future_scheduled(ts, now, today) is False


@pytest.mark.asyncio
async def test_interviewer_readiness_counts_office_pool_free_slots() -> None:
    """اسلات عمومی دفتر (بدون interviewer_user_id) هم ظرفیت رزرو را برای مصاحبه‌گر می‌شمارد."""
    from unittest.mock import AsyncMock, MagicMock

    from app.models.operational_models import User
    from app.services.operator_readiness import _check_interviewer_free_slots

    uid = uuid.uuid4()
    db = MagicMock()
    result = MagicMock()
    result.scalar.return_value = 1
    db.execute = AsyncMock(return_value=result)

    alerts = await _check_interviewer_free_slots(
        db,
        uid,
        1,
        {"title_fa": "زمان آزاد مصاحبه تعریف نشده"},
        "interviewer_future_free_slots",
    )
    assert alerts == []


@pytest.mark.asyncio
async def test_interviewer_readiness_alert_when_no_free_slots() -> None:
    from unittest.mock import AsyncMock, MagicMock

    from app.services.operator_readiness import _check_interviewer_free_slots

    uid = uuid.uuid4()
    db = MagicMock()
    result = MagicMock()
    result.scalar.return_value = 0
    db.execute = AsyncMock(return_value=result)

    alerts = await _check_interviewer_free_slots(
        db,
        uid,
        1,
        {"title_fa": "زمان آزاد مصاحبه تعریف نشده", "detail_fa": "جزئیات"},
        "interviewer_future_free_slots",
    )
    assert len(alerts) == 1
    assert alerts[0]["title_fa"] == "زمان آزاد مصاحبه تعریف نشده"


@pytest.mark.asyncio
async def test_compute_readiness_empty_for_student():
    from unittest.mock import MagicMock

    from app.models.operational_models import User
    from app.services.operator_readiness import compute_operator_readiness_alerts

    u = MagicMock(spec=User)
    u.role = "student"
    u.id = uuid.uuid4()
    db = MagicMock()
    out = await compute_operator_readiness_alerts(db, u)
    assert out == []


def test_my_operator_followup_requires_auth(client: TestClient):
    r = client.get("/api/panel/my-operator-followup")
    assert r.status_code == 401


def test_my_operator_followup_admin_returns_shape(client: TestClient):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.text}")
    token = r.json()["access_token"]
    r2 = client.get(
        "/api/panel/my-operator-followup",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert "items" in data
    assert "summary" in data
    assert "readiness_alerts" in data
    assert isinstance(data["readiness_alerts"], list)
    assert data["summary"].get("readiness_count") == len(data["readiness_alerts"])
