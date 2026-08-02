"""Flow-through API test fixtures."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.demo_role_users import ensure_demo_role_users
from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def _enriched_matrix_path() -> Path:
    track = (os.getenv("FLOW_THROUGH_TRACK") or "").strip().lower()
    if track == "onboarding":
        return ROOT / "reports" / "flow_through" / "onboarding" / "matrix_enriched.json"
    return ROOT / "reports" / "flow_through" / "matrix_enriched.json"


ENRICHED_MATRIX = _enriched_matrix_path()


def _load_matrix_rows() -> list[dict[str, Any]]:
    path = _enriched_matrix_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows") or []
    only = os.getenv("FLOW_THROUGH_PROCESS")
    if only:
        rows = [r for r in rows if r.get("process_code") == only]
    proof = os.getenv("FLOW_THROUGH_PROOF")
    if proof:
        rows = [r for r in rows if r.get("process_code") == proof]
    return rows

MATRIX_ROWS = _load_matrix_rows()


def matrix_ids(row: dict[str, Any]) -> str:
    return row.get("step_id") or f"{row.get('process_code')}/{row.get('state_code')}"


@pytest.fixture
def flow_matrix_rows() -> list[dict[str, Any]]:
    return MATRIX_ROWS


@pytest_asyncio.fixture
async def flow_api_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    await ensure_demo_role_users(db_session)
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture(autouse=True)
async def _ensure_demo_users(db_session: AsyncSession):
    await ensure_demo_role_users(db_session)
    await db_session.commit()
