"""
Onboarding flow-through API tests.

مسیر ورود مرکز: آماده‌سازی ترم پاییز → ثبت‌نام آشنایی → پایان ترم آشنایی

Run:
  python -m scripts.flow_through.build_matrix --track onboarding
  python -m scripts.flow_through.resolve_ui_surface --track onboarding
  FLOW_THROUGH_TRACK=onboarding pytest tests/flow_through/test_onboarding_flow.py -q
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import authenticate_user, create_access_token
from app.meta.seed import load_process, load_rules
from scripts.flow_through.build_sample_values import build_sample_values
from tests.helpers.flow_through_interview_fixture import ensure_open_interview_slot

ROOT = Path(__file__).resolve().parents[2]
ONBOARDING_MATRIX = ROOT / "reports" / "flow_through" / "onboarding" / "matrix_enriched.json"

pytestmark = pytest.mark.asyncio


def _load_onboarding_rows() -> list[dict[str, Any]]:
    if not ONBOARDING_MATRIX.is_file():
        return []
    data = json.loads(ONBOARDING_MATRIX.read_text(encoding="utf-8"))
    rows = data.get("rows") or []
    only = os.getenv("FLOW_THROUGH_PROCESS")
    if only:
        rows = [r for r in rows if r.get("process_code") == only]
    proof = os.getenv("FLOW_THROUGH_PROOF")
    if proof:
        rows = [r for r in rows if r.get("process_code") == proof]
    return rows


ONBOARDING_ROWS = _load_onboarding_rows()


def _matrix_ids(row: dict[str, Any]) -> str:
    return row.get("step_id") or f"{row.get('process_code')}/{row.get('state_code')}"


_ROLE_LOGIN_MAP = {
    "course_committee_executive": ("course_committee1", "demo123"),
    "scientific_officer_course_committee": ("course_committee1", "demo123"),
    "deputy_education_director": ("deputy_education1", "demo123"),
    "admissions_officer": ("staff1", "demo123"),
    "staff": ("staff1", "demo123"),
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
    path = ROOT / "metadata" / "processes" / f"{process_code}.json"
    if path.is_file():
        await load_rules(db_session)
        await load_process(db_session, path)
        await db_session.commit()


async def _execute_interview_book(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    instance_id: str,
    headers: dict[str, str],
    process_code: str,
) -> None:
    course_type = "comprehensive" if "comprehensive" in process_code else "introductory"
    slot = await ensure_open_interview_slot(db_session, course_type=course_type)
    await db_session.commit()
    book_r = await client.post(
        "/api/interview-slots/book",
        json={"instance_id": instance_id, "slot_id": str(slot.id)},
        headers=headers,
    )
    if book_r.status_code != 200:
        pytest.fail(f"INTERVIEW_BOOK_FAIL: {book_r.text}")


async def _execute_interview_result(
    client: AsyncClient,
    *,
    instance_id: str,
    headers: dict[str, str],
    trigger: str,
    to_state: str,
    field_specs: list[dict[str, Any]] | None = None,
) -> None:
    result_map = {
        "result_conditional_therapy": ("conditional_therapy", "result_conditional_therapy"),
        "result_single_course": ("single_course", "result_single_course"),
        "result_full_admission": ("full_admission", "result_full_admission"),
        "rejected": ("rejected", "rejected"),
    }
    interview_result, target = result_map.get(to_state, ("full_admission", "result_full_admission"))
    payload: dict[str, Any] = {
        "interview_result": interview_result,
        "to_state": target,
        "allowed_course_count": 5 if interview_result == "full_admission" else 1,
    }
    if interview_result == "rejected":
        payload["rejection_reason"] = "تست flow-through"
    sample = build_sample_values(field_specs or [])
    payload.update({k: v for k, v in sample.items() if v is not None})
    trig_r = await client.post(
        f"/api/process/{instance_id}/trigger",
        json={"trigger_event": trigger, "payload": payload},
        headers=headers,
    )
    if trig_r.status_code != 200:
        pytest.fail(f"INTERVIEW_RESULT_FAIL: {trig_r.text}")
    body = trig_r.json()
    assert body.get("success") is True, f"INTERVIEW_RESULT_FAIL: {body.get('error')}"


@pytest.mark.parametrize("row", ONBOARDING_ROWS, ids=_matrix_ids)
async def test_onboarding_flow_step(
    row: dict[str, Any],
    db_session: AsyncSession,
    flow_api_client: AsyncClient,
):
    if not ONBOARDING_ROWS:
        pytest.skip("Run: build_matrix --track onboarding && resolve_ui_surface --track onboarding")

    process_code = row["process_code"]
    state_code = row["state_code"]
    portal_role = row.get("portal_role") or row.get("required_role")
    required_role = row.get("required_role") or portal_role
    trigger = row["trigger"]
    to_state = row.get("to_state")
    action_type = row.get("action_type") or "standard"

    if not row.get("ui_surface_ok", True):
        pytest.skip(f"UI surface MISSING for {row.get('step_id')}")

    from app.flow_through.state_seeder import seed_instance_at_state
    from app.models.operational_models import Student, User

    await _ensure_process_loaded(db_session, process_code)
    seed = await seed_instance_at_state(
        db_session,
        process_code,
        state_code,
        student_code=f"FLOW-ONB-{process_code[:10]}-{state_code[:10]}"[:50],
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
        if process_code == "introductory_course_registration" and state_code == "documents_upload":
            st_r = await client.get(f"/api/process/{iid}/status", headers=headers)
            if st_r.status_code == 200 and st_r.json().get("current_state") == to_state:
                return

    if action_type == "interview_book":
        await _execute_interview_book(
            client, db_session, instance_id=iid, headers=headers, process_code=process_code
        )
    elif trigger == "interview_result_submitted":
        await _execute_interview_result(
            client,
            instance_id=iid,
            headers=headers,
            trigger=trigger,
            to_state=to_state,
            field_specs=row.get("field_specs"),
        )
    else:
        status_before = await client.get(f"/api/process/{iid}/status", headers=headers)
        if status_before.status_code == 200 and status_before.json().get("current_state") == to_state:
            return
        trans_r = await client.get(f"/api/process/{iid}/transitions", headers=headers)
        assert trans_r.status_code == 200, trans_r.text
        triggers = [t.get("trigger_event") for t in trans_r.json().get("transitions") or []]
        payload: dict[str, Any] = {}
        if trigger == "documents_submitted":
            payload = {"documents_complete": True}
        if trigger in triggers or trigger == "documents_submitted":
            trig_r = await client.post(
                f"/api/process/{iid}/trigger",
                json={"trigger_event": trigger, "payload": payload},
                headers=headers,
            )
        else:
            assert trigger in triggers, f"NO_TRIGGER: expected {trigger}, got {triggers}"
            trig_r = None  # unreachable
        assert trig_r.status_code == 200, trig_r.text
        body = trig_r.json()
        assert body.get("success") is True, f"TRIGGER_FAIL: {body.get('error')}"

    status_r = await client.get(f"/api/process/{iid}/status", headers=headers)
    assert status_r.status_code == 200
    new_state = status_r.json().get("current_state")
    acceptable = {to_state}
    if trigger == "interview_result_submitted" and to_state.startswith("result_"):
        acceptable.add("documents_upload")
    assert new_state in acceptable, f"STUCK: expected one of {sorted(acceptable)}, got {new_state}"
