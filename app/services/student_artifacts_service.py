"""Read-only student artifacts (transcripts, certificates) from extra_data."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.models.operational_models import Student

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


def _as_mapping(val: Any) -> dict[str, Any]:
    return StateMachineEngine._as_mapping(val)


def collect_student_artifacts(student: Student) -> list[dict[str, Any]]:
    """Documents visible to student in portal."""
    extra = _as_mapping(student.extra_data)
    docs = extra.get("documents") or []
    if not isinstance(docs, list):
        return []

    out: list[dict[str, Any]] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        doc_type = doc.get("type") or ""
        portal_visible = doc.get("portal_visible") is True
        signed = doc.get("signed") is True
        export_enabled = doc.get("export_enabled") is True
        if doc_type not in _ARTIFACT_TYPES:
            continue
        if not (portal_visible or signed or export_enabled):
            continue
        out.append(
            {
                "id": doc.get("id"),
                "type": doc_type,
                "title_fa": doc.get("title_fa") or doc_type,
                "body_fa": doc.get("body_fa"),
                "url": doc.get("url"),
                "process_code": doc.get("process_code"),
                "instance_id": doc.get("instance_id"),
                "created_at": doc.get("created_at"),
                "signed": signed,
                "portal_visible": portal_visible,
                "export_enabled": export_enabled,
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
    """Single portal-visible document by id (for student download/view)."""
    from sqlalchemy import select

    row = (
        await db.execute(select(Student).where(Student.id == student_id))
    ).scalars().first()
    if not row:
        return None
    for doc in collect_student_artifacts(row):
        if str(doc.get("id")) == str(doc_id):
            return doc
    return None
