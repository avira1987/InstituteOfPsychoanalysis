"""Read-only student artifacts (transcripts, certificates) from extra_data."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.core.resource_access import is_operator_role, normalize_role
from app.models.operational_models import Student, User

_ARTIFACT_TYPES = frozenset(
    {
        "certificate",
        "term_transcript",
        "cumulative_transcript",
        "pdf_export",
        "decline_list",
        "termination_letter",
    }
)

_COMMITTEE_READ_ROLES = frozenset({"supervision_committee", "committee"})


def _as_mapping(val: Any) -> dict[str, Any]:
    return StateMachineEngine._as_mapping(val)


def _doc_visible_to_student(doc: dict) -> bool:
    portal_visible = doc.get("portal_visible") is True
    signed = doc.get("signed") is True
    export_enabled = doc.get("export_enabled") is True
    return portal_visible or signed or export_enabled


def _can_read_draft_documents(user: Optional[User]) -> bool:
    if not user:
        return False
    role = normalize_role(user.role)
    return is_operator_role(role) or role in _COMMITTEE_READ_ROLES


def find_raw_student_document(student: Student, doc_id: str) -> Optional[dict[str, Any]]:
    extra = _as_mapping(student.extra_data)
    docs = extra.get("documents") or []
    if not isinstance(docs, list):
        return None
    for doc in docs:
        if isinstance(doc, dict) and str(doc.get("id")) == str(doc_id):
            if (doc.get("type") or "") in _ARTIFACT_TYPES:
                return doc
    return None


def document_accessible_to_user(doc: dict, user: Optional[User], *, is_own_student: bool) -> bool:
    if _can_read_draft_documents(user):
        return True
    if not is_own_student:
        return False
    return _doc_visible_to_student(doc)


def collect_student_artifacts(student: Student) -> list[dict[str, Any]]:
    """Documents visible to student in portal."""
    extra = _as_mapping(student.extra_data)
    docs = extra.get("documents") or []
    if not isinstance(docs, list):
        return []

    student_id = str(student.id)
    out: list[dict[str, Any]] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        doc_type = doc.get("type") or ""
        if doc_type not in _ARTIFACT_TYPES:
            continue
        if not _doc_visible_to_student(doc):
            continue
        doc_id = doc.get("id")
        out.append(
            {
                "id": doc_id,
                "type": doc_type,
                "title_fa": doc.get("title_fa") or doc_type,
                "url": doc.get("url"),
                "pdf_download_url": doc.get("pdf_url")
                or f"/api/process/student/{student_id}/documents/{doc_id}.pdf",
                "process_code": doc.get("process_code"),
                "instance_id": doc.get("instance_id"),
                "created_at": doc.get("created_at"),
                "signed": doc.get("signed") is True,
                "portal_visible": doc.get("portal_visible") is True,
                "export_enabled": doc.get("export_enabled") is True,
            }
        )
    out.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    return out


async def get_student_artifacts(
    db: AsyncSession,
    student_id: uuid.UUID,
) -> Optional[dict[str, Any]]:
    from sqlalchemy import select

    row = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalars().first()
    if not row:
        return None
    artifacts = collect_student_artifacts(row)
    return {
        "student_id": str(row.id),
        "student_code": row.student_code,
        "artifacts": artifacts,
        "count": len(artifacts),
    }


async def get_student_document(
    db: AsyncSession,
    student_id: uuid.UUID,
    doc_id: str,
) -> Optional[dict[str, Any]]:
    """Single portal-visible document by id (JSON detail for operators)."""
    from sqlalchemy import select

    row = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalars().first()
    if not row:
        return None
    for doc in collect_student_artifacts(row):
        if str(doc.get("id")) == str(doc_id):
            raw = find_raw_student_document(row, doc_id)
            if raw:
                return {
                    **doc,
                    "body_fa": raw.get("body_fa"),
                    "pdf_context": raw.get("pdf_context"),
                }
            return doc
    return None


async def get_student_document_for_pdf(
    db: AsyncSession,
    student_id: uuid.UUID,
    doc_id: str,
    current_user: User,
) -> tuple[Optional[Student], Optional[dict[str, Any]]]:
    """Load student + raw document if the user may download PDF."""
    from sqlalchemy import select

    row = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalars().first()
    if not row:
        return None, None
    raw = find_raw_student_document(row, doc_id)
    if not raw:
        return row, None
    is_own = False
    if normalize_role(current_user.role) == "student":
        is_own = row.user_id == current_user.id
    if not document_accessible_to_user(raw, current_user, is_own_student=is_own):
        return row, None
    return row, raw
