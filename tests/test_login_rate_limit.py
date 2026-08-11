"""تست محدودیت نرخ ورود — ورود موفق سهمیه را مصرف نمی‌کند."""

import re

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.middleware.login_rate_limit import reset_login_rate_limits


@pytest.fixture
def client():
    reset_login_rate_limits()
    with TestClient(app) as c:
        yield c
    reset_login_rate_limits()


def test_successful_login_does_not_consume_rate_limit_budget(client: TestClient):
    """ورود موفق نباید پس از چند بار تکرار، قفل ۴۲۹ بدهد."""
    for _ in range(12):
        ch = client.post("/api/auth/login-challenge")
        assert ch.status_code == 200
        data = ch.json()
        m = re.search(r"حاصل\s*(\d+)\s*\+\s*(\d+)", data["question"])
        assert m
        answer = str(int(m.group(1)) + int(m.group(2)))
        login = client.post(
            "/api/auth/login-json",
            json={
                "username": "admin",
                "password": "admin123",
                "challenge_id": data["challenge_id"],
                "challenge_answer": answer,
            },
        )
        assert login.status_code == 200, login.text
