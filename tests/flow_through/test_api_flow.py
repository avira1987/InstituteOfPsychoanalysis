"""
API flow-through tests: seed -> login as role -> forms -> submit -> trigger.

Run:
  python -m scripts.flow_through.build_matrix --wave 1
  python -m scripts.flow_through.resolve_ui_surface
  FLOW_THROUGH_PROOF=fall_semester_preparation pytest tests/flow_through -q
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import authenticate_user, create_access_token
from app.meta.seed import load_process, load_rules
from scripts.flow_through.build_sample_values import build_sample_values
from tests.flow_through.conftest import MATRIX_ROWS, matrix_ids

pytestmark = pytest.mark.asyncio


_ROLE_LOGIN_MAP = {
    "course_committee_executive": ("course_committee1", "demo123"),
    "scientific_officer_course_committee": ("course_committee1", "demo123"),
    "deputy_education_director": ("deputy_education1", "demo123"),
    "admissions_officer": ("staff1", "demo123"),
    "staff": ("staff1", "demo123"),
    "site_manager": ("site_manager1", "demo123"),
    "therapist": ("therapist1", "demo123"),
    "supervisor": ("supervisor1", "demo123"),
    "interviewer": ("interviewer1", "demo123"),
    "student": ("", "demo123"),
    "applicant": ("", "demo123"),
    "admin": ("admin", "admin123"),
}


async def _token_for_role(
    db_session: AsyncSession,
    portal_role: str,
    required_role: str,
    *,
    student_username: str | None = None,
) -> str:
    if portal_role in ("student", "applicant") and student_username:
        user = await authenticate_user(db_session, student_username, "demo123")
    else:
        key = required_role if required_role in _ROLE_LOGIN_MAP else portal_role
        username, password = _ROLE_LOGIN_MAP.get(key, (f"{portal_role}1", "demo123"))
        if username == "admin":
            password = "admin123"
        user = await authenticate_user(db_session, username, password)
    assert user is not None, f"Cannot authenticate role {portal_role}/{required_role}"
    return create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})


async def _ensure_process_loaded(db_session: AsyncSession, process_code: str) -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "metadata" / "processes" / f"{process_code}.json"
    if path.is_file():
        await load_rules(db_session)
        await load_process(db_session, path)
        await db_session.commit()


@pytest.mark.parametrize("row", MATRIX_ROWS, ids=matrix_ids)
async def test_api_flow_step(
    row: dict[str, Any],
    db_session: AsyncSession,
    flow_api_client: AsyncClient,
):
    if not MATRIX_ROWS:
        pytest.skip("Run build_matrix + resolve_ui_surface first")

    process_code = row["process_code"]
    state_code = row["state_code"]
    portal_role = row.get("portal_role") or row.get("required_role")
    required_role = row.get("required_role") or portal_role
    trigger = row["trigger"]
    to_state = row.get("to_state")

    if not row.get("ui_surface_ok", True):
        pytest.skip(f"UI surface MISSING for {row.get('step_id')}")

    from app.flow_through.state_seeder import seed_instance_at_state
    from app.models.operational_models import Student, User

    await _ensure_process_loaded(db_session, process_code)
    seed = await seed_instance_at_state(
        db_session,
        process_code,
        state_code,
        student_code=f"FLOW-API-{process_code[:10]}-{state_code[:10]}"[:50],
        institute_student=process_code in ("fall_semester_preparation", "winter_semester_preparation"),
    )
    await db_session.commit()

    assert seed.current_state == state_code, (
        f"seed failed: mode={seed.mode} blocked_at={seed.blocked_at} "
        f"got={seed.current_state} want={state_code}"
    )

    student_username = None
    if portal_role in ("student", "applicant"):
        st = (await db_session.execute(select(Student).where(Student.id == seed.student_id))).scalar_one()
        user = (await db_session.execute(select(User).where(User.id == st.user_id))).scalar_one()
        student_username = user.username

    token = await _token_for_role(
        db_session, portal_role, required_role, student_username=student_username
    )
    client = flow_api_client
    headers = {"Authorization": f"Bearer {token}"}
    iid = str(seed.instance_id)

    forms_r = await client.get(
        f"/api/process/definitions/{process_code}/forms",
        params={"state": state_code, "instance_id": iid},
        headers=headers,
    )
    assert forms_r.status_code == 200, forms_r.text
    forms_body = forms_r.json()
    forms = forms_body.get("forms") or []
    can_act = forms_body.get("can_act_on_state")

    if row.get("has_forms") and forms:
        assert can_act is not False, f"ROLE_CANNOT_ACT: {portal_role} on {state_code}"
        sample = build_sample_values(row.get("field_specs") or [])
        if portal_role in ("student", "applicant"):
            from tests.helpers.step_otp_fixture import (
                field_specs_include_step_otp,
                stamp_instance_step_otp_verified,
            )

            if field_specs_include_step_otp(row.get("field_specs")):
                await stamp_instance_step_otp_verified(
                    db_session, seed.instance_id, state_code
                )
            reg = await client.post(
                f"/api/process/{iid}/student-step-forms/register",
                json={"form_values": sample},
                headers=headers,
            )
        else:
            reg = await client.post(
                f"/api/process/{iid}/operator-step-forms/register",
                json={"form_values": sample, "state_code": state_code},
                headers=headers,
            )
        if reg.status_code != 200:
            detail = reg.text
            try:
                detail = json.dumps(reg.json(), ensure_ascii=False)
            except Exception:
                pass
            pytest.fail(f"SUBMIT_FAIL {state_code}: {detail}")

    trans_r = await client.get(f"/api/process/{iid}/transitions", headers=headers)
    assert trans_r.status_code == 200, trans_r.text
    triggers = [t.get("trigger_event") for t in trans_r.json().get("transitions") or []]
    assert trigger in triggers, f"NO_TRIGGER: expected {trigger}, got {triggers}"

    trig_r = await client.post(
        f"/api/process/{iid}/trigger",
        json={"trigger_event": trigger, "payload": {}},
        headers=headers,
    )
    assert trig_r.status_code == 200, trig_r.text
    body = trig_r.json()
    assert body.get("success") is True, f"TRIGGER_FAIL: {body.get('error')}"

    status_r = await client.get(f"/api/process/{iid}/status", headers=headers)
    assert status_r.status_code == 200
    new_state = status_r.json().get("current_state")
    assert new_state == to_state, f"STUCK: expected {to_state}, got {new_state}"
