"""
شبیه‌سازی جریان پنل دانشجو (مثل UI):
۱) بارگذاری پروفایل → GET /api/students/me
۲) خواندن مسیر اصلی → GET /api/process/{id}/status و transitions

هدف: اگر primary_instance_id خالی بود ولی فرایند ثبت‌نام وجود داشت، با اولین /me ترمیم شود.
"""

from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.engine import StateMachineEngine
from app.database import get_db
from app.main import app
from app.meta.seed import load_process


@pytest_asyncio.fixture
async def student_portal_ui_client(db_session: AsyncSession, sample_student_user):
    """
    کلاینت با هویت دانشجو — همان چیزی که پس از لاگین به پنل می‌رسد
    (توکن واقعی نداریم؛ get_current_user را با کاربر دانشجو override می‌کنیم).
    """
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
async def test_student_portal_flow_me_repairs_primary_then_process_apis_load_quest(
    student_portal_ui_client: AsyncClient,
    db_session: AsyncSession,
    sample_student,
    sample_student_user,
):
    """
    سناریو کامل مثل StudentPortal.loadData:
    - فرایند comprehensive_course_registration از قبل وجود دارد
    - extra_data بدون primary (دادهٔ قدیمی / خطای ثبت‌نام)
    - اولین GET /students/me باید primary را بنویسد
    - سپس همان فراخوانی‌هایی که کارت «مسیر» می‌زند باید ۲۰۰ بدهند
    """
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "comprehensive_course_registration.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="comprehensive_course_registration",
        student_id=sample_student.id,
        actor_id=sample_student_user.id,
        actor_role="student",
    )
    await db_session.commit()

    sample_student.extra_data = {}
    await db_session.commit()
    await db_session.refresh(sample_student)

    r_me = await student_portal_ui_client.get("/api/students/me")
    assert r_me.status_code == 200, r_me.text
    body = r_me.json()
    pid = body.get("extra_data") or {}
    assert pid.get("primary_instance_id") == str(instance.id)

    iid = pid["primary_instance_id"]
    r_status = await student_portal_ui_client.get(f"/api/process/{iid}/status")
    assert r_status.status_code == 200, r_status.text
    st = r_status.json()
    assert st.get("process_code") == "comprehensive_course_registration"
    assert st.get("current_state")

    r_tr = await student_portal_ui_client.get(f"/api/process/{iid}/transitions")
    assert r_tr.status_code == 200, r_tr.text
    assert "transitions" in r_tr.json()

    r_def = await student_portal_ui_client.get("/api/process/definitions/comprehensive_course_registration")
    assert r_def.status_code == 200, r_def.text
    assert r_def.json().get("process", {}).get("code") == "comprehensive_course_registration"


@pytest.mark.asyncio
async def test_student_me_idempotent_when_primary_already_valid(
    student_portal_ui_client: AsyncClient,
    db_session: AsyncSession,
    sample_student,
    sample_student_user,
):
    """اگر primary از قبل درست است، /me خطا نمی‌دهد و همان می‌ماند."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "comprehensive_course_registration.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="comprehensive_course_registration",
        student_id=sample_student.id,
        actor_id=sample_student_user.id,
        actor_role="student",
    )
    await db_session.commit()

    sample_student.extra_data = {"primary_instance_id": str(instance.id)}
    await db_session.commit()

    r1 = await student_portal_ui_client.get("/api/students/me")
    r2 = await student_portal_ui_client.get("/api/students/me")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["extra_data"]["primary_instance_id"] == str(instance.id)
