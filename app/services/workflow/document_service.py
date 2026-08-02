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

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.student_artifact_pdf_service import interpolate_certificate_text
from app.services.term_end_snapshot_service import (
    apply_term_end_snapshot,
    rich_document_body,
)
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


def _transcript_pdf_context(student, ctx: dict) -> dict[str, Any]:
    return {
        "term_code": ctx.get("term_code") or getattr(student, "current_term", None),
        "term_transcript_rows": list(ctx.get("term_transcript_rows") or []),
        "term_gpa": ctx.get("term_gpa"),
        "cumulative_gpa": ctx.get("cumulative_gpa"),
    }


async def _certificate_pdf_context(
    db: AsyncSession,
    student,
    action: dict,
    ctx: dict,
) -> dict[str, Any]:
    user = None
    if getattr(student, "user_id", None):
        user = await C.get_user(db, student.user_id)
    template = (
        action.get("certificate_text_fa")
        or ctx.get("certificate_text_fa")
        or ""
    )
    hours_formula = action.get("hours_formula") or ctx.get("hours_formula")
    resolved = interpolate_certificate_text(
        template,
        student=student,
        user=user,
        ctx=ctx,
        hours_formula=hours_formula,
    ) if template else ""
    return {
        "certificate_template": action.get("certificate_template") or ctx.get("certificate_template"),
        "certificate_text_fa": template,
        "certificate_text_resolved": resolved,
        "signed_by": action.get("signed_by") or ctx.get("signed_by") or "",
        "hours_formula": hours_formula,
        "total_units": ctx.get("total_units") or ctx.get("totalUnits"),
        "total_hours": ctx.get("total_hours") or ctx.get("totalHours"),
        "completion_date": ctx.get("completion_date") or ctx.get("completionDate"),
    }


def _build_pdf_context(
    doc_type: str,
    student,
    ctx: dict,
    action: dict,
    pdf_ctx_extra: Optional[dict] = None,
) -> dict[str, Any]:
    pdf_ctx: dict[str, Any] = dict(pdf_ctx_extra or {})
    if doc_type in ("term_transcript", "cumulative_transcript", "pdf_export"):
        pdf_ctx.update(_transcript_pdf_context(student, ctx))
    elif doc_type == "certificate":
        pdf_ctx.update({k: v for k, v in (pdf_ctx_extra or {}).items() if v is not None})
    elif doc_type == "decline_list":
        pdf_ctx["failed_courses"] = list(ctx.get("failed_courses") or [])
        pdf_ctx["process_code"] = ctx.get("process_code")
    elif doc_type == "termination_letter":
        pdf_ctx["termination_reason_fa"] = (
            ctx.get("termination_reason_fa") or ctx.get("reason_fa")
        )
        pdf_ctx["reason_fa"] = ctx.get("reason_fa")
    if action.get("signed_by") and not pdf_ctx.get("signed_by"):
        pdf_ctx["signed_by"] = action.get("signed_by")
    return pdf_ctx


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    ctx = C.merged_context(instance, action, context)
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"

    extra = C.student_extra(student)
    docs = _docs(extra)
    result = action_type
    ctx = C.merged_context(instance, action, context)

    if action_type in ("generate_term_transcript", "generate_cumulative_transcript"):
        await apply_term_end_snapshot(db, instance, student)
        ctx = C.merged_context(instance, action, context)

    if action_type in _DOC_TITLES:
        doc_type, title = _DOC_TITLES[action_type]
        pdf_ctx_extra = None
        if doc_type == "certificate":
            pdf_ctx_extra = await _certificate_pdf_context(db, student, action, ctx)
        body = (
            rich_document_body(doc_type, student, ctx)
            if doc_type in ("term_transcript", "cumulative_transcript") and ctx.get("term_transcript_rows")
            else (
                pdf_ctx_extra.get("certificate_text_resolved")
                if doc_type == "certificate" and pdf_ctx_extra and pdf_ctx_extra.get("certificate_text_resolved")
                else _build_body(doc_type, student, ctx)
            )
        )
        doc = {
            "id": C.new_id(),
            "type": doc_type,
            "title_fa": action.get("title_fa") or title,
            "body_fa": body,
            "process_code": instance.process_code,
            "instance_id": str(instance.id),
            "created_at": C.now_iso(),
            "signed": False,
            "archived": False,
            "portal_visible": doc_type in ("term_transcript", "cumulative_transcript", "pdf_export"),
            "export_enabled": doc_type in ("term_transcript", "cumulative_transcript", "pdf_export"),
            "pdf_context": _build_pdf_context(doc_type, student, ctx, action, pdf_ctx_extra),
        }
        doc["url"] = f"/api/process/student/{instance.student_id}/documents/{doc['id']}"
        doc["pdf_url"] = f"/api/process/student/{instance.student_id}/documents/{doc['id']}.pdf"
        docs.append(doc)
        result = f"document_created type={doc_type} id={doc['id']}"

    elif action_type == "enable_pdf_export":
        exportable = [
            d
            for d in docs
            if d.get("type") in ("term_transcript", "cumulative_transcript", "pdf_export", "certificate")
        ]
        if exportable:
            for d in exportable:
                d["export_enabled"] = True
                if d.get("type") in ("term_transcript", "cumulative_transcript", "pdf_export"):
                    d["portal_visible"] = True
            result = f"pdf_export_enabled n={len(exportable)}"
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
