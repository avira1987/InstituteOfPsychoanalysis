"""Integration tests for Payment and SMS APIs."""

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """TestClient اجرای lifespan را انجام می‌دهد (init_db، admin، …)."""
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    """Health check."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_login(client: TestClient):
    """Login returns token."""
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    data = r.json()
    assert "access_token" in data


def test_payment_create(client: TestClient):
    """Payment create returns payment_url (mock) or gateway error (real provider)."""
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.text}")
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/payment/create",
        headers=headers,
        json={"amount": 1000, "description": "تست"},
    )
    assert r.status_code in (200, 400), f"Unexpected status: {r.status_code} {r.text}"
    if r.status_code == 200:
        data = r.json()
        assert data.get("success") is True
        assert "payment_url" in data
        assert "authority" in data


def test_sms_endpoint(client: TestClient):
    """Test SMS endpoint returns success or provider info."""
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.text}")
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/admin/test-sms",
        headers=headers,
        json={"phone": "09123456789", "message": "تست API انستیتو"},
    )
    assert r.status_code == 200, f"SMS test failed: {r.text}"
    data = r.json()
    assert "success" in data
    assert "provider" in data
    if data.get("provider") == "log":
        assert data.get("simulated_sms") or (data.get("simulated_sms_list") or []), (
            "در حالت log باید simulated_sms در پاسخ test-sms باشد"
        )
