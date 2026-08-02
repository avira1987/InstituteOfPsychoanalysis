"""Test process UI/API: forms and dashboard (BUILD_TODO § ز — بخش ۷)."""

import pytest
import pytest_asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db
from app.api.auth import get_current_user
from app.core.engine import StateMachineEngine
from app.meta.process_forms import get_process_forms, get_process_ui_requirements
from app.meta.seed import load_process
from app.models.operational_models import Student


def test_get_process_forms_returns_list():
    """get_process_forms returns a list (empty if process has no forms or missing)."""
    assert get_process_forms("nonexistent_process") == []
    assert isinstance(get_process_forms("session_payment"), list)


def test_get_process_forms_filter_by_state():
    """get_process_forms(process_code, state_code) returns only forms for that state."""
    forms = get_process_forms("fall_semester_preparation", state_code="calendar_entry")
    assert isinstance(forms, list)
    if forms:
        assert all(f.get("used_in_state") == "calendar_entry" for f in forms)


def test_get_process_forms_normalizes_missing_labels():
    """Missing label_fa values are normalized for UI rendering."""
    forms = get_process_forms("upgrade_to_ta", state_code="interview_scheduling")
    assert forms
    assert all(field.get("label_fa") for field in forms[0].get("fields", []))


def test_get_process_forms_fallback_semester_has_forms():
    """fall_semester_preparation has forms in JSON."""
    all_forms = get_process_forms("fall_semester_preparation")
    assert len(all_forms) >= 1
    assert any("form" in str(f).lower() or "code" in f for f in all_forms)


def test_committees_review_forms_for_supervision_state():
    """committees_review exposes supervision_recommendation form at supervision_review."""
    forms = get_process_forms("committees_review", state_code="supervision_review")
    assert len(forms) == 1
    assert forms[0].get("code") == "supervision_recommendation"
    field_names = {f["name"] for f in forms[0].get("fields", [])}
    assert "nezarat_recommendation_code" in field_names
    assert "nezarat_recommendation_fa" in field_names


def test_specialized_commission_review_has_decision_form():
    forms = get_process_forms("specialized_commission_review", state_code="commission_review")
    assert len(forms) == 1
    assert forms[0].get("code") == "commission_decision"


def test_get_process_ui_requirements_returns_dashboard():
    """ui_requirements is available for dashboard-style processes."""
    ui = get_process_ui_requirements("ta_track_completion")
    assert ui["dashboard"]["name_fa"]
    assert ui["dashboard"]["sections"]


def test_get_process_forms_marks_view_only_forms():
    """View-only forms with readonly fields normalize to kind 'form' (see process_forms._normalize_form)."""
    forms = get_process_forms("live_supervision_ta_evaluation")
    assert forms
    assert forms[0]["kind"] == "form"


@pytest.mark.asyncio
async def test_dashboard_structure_status_transitions_forms(
    db_session: AsyncSession, sample_student, sample_user
):
    """Dashboard combines status + transitions + forms for current state."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="session_payment",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    await db_session.commit()

    status = await engine.get_instance_status(instance.id)
    transitions = await engine.get_available_transitions(instance.id, sample_user.role)
    forms = get_process_forms(status.get("process_code", ""), state_code=status.get("current_state"))

    dashboard = {"status": status, "transitions": transitions, "forms": forms}
    assert "status" in dashboard
    assert "transitions" in dashboard
    assert "forms" in dashboard
    assert dashboard["status"]["current_state"] == "payment_due"
    assert isinstance(dashboard["transitions"], list)
    assert isinstance(dashboard["forms"], list)


# ─── API (HTTP) tests for دسته ز ───────────────────────────────────

@pytest_asyncio.fixture
async def process_api_client(db_session: AsyncSession, sample_user):
    """Authenticated client with get_db and get_current_user overridden for process API tests."""
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def session_payment_instance_for_api(db_session, sample_student, sample_user):
    """Load session_payment process and create one instance for API tests."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()
    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="session_payment",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    await db_session.commit()
    return instance


@pytest.mark.asyncio
async def test_api_get_definitions_forms(process_api_client):
    """دسته ز: GET /api/process/definitions/{code}/forms returns form metadata for UI."""
    r = await process_api_client.get(
        "/api/process/definitions/session_payment/forms"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["process_code"] == "session_payment"
    assert "forms" in data
    assert isinstance(data["forms"], list)


@pytest.mark.asyncio
async def test_api_get_process_definition_includes_ui_requirements(
    process_api_client, db_session: AsyncSession
):
    """Process definition response should include ui_requirements when present."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "live_supervision_ta_evaluation.json")
    await db_session.commit()

    r = await process_api_client.get(
        "/api/process/definitions/live_supervision_ta_evaluation"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["process"]["code"] == "live_supervision_ta_evaluation"
    assert "ui_requirements" in data["process"]
    assert data["process"]["ui_requirements"]["dashboard"]["name_fa"] == "داشبورد ارزیابی نهایی کمک‌مدرس (درس سوپرویژن زنده)"


@pytest.mark.asyncio
async def test_api_get_definitions_forms_with_state_filter(process_api_client):
    """دسته ز: GET .../forms?state=... returns only forms for that state."""
    r = await process_api_client.get(
        "/api/process/definitions/fall_semester_preparation/forms",
        params={"state": "calendar_entry"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["process_code"] == "fall_semester_preparation"
    assert data["state"] == "calendar_entry"
    assert isinstance(data["forms"], list)
    for f in data["forms"]:
        assert f.get("used_in_state") == "calendar_entry"


@pytest.mark.asyncio
async def test_api_get_instance_dashboard(
    process_api_client, session_payment_instance_for_api
):
    """دسته ز: GET /api/process/{id}/dashboard returns status + transitions + forms."""
    instance = session_payment_instance_for_api
    r = await process_api_client.get(
        f"/api/process/{instance.id}/dashboard"
    )
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "transitions" in data
    assert "forms" in data
    assert data["status"]["process_code"] == "session_payment"
    assert data["status"]["current_state"] == "payment_due"
    assert isinstance(data["transitions"], list)
    assert isinstance(data["forms"], list)
    assert "ui_requirements" in data


@pytest.mark.asyncio
async def test_api_get_instance_dashboard_includes_ui_requirements(
    process_api_client, db_session: AsyncSession, sample_student, sample_user
):
    """Dashboard response should include UI requirements for display-only processes."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "live_supervision_ta_evaluation.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="live_supervision_ta_evaluation",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="system",
    )
    await db_session.commit()

    r = await process_api_client.get(f"/api/process/{instance.id}/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "ui_requirements" in data
    assert data["ui_requirements"]["dashboard"]["name_fa"] == "داشبورد ارزیابی نهایی کمک‌مدرس (درس سوپرویژن زنده)"


@pytest.mark.asyncio
async def test_api_trigger_transition_with_payload(
    process_api_client, session_payment_instance_for_api
):
    """دسته ز: ارسال payload با trigger (رندر فرم و ارسال به trigger)."""
    instance = session_payment_instance_for_api
    r = await process_api_client.post(
        f"/api/process/{instance.id}/trigger",
        json={"trigger_event": "student_initiated_payment", "payload": {"amount": 1000}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert data.get("from_state") == "payment_due"
    assert data.get("to_state") == "payment_selection"


@pytest.mark.asyncio
async def test_api_start_intro_second_semester_blocked_when_class_access_blocked(
    process_api_client, db_session: AsyncSession, sample_student, sample_user
):
    """ثبت‌نام ترم دوم آشنایی وقتی class_access_blocked فعال است، از API رد شود."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "intro_second_semester_registration.json")
    sample_student.extra_data = {"class_access_blocked": True}
    db_session.add(sample_student)
    await db_session.commit()

    r = await process_api_client.post(
        "/api/process/start",
        json={
            "process_code": "intro_second_semester_registration",
            "student_id": str(sample_student.id),
        },
    )
    assert r.status_code == 400
    assert "مرخصی" in (r.json().get("detail") or "")


@pytest.mark.asyncio
async def test_api_start_educational_leave_sets_primary_instance(
    process_api_client, db_session: AsyncSession, sample_student, sample_user
):
    """شروع مرخصی آموزشی باید primary_instance_id دانشجو را به همان نمونه وصل کند."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "educational_leave.json")
    sample_student.extra_data = {}
    db_session.add(sample_student)
    await db_session.commit()

    r = await process_api_client.post(
        "/api/process/start",
        json={
            "process_code": "educational_leave",
            "student_id": str(sample_student.id),
        },
    )
    assert r.status_code == 200
    data = r.json()
    iid = data.get("instance_id")
    assert iid

    st = await db_session.get(Student, sample_student.id)
    extra = st.extra_data or {}
    if isinstance(extra, str):
        import json
        extra = json.loads(extra)
    assert extra.get("primary_instance_id") == iid


@pytest.mark.asyncio
async def test_api_educational_leave_forms_committee_review(process_api_client):
    """فرم تعیین جلسه برای committee_review در API متادیتا موجود است."""
    r = await process_api_client.get(
        "/api/process/definitions/educational_leave/forms",
        params={"state": "committee_review"},
    )
    assert r.status_code == 200
    data = r.json()
    codes = {f.get("code") for f in data.get("forms") or []}
    assert "leave_committee_meeting" in codes


@pytest.mark.asyncio
async def test_api_educational_leave_reject_requires_reason(
    process_api_client, db_session: AsyncSession, sample_student, sample_user, sample_student_user
):
    """رد درخواست مرخصی بدون علت باید 400 برگرداند."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "educational_leave.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="educational_leave",
        student_id=sample_student.id,
        actor_id=sample_student_user.id,
        actor_role="student",
    )
    await db_session.commit()

    for trigger, payload in [
        ("student_submitted", {"leave_terms": 1}),
        (
            "committee_set_meeting",
            {
                "committee_meeting_at": "2026-09-15T10:30:00+00:00",
                "committee_meeting_mode": "online",
                "committee_meeting_link": "https://meet.example/leave",
            },
        ),
        ("meeting_held", None),
    ]:
        result = await engine.execute_transition(
            instance.id,
            trigger,
            sample_user.id,
            "admin",
            payload,
        )
        assert result.success, result.error
        await db_session.commit()

    r = await process_api_client.post(
        f"/api/process/{instance.id}/trigger",
        json={"trigger_event": "committee_rejected", "payload": {}},
    )
    assert r.status_code == 400
    detail = r.json().get("detail") or ""
    assert "علت رد" in detail or "rejection_reason" in detail


@pytest_asyncio.fixture
async def student_process_api_client(db_session: AsyncSession, sample_student_user):
    """Authenticated student client for instance list API tests."""

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return sample_student_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_student_instances_hide_institute_semester_prep(
    db_session: AsyncSession,
    sample_student,
    sample_student_user,
    sample_user,
    student_process_api_client: AsyncClient,
):
    """دانشجو نباید فرایند آماده‌سازی ترم را در لیست نمونه‌های خود ببیند."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    await engine.start_process(
        process_code="fall_semester_preparation",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="course_committee_executive",
    )
    await engine.start_process(
        process_code="session_payment",
        student_id=sample_student.id,
        actor_id=sample_student_user.id,
        actor_role="student",
    )
    await db_session.commit()

    r = await student_process_api_client.get(
        f"/api/process/instances/student/{sample_student.id}"
    )
    assert r.status_code == 200
    codes = {item["process_code"] for item in r.json().get("instances") or []}
    assert "fall_semester_preparation" not in codes
    assert "session_payment" in codes
