"""Integration tests for Payment and SMS APIs."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    """Health check."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"


@pytest.mark.asyncio
async def test_login():
    """Login returns token."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        data = r.json()
        assert "access_token" in data
        return data["access_token"]


@pytest.mark.asyncio
async def test_payment_create():
    """Payment create returns payment_url (mock) or gateway error (real provider)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
        if r.status_code != 200:
            pytest.skip(f"Login failed: {r.text}")
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = await client.post(
            "/api/payment/create",
            headers=headers,
            json={"amount": 1000, "description": "تست"},
        )
        # With mock provider → 200; with real provider (saman/zibal) → may fail if gateway unreachable
        assert r.status_code in (200, 400), f"Unexpected status: {r.status_code} {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert data.get("success") is True
            assert "payment_url" in data
            assert "authority" in data


@pytest.mark.asyncio
async def test_sms_endpoint():
    """Test SMS endpoint returns success or provider info."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
        if r.status_code != 200:
            pytest.skip(f"Login failed: {r.text}")
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = await client.post(
            "/api/admin/test-sms",
            headers=headers,
            json={"phone": "09123456789", "message": "تست API انستیتو"},
        )
        assert r.status_code == 200, f"SMS test failed: {r.text}"
        data = r.json()
        assert "success" in data
        assert "provider" in data
