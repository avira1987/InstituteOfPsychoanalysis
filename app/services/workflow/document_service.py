"""Service C - PDF / Certificate / Transcript Service.

Replaces the log-only stub for document generation. Each ``generate_*`` action
produces a real document record (with a textual body assembled from student
data) stored in ``Student.extra_data['documents']``. Subsequent actions mutate
that record: signing, archiving and portal publishing.

Document record shape:
    {
        "id", "type", "title_fa", "body_fa", "created_at",
        "signed": bool, "archived": bool, "portal_visible": bool,
        "export_enabled": bool, "url": "/documents/<id>"
    }
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.workflow import _common as C

_DOC_TITLES = {
    "generate_certificate": ("certificate", "گواهی پایان دوره"),
    "generate_term_transcript": ("term_transcript", "کارنامه ترم"),
    "generate_cumulative_transcript": ("cumulative_transcript", "کارنامه کل"),
    "generate_decline_list": ("decline_list", "فهرست انصراف/عدم احراز"),
    "generate_termination_letter": ("termination_letter", "نامه خاتمه"),
    "generate_pdf_export": ("pdf_export", "خروجی PDF"),
}


def _docs(extra: dict) -> list:
    docs = list(extra.get("documents") or [])
    extra["documents"] = docs
    return docs


def _build_body(doc_type: str, student, ctx: dict) -> str:
    code = getattr(student, "student_code", "—")
    term = getattr(student, "current_term", "—")
    course = getattr(student, "course_type", "—")
    if doc_type == "term_transcript":
        return f"کارنامه ترم {term} — دانشجو {code} — دوره {course}"
    if doc_type == "cumulative_transcript":
        return f"کارنامه کل — دانشجو {code} — دوره {course} — تعداد ترم‌ها: {getattr(student, 'term_count', '—')}"
    if doc_type == "certificate":
        return f"گواهی پایان دوره {course} برای دانشجو {code}"
    if doc_type == "termination_letter":
        reason = ctx.get("termination_reason_fa") or ctx.get("reason_fa") or "—"
        return f"نامه خاتمه برای دانشجو {code} — علت: {reason}"
    if doc_type == "decline_list":
        return f"فهرست انصراف/عدم احراز — مرتبط با فرایند {ctx.get('process_code') or '—'}"
    return f"سند {doc_type} برای دانشجو {code}"


def _latest_doc(docs: list, doc_type: Optional[str] = None) -> Optional[dict]:
    for d in reversed(docs):
        if doc_type is None or d.get("type") == doc_type:
            return d
    return None


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    ctx = C.merged_context(instance, action, context)
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"

    extra = C.student_extra(student)
    docs = _docs(extra)
    result = action_type

    if action_type in _DOC_TITLES:
        doc_type, title = _DOC_TITLES[action_type]
        doc = {
            "id": C.new_id(),
            "type": doc_type,
            "title_fa": action.get("title_fa") or title,
            "body_fa": _build_body(doc_type, student, ctx),
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "created_at": C.now_iso(),
            "signed": False,
            "archived": False,
            "portal_visible": False,
            "export_enabled": doc_type == "pdf_export",
        }
        doc["url"] = f"/documents/{doc['id']}"
        docs.append(doc)
        result = f"document_created type={doc_type} id={doc['id']}"

    elif action_type == "enable_pdf_export":
        target = _latest_doc(docs)
        if target:
            target["export_enabled"] = True
            result = f"pdf_export_enabled id={target['id']}"
        else:
            extra["pdf_export_enabled"] = True
            result = "pdf_export_enabled global"

    elif action_type == "apply_electronic_signature_and_seal":
        target = _latest_doc(docs, ctx.get("document_type")) or _latest_doc(docs)
        if not target:
            return "no_document_to_sign"
        target["signed"] = True
        target["signed_at"] = C.now_iso()
        target["seal"] = "electronic"
        result = f"document_signed id={target['id']}"

    elif action_type == "archive_letter_in_student_file":
        target = _latest_doc(docs, "termination_letter") or _latest_doc(docs)
        if not target:
            return "no_document_to_archive"
        target["archived"] = True
        target["archived_at"] = C.now_iso()
        result = f"document_archived id={target['id']}"

    elif action_type == "upload_certificate_to_portal":
        target = _latest_doc(docs, "certificate") or _latest_doc(docs)
        if not target:
            return "no_document_to_upload"
        target["portal_visible"] = True
        target["uploaded_at"] = C.now_iso()
        result = f"certificate_uploaded id={target['id']}"

    else:
        C.record_event(instance, action_type, {"unhandled_in": "document_service"})
        return f"document_noop:{action_type}"

    C.commit_student_extra(student, extra)
    C.record_event(instance, action_type, {"result": result})
    return result
