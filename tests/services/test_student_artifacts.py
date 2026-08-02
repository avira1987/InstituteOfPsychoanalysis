"""Tests for student artifacts (transcripts/certificates) collection and fetch."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.services.student_artifacts_service import (
    collect_student_artifacts,
    get_student_artifacts,
    get_student_document,
)


def _set_documents(student, docs):
    extra = dict(student.extra_data or {})
    extra["documents"] = docs
    student.extra_data = extra
    flag_modified(student, "extra_data")


def test_collect_only_visible_artifacts(sample_student):
    _set_documents(
        sample_student,
        [
            {
                "id": "d1",
                "type": "term_transcript",
                "title_fa": "کارنامه ترم ۳",
                "body_fa": "...",
                "portal_visible": True,
            },
            {
                "id": "d2",
                "type": "certificate",
                "title_fa": "گواهی",
                "portal_visible": False,
                "signed": False,
            },
            {"id": "d3", "type": "internal_note", "portal_visible": True},
        ],
    )
    out = collect_student_artifacts(sample_student)
    ids = {d["id"] for d in out}
    assert "d1" in ids
    assert "body_fa" not in out[0]
    assert out[0]["pdf_download_url"].endswith("/documents/d1.pdf")
    assert "d2" not in ids  # not visible/signed/exportable
    assert "d3" not in ids  # type not allowed


def test_signed_certificate_visible(sample_student):
    _set_documents(
        sample_student,
        [{"id": "c1", "type": "certificate", "title_fa": "گواهی", "signed": True}],
    )
    out = collect_student_artifacts(sample_student)
    assert len(out) == 1
    assert out[0]["signed"] is True


@pytest.mark.asyncio
async def test_get_student_artifacts_payload(db_session: AsyncSession, sample_student):
    _set_documents(
        sample_student,
        [{"id": "d1", "type": "pdf_export", "export_enabled": True, "title_fa": "خروجی"}],
    )
    await db_session.commit()
    payload = await get_student_artifacts(db_session, sample_student.id)
    assert payload is not None
    assert payload["count"] == 1
    assert payload["artifacts"][0]["id"] == "d1"


@pytest.mark.asyncio
async def test_get_student_document_by_id(db_session: AsyncSession, sample_student):
    _set_documents(
        sample_student,
        [
            {
                "id": "d1",
                "type": "term_transcript",
                "title_fa": "کارنامه",
                "body_fa": "محتوا",
                "portal_visible": True,
            }
        ],
    )
    await db_session.commit()
    doc = await get_student_document(db_session, sample_student.id, "d1")
    assert doc is not None
    assert doc["body_fa"] == "محتوا"
    missing = await get_student_document(db_session, sample_student.id, "nope")
    assert missing is None
