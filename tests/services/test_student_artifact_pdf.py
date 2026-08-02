"""Tests for student artifact PDF generation and download endpoint."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.main import app
from app.api.auth import get_current_user
from app.models.operational_models import Student
from app.services.student_artifact_pdf_service import (
    interpolate_certificate_text,
    render_student_document_pdf,
)
from app.services.student_artifacts_service import collect_student_artifacts


def _set_documents(student: Student, docs: list) -> None:
    extra = dict(student.extra_data or {})
    extra["documents"] = docs
    student.extra_data = extra
    flag_modified(student, "extra_data")


def test_collect_artifacts_omits_body_fa_and_includes_pdf_url(sample_student):
    _set_documents(
        sample_student,
        [
            {
                "id": "d1",
                "type": "term_transcript",
                "title_fa": "کارنامه ترم ۳",
                "body_fa": "متن محرمانه",
                "portal_visible": True,
            },
        ],
    )
    out = collect_student_artifacts(sample_student)
    assert len(out) == 1
    assert "body_fa" not in out[0]
    assert out[0]["pdf_download_url"].endswith("/documents/d1.pdf")


def test_render_term_transcript_pdf_starts_with_pdf_magic(sample_student):
    _set_documents(
        sample_student,
        [
            {
                "id": "t1",
                "type": "term_transcript",
                "title_fa": "کارنامه ترم",
                "body_fa": "fallback",
                "portal_visible": True,
                "pdf_context": {
                    "term_code": 3,
                    "term_transcript_rows": [
                        {
                            "course_name": "روانشناسی عمومی",
                            "units": 2,
                            "numeric_grade": 18,
                            "letter_grade": "A",
                            "pass_fail_status": "قبول",
                        }
                    ],
                    "term_gpa": 18.0,
                },
            }
        ],
    )
    doc = sample_student.extra_data["documents"][0]
    pdf_bytes = render_student_document_pdf(sample_student, doc)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500


def test_interpolate_certificate_text_replaces_placeholders(sample_student, sample_student_user):
    sample_student.extra_data = {
        **(sample_student.extra_data or {}),
        "first_name_fa": "علی",
        "last_name_fa": "احمدی",
        "birth_certificate_number": "123",
        "national_code": "0012345678",
    }
    template = (
        "گواهی می‌شود {student_name} با شناسنامه {id_number} و کد ملی {national_code} "
        "در {completion_date} دوره {total_units} واحد ({total_hours} ساعت) را گذرانده است."
    )
    out = interpolate_certificate_text(
        template,
        student=sample_student,
        user=sample_student_user,
        ctx={"completion_date": "1404/01/01", "total_units": 10},
        hours_formula="total_units * 13.5",
    )
    assert "علی احمدی" in out
    assert "0012345678" in out
    assert "1404/01/01" in out
    assert "135" in out


def test_render_certificate_pdf(sample_student):
    _set_documents(
        sample_student,
        [
            {
                "id": "c1",
                "type": "certificate",
                "title_fa": "گواهی",
                "signed": True,
                "pdf_context": {
                    "certificate_text_resolved": "گواهی می‌شود دانشجو دوره را تکمیل کرده است.",
                    "signed_by": "مسئول علمی",
                },
            }
        ],
    )
    doc = sample_student.extra_data["documents"][0]
    pdf_bytes = render_student_document_pdf(sample_student, doc)
    assert pdf_bytes[:4] == b"%PDF"


@pytest_asyncio.fixture
async def student_api_client(db_session: AsyncSession, sample_student_user):
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
async def test_pdf_download_endpoint_visible_document(
    db_session: AsyncSession,
    sample_student,
    student_api_client: AsyncClient,
):
    _set_documents(
        sample_student,
        [
            {
                "id": "d1",
                "type": "term_transcript",
                "title_fa": "کارنامه",
                "body_fa": "متن",
                "portal_visible": True,
                "pdf_context": {
                    "term_transcript_rows": [],
                    "term_gpa": None,
                },
            }
        ],
    )
    await db_session.commit()

    r = await student_api_client.get(
        f"/api/process/student/{sample_student.id}/documents/d1.pdf",
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_pdf_download_endpoint_hidden_document_returns_404(
    db_session: AsyncSession,
    sample_student,
    student_api_client: AsyncClient,
):
    _set_documents(
        sample_student,
        [
            {
                "id": "hidden",
                "type": "certificate",
                "title_fa": "گواهی",
                "portal_visible": False,
                "signed": False,
                "export_enabled": False,
                "pdf_context": {"certificate_text_resolved": "پیش‌نویس"},
            }
        ],
    )
    await db_session.commit()

    r = await student_api_client.get(
        f"/api/process/student/{sample_student.id}/documents/hidden.pdf",
    )
    assert r.status_code == 404
