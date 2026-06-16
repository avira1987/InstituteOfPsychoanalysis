"""API فرم‌های داینامیک و منوی پورتال."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_current_user, require_role
from app.config import get_settings
from app.database import get_db
from app.models.dynamic_forms import (
    FormApprovalStep,
    FormAssignment,
    FormFieldFile,
    FormResponse,
    FormTemplate,
    FormTemplateVersion,
    PortalNavConfig,
)
from app.models.operational_models import ProcessInstance, Student, User
from app.services.dynamic_form_validation import merge_dynamic_into_context, validate_dynamic_answers
from app.services.forms.validate import filter_schema_for_role

router = APIRouter(prefix="/api/dynamic-forms", tags=["DynamicForms"])

CAN_MANAGE = ("admin", "staff")

_FIELD_NAME_RE = re.compile(r"^[a-zA-Z0-9_]{1,120}$")
_ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _is_file_descriptor(v: Any) -> bool:
    return isinstance(v, dict) and bool(v.get("url") or v.get("file_name") or v.get("content_base64"))


def _norm_role(r: str) -> str:
    return (r or "").strip().lower()


# ─── Schemas ───────────────────────────────────────────────────


class FormTemplateCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=80)
    name_fa: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    audience: str = Field("both", pattern="^(student|operator|both)$")


class FormTemplateUpdate(BaseModel):
    name_fa: Optional[str] = None
    description: Optional[str] = None
    audience: Optional[str] = Field(None, pattern="^(student|operator|both)$")


class FormVersionCreate(BaseModel):
    form_schema_json: dict[str, Any]
    publish: bool = True


class FormAssignmentCreate(BaseModel):
    template_id: str
    template_version_id: Optional[str] = None
    assignment_type: str = Field(..., pattern="^(portal|process|standalone)$")
    portal_role: Optional[str] = None
    portal_section: Optional[str] = None
    process_code: Optional[str] = None
    state_code: Optional[str] = None
    context_key: Optional[str] = Field(None, max_length=80)
    sort_order: int = 0
    active: bool = True


class FormAssignmentUpdate(BaseModel):
    template_version_id: Optional[str] = None
    portal_role: Optional[str] = None
    portal_section: Optional[str] = None
    process_code: Optional[str] = None
    state_code: Optional[str] = None
    context_key: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class FormResponseCreate(BaseModel):
    template_version_id: str
    assignment_id: Optional[str] = None
    instance_id: Optional[str] = None
    answers_json: dict[str, Any] = Field(default_factory=dict)
    submit: bool = False


class FormResponsePatch(BaseModel):
    answers_json: dict[str, Any]
    submit: bool = False


class ResponseApproveBody(BaseModel):
    comment: Optional[str] = None
    field_status: Optional[dict[str, Any]] = None


class ResponseRejectBody(BaseModel):
    comment: Optional[str] = None
    field_status: Optional[dict[str, Any]] = None
    resubmit_fields: Optional[list[str]] = None


class ResponseUnlockBody(BaseModel):
    fields: list[str] = Field(default_factory=list)


class PortalNavPut(BaseModel):
    items_json: list[dict[str, Any]]
    merge_mode: str = Field("append", pattern="^(append|prepend|replace)$")


# ─── Helpers ─────────────────────────────────────────────────────


async def _latest_published_version(
    db: AsyncSession, template_id: uuid.UUID
) -> Optional[FormTemplateVersion]:
    stmt = (
        select(FormTemplateVersion)
        .where(
            FormTemplateVersion.template_id == template_id,
            FormTemplateVersion.published_at.isnot(None),
        )
        .order_by(FormTemplateVersion.version.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def _resolve_version_for_assignment(
    db: AsyncSession, a: FormAssignment
) -> Optional[FormTemplateVersion]:
    if a.template_version_id:
        r = await db.execute(select(FormTemplateVersion).where(FormTemplateVersion.id == a.template_version_id))
        return r.scalars().first()
    return await _latest_published_version(db, a.template_id)


async def _ensure_student_instance(db: AsyncSession, user: User, inst: ProcessInstance) -> None:
    if _norm_role(user.role) != "student":
        return
    st = (await db.execute(select(Student).where(Student.user_id == user.id))).scalars().first()
    if not st or st.id != inst.student_id:
        raise HTTPException(status_code=403, detail="این فرایند متعلق به شما نیست.")


# ─── Templates CRUD ─────────────────────────────────────────────


@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*CAN_MANAGE)),
):
    r = await db.execute(select(FormTemplate).order_by(FormTemplate.code))
    rows = r.scalars().all()
    return {
        "templates": [
            {
                "id": str(t.id),
                "code": t.code,
                "name_fa": t.name_fa,
                "description": t.description,
                "audience": t.audience,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in rows
        ]
    }


@router.post("/templates", status_code=201)
async def create_template(
    body: FormTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*CAN_MANAGE)),
):
    code = body.code.strip()
    exists = (await db.execute(select(FormTemplate).where(FormTemplate.code == code))).scalars().first()
    if exists:
        raise HTTPException(status_code=400, detail="این کد قالب قبلاً ثبت شده است.")
    t = FormTemplate(
        id=uuid.uuid4(),
        code=code,
        name_fa=body.name_fa.strip(),
        description=body.description,
        audience=body.audience,
        created_by_id=user.id,
    )
    db.add(t)
    await db.flush()
    v = FormTemplateVersion(
        id=uuid.uuid4(),
        template_id=t.id,
        version=1,
        schema_json={"fields": []},
        published_at=datetime.now(timezone.utc),
    )
    db.add(v)
    await db.flush()
    return {"id": str(t.id), "default_version_id": str(v.id)}


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*CAN_MANAGE)),
):
    tid = uuid.UUID(template_id)
    t = (await db.execute(select(FormTemplate).where(FormTemplate.id == tid))).scalars().first()
    if not t:
        raise HTTPException(status_code=404)
    vers = (
        (
            await db.execute(
                select(FormTemplateVersion)
                .where(FormTemplateVersion.template_id == tid)
                .order_by(FormTemplateVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": str(t.id),
        "code": t.code,
        "name_fa": t.name_fa,
        "description": t.description,
        "audience": t.audience,
        "versions": [
            {
                "id": str(v.id),
                "version": v.version,
                "published_at": v.published_at.isoformat() if v.published_at else None,
                "schema_json": v.schema_json,
            }
            for v in vers
        ],
    }


@router.patch("/templates/{template_id}")
async def patch_template(
    template_id: str,
    body: FormTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*CAN_MANAGE)),
):
    tid = uuid.UUID(template_id)
    t = (await db.execute(select(FormTemplate).where(FormTemplate.id == tid))).scalars().first()
    if not t:
        raise HTTPException(status_code=404)
    if body.name_fa is not None:
        t.name_fa = body.name_fa
    if body.description is not None:
        t.description = body.description
    if body.audience is not None:
        t.audience = body.audience
    return {"ok": True}


@router.post("/templates/{template_id}/versions", status_code=201)
async def publish_version(
    template_id: str,
    body: FormVersionCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*CAN_MANAGE)),
):
    tid = uuid.UUID(template_id)
    t = (await db.execute(select(FormTemplate).where(FormTemplate.id == tid))).scalars().first()
    if not t:
        raise HTTPException(status_code=404)
    r = await db.execute(select(func.max(FormTemplateVersion.version)).where(FormTemplateVersion.template_id == tid))
    max_v = r.scalar()
    next_v = (max_v or 0) + 1
    now = datetime.now(timezone.utc) if body.publish else None
    v = FormTemplateVersion(
        id=uuid.uuid4(),
        template_id=tid,
        version=next_v,
        schema_json=body.form_schema_json,
        published_at=now,
    )
    db.add(v)
    await db.flush()
    return {"id": str(v.id), "version": next_v}


# ─── Assignments ────────────────────────────────────────────────


@router.get("/assignments")
async def list_assignments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*CAN_MANAGE)),
    process_code: Optional[str] = None,
    state_code: Optional[str] = None,
):
    stmt = select(FormAssignment).where(FormAssignment.active.is_(True))
    if process_code:
        stmt = stmt.where(FormAssignment.process_code == process_code.strip())
    if state_code:
        stmt = stmt.where(FormAssignment.state_code == state_code.strip())
    stmt = stmt.order_by(FormAssignment.sort_order, FormAssignment.created_at)
    rows = (await db.execute(stmt)).scalars().all()
    out = []
    for a in rows:
        out.append(
            {
                "id": str(a.id),
                "template_id": str(a.template_id),
                "template_version_id": str(a.template_version_id) if a.template_version_id else None,
                "assignment_type": a.assignment_type,
                "portal_role": a.portal_role,
                "portal_section": a.portal_section,
                "process_code": a.process_code,
                "state_code": a.state_code,
                "context_key": a.context_key,
                "sort_order": a.sort_order,
            }
        )
    return {"assignments": out}


@router.post("/assignments", status_code=201)
async def create_assignment(
    body: FormAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*CAN_MANAGE)),
):
    tid = uuid.UUID(body.template_id)
    t = (await db.execute(select(FormTemplate).where(FormTemplate.id == tid))).scalars().first()
    if not t:
        raise HTTPException(status_code=404, detail="قالب یافت نشد.")
    tv_id = uuid.UUID(body.template_version_id) if body.template_version_id else None
    if tv_id:
        tv = (await db.execute(select(FormTemplateVersion).where(FormTemplateVersion.id == tv_id))).scalars().first()
        if not tv or tv.template_id != tid:
            raise HTTPException(status_code=400, detail="نسخه متعلق به این قالب نیست.")
    a = FormAssignment(
        id=uuid.uuid4(),
        template_id=tid,
        template_version_id=tv_id,
        assignment_type=body.assignment_type,
        portal_role=body.portal_role,
        portal_section=body.portal_section,
        process_code=body.process_code,
        state_code=body.state_code,
        context_key=(body.context_key or "").strip() or None,
        sort_order=body.sort_order,
        active=body.active,
    )
    db.add(a)
    await db.flush()
    return {"id": str(a.id)}


@router.patch("/assignments/{assignment_id}")
async def patch_assignment(
    assignment_id: str,
    body: FormAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*CAN_MANAGE)),
):
    aid = uuid.UUID(assignment_id)
    a = (await db.execute(select(FormAssignment).where(FormAssignment.id == aid))).scalars().first()
    if not a:
        raise HTTPException(status_code=404)
    if body.template_version_id is not None:
        a.template_version_id = uuid.UUID(body.template_version_id) if body.template_version_id else None
    if body.portal_role is not None:
        a.portal_role = body.portal_role
    if body.portal_section is not None:
        a.portal_section = body.portal_section
    if body.process_code is not None:
        a.process_code = body.process_code
    if body.state_code is not None:
        a.state_code = body.state_code
    if body.context_key is not None:
        a.context_key = body.context_key.strip() or None
    if body.sort_order is not None:
        a.sort_order = body.sort_order
    if body.active is not None:
        a.active = body.active
    return {"ok": True}


# ─── Open forms for instance (student / staff) ───────────────────


@router.get("/open-for-instance/{instance_id}")
async def open_for_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    iid = uuid.UUID(instance_id)
    inst = (await db.execute(select(ProcessInstance).where(ProcessInstance.id == iid))).scalars().first()
    if not inst:
        raise HTTPException(status_code=404, detail="نمونه فرایند یافت نشد.")
    await _ensure_student_instance(db, user, inst)
    if _norm_role(user.role) == "student" and inst.is_completed:
        return {"assignments": []}

    stmt = (
        select(FormAssignment)
        .where(
            FormAssignment.active.is_(True),
            FormAssignment.assignment_type == "process",
            FormAssignment.process_code == inst.process_code,
            FormAssignment.state_code == inst.current_state_code,
        )
        .order_by(FormAssignment.sort_order)
    )
    rows = (await db.execute(stmt)).scalars().all()
    role = _norm_role(user.role)
    out = []
    for a in rows:
        ver = await _resolve_version_for_assignment(db, a)
        if not ver:
            continue
        tmpl = (await db.execute(select(FormTemplate).where(FormTemplate.id == a.template_id))).scalars().first()
        schema = ver.schema_json if isinstance(ver.schema_json, dict) else {"fields": []}
        # فیلتر نقش: فیلدهای محرمانه/محدود برای نقش جاری حذف می‌شوند
        schema = filter_schema_for_role(schema, role)
        # آخرین پاسخ این انتساب برای پیش‌پرکردن/نمایش وضعیت تأیید
        last_resp = (
            await db.execute(
                select(FormResponse)
                .where(FormResponse.assignment_id == a.id, FormResponse.instance_id == inst.id)
                .order_by(FormResponse.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        out.append(
            {
                "assignment_id": str(a.id),
                "template_id": str(a.template_id),
                "template_code": tmpl.code if tmpl else "",
                "template_name_fa": tmpl.name_fa if tmpl else "",
                "version_id": str(ver.id),
                "schema_json": schema,
                "context_key": a.context_key or (tmpl.code if tmpl else None),
                "submit_label_fa": a.submit_label_fa,
                "header_fa": a.header_fa,
                "response": (
                    {
                        "id": str(last_resp.id),
                        "status": last_resp.status,
                        "answers_json": last_resp.answers_json,
                        "field_status": last_resp.field_status,
                        "edit_unlocked_fields": last_resp.edit_unlocked_fields,
                    }
                    if last_resp
                    else None
                ),
            }
        )
    return {"assignments": out, "instance_id": str(inst.id), "current_state": inst.current_state_code}


# ─── Responses ───────────────────────────────────────────────────


@router.post("/responses", status_code=201)
async def create_or_update_response(
    body: FormResponseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    vid = uuid.UUID(body.template_version_id)
    ver = (await db.execute(select(FormTemplateVersion).where(FormTemplateVersion.id == vid))).scalars().first()
    if not ver:
        raise HTTPException(status_code=404, detail="نسخه قالب یافت نشد.")

    schema = ver.schema_json or {}
    missing: list[str] = []
    if body.submit:
        ok, missing = validate_dynamic_answers(
            schema if isinstance(schema, dict) else {}, body.answers_json, role=_norm_role(user.role)
        )
        if not ok:
            raise HTTPException(status_code=400, detail={"error": "validation_failed", "missing": missing})

    assignment_id = uuid.UUID(body.assignment_id) if body.assignment_id else None
    instance_id = uuid.UUID(body.instance_id) if body.instance_id else None
    aid = assignment_id
    a: Optional[FormAssignment] = None
    if aid:
        a = (await db.execute(select(FormAssignment).where(FormAssignment.id == aid))).scalars().first()

    student_id: Optional[uuid.UUID] = None
    if _norm_role(user.role) == "student":
        st = (await db.execute(select(Student).where(Student.user_id == user.id))).scalars().first()
        if not st:
            raise HTTPException(status_code=400, detail="پروفایل دانشجو یافت نشد.")
        student_id = st.id
        if instance_id:
            inst = (await db.execute(select(ProcessInstance).where(ProcessInstance.id == instance_id))).scalars().first()
            if not inst or inst.student_id != student_id:
                raise HTTPException(status_code=403, detail="فرایند متعلق به شما نیست.")
    else:
        if instance_id:
            inst = (await db.execute(select(ProcessInstance).where(ProcessInstance.id == instance_id))).scalars().first()
            if inst:
                student_id = inst.student_id

    now = datetime.now(timezone.utc)
    fr = FormResponse(
        id=uuid.uuid4(),
        template_version_id=vid,
        assignment_id=aid,
        user_id=user.id,
        student_id=student_id,
        instance_id=instance_id,
        status="submitted" if body.submit else "draft",
        answers_json=dict(body.answers_json or {}),
        submitted_at=now if body.submit else None,
    )
    db.add(fr)
    await db.flush()

    # ثبت فایل‌های آپلودشده در جدول form_field_files
    for fname, fval in (body.answers_json or {}).items():
        if _is_file_descriptor(fval) and fval.get("url"):
            db.add(
                FormFieldFile(
                    id=uuid.uuid4(),
                    response_id=fr.id,
                    field_name=str(fname)[:120],
                    file_name=str(fval.get("file_name") or "")[:512],
                    url=str(fval.get("url"))[:1024],
                    mime_type=(fval.get("mime") or fval.get("mime_type") or None),
                    size=fval.get("size") if isinstance(fval.get("size"), int) else None,
                )
            )

    if body.submit and instance_id and a and a.assignment_type == "process":
        inst = (await db.execute(select(ProcessInstance).where(ProcessInstance.id == instance_id))).scalars().first()
        if inst:
            key = (a.context_key or "").strip() or str(a.id)[:8]
            merged = merge_dynamic_into_context(
                inst.context_data if isinstance(inst.context_data, dict) else {},
                key,
                dict(body.answers_json or {}),
            )
            inst.context_data = merged
            flag_modified(inst, "context_data")

    return {
        "id": str(fr.id),
        "status": fr.status,
        "missing": missing,
    }


@router.get("/responses")
async def list_responses(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*CAN_MANAGE)),
    instance_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(FormResponse).order_by(FormResponse.created_at.desc()).limit(limit)
    if instance_id:
        stmt = stmt.where(FormResponse.instance_id == uuid.UUID(instance_id))
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "responses": [
            {
                "id": str(r.id),
                "template_version_id": str(r.template_version_id),
                "student_id": str(r.student_id) if r.student_id else None,
                "instance_id": str(r.instance_id) if r.instance_id else None,
                "status": r.status,
                "answers_json": r.answers_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


# ─── File upload (multipart) ─────────────────────────────────────


@router.post("/responses/upload-file")
async def upload_response_file(
    field_name: str = Form(...),
    file: UploadFile = File(...),
    instance_id: Optional[str] = Form(None),
    template_version_id: Optional[str] = Form(None),
    assignment_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """آپلود multipart فایل یک فیلد فرم؛ توصیفگر فایل را برمی‌گرداند تا در answers قرار گیرد."""
    if not _FIELD_NAME_RE.match(field_name or ""):
        raise HTTPException(status_code=400, detail="نام فیلد نامعتبر است.")
    ct = file.content_type or ""
    if ct not in _ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="فرمت مجاز: تصویر یا PDF")
    body = await file.read()
    if len(body) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="حداکثر حجم ۲۵ مگابایت")

    # مالکیت نمونه برای دانشجو
    if instance_id:
        inst = (await db.execute(select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id)))).scalars().first()
        if inst:
            await _ensure_student_instance(db, user, inst)

    settings = get_settings()
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    bucket = instance_id or "standalone"
    safe_dir = upload_root / "dynamic_forms" / bucket
    safe_dir.mkdir(parents=True, exist_ok=True)
    ext = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(ct, "")
    fname = f"{field_name}_{uuid.uuid4().hex}{ext}"
    (safe_dir / fname).write_bytes(body)
    rel = f"/uploads/dynamic_forms/{bucket}/{fname}"
    return {
        "file_name": file.filename or fname,
        "size": len(body),
        "mime": ct,
        "mime_type": ct,
        "url": rel,
    }


# ─── Approvals ───────────────────────────────────────────────────


async def _get_response_or_404(db: AsyncSession, response_id: str) -> FormResponse:
    rid = uuid.UUID(response_id)
    r = (await db.execute(select(FormResponse).where(FormResponse.id == rid))).scalars().first()
    if not r:
        raise HTTPException(status_code=404, detail="پاسخ فرم یافت نشد.")
    return r


async def _record_approval_step(
    db: AsyncSession, resp: FormResponse, role: str, decision: str, user: User, comment: Optional[str]
) -> None:
    steps = (
        await db.execute(
            select(FormApprovalStep)
            .where(FormApprovalStep.response_id == resp.id)
            .order_by(FormApprovalStep.step_index.desc())
        )
    ).scalars().all()
    next_index = (steps[0].step_index + 1) if steps else 0
    db.add(
        FormApprovalStep(
            id=uuid.uuid4(),
            response_id=resp.id,
            step_index=next_index,
            required_role=role,
            status=decision,
            acted_by_id=user.id,
            acted_at=datetime.now(timezone.utc),
            comment=comment,
        )
    )


@router.post("/responses/{response_id}/approve")
async def approve_response(
    response_id: str,
    body: ResponseApproveBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*CAN_MANAGE)),
):
    resp = await _get_response_or_404(db, response_id)
    resp.status = "approved"
    resp.locked_at = datetime.now(timezone.utc)
    if body.field_status is not None:
        resp.field_status = body.field_status
        flag_modified(resp, "field_status")
    await _record_approval_step(db, resp, _norm_role(user.role), "approved", user, body.comment)
    await db.flush()
    return {"id": str(resp.id), "status": resp.status}


@router.post("/responses/{response_id}/reject")
async def reject_response(
    response_id: str,
    body: ResponseRejectBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*CAN_MANAGE)),
):
    resp = await _get_response_or_404(db, response_id)
    resp.status = "rejected"
    resp.locked_at = None
    if body.field_status is not None:
        resp.field_status = body.field_status
        flag_modified(resp, "field_status")
    if body.resubmit_fields is not None:
        resp.edit_unlocked_fields = list(body.resubmit_fields)
        flag_modified(resp, "edit_unlocked_fields")
    await _record_approval_step(db, resp, _norm_role(user.role), "rejected", user, body.comment)
    await db.flush()
    return {"id": str(resp.id), "status": resp.status, "resubmit_fields": resp.edit_unlocked_fields}


@router.post("/responses/{response_id}/unlock-fields")
async def unlock_response_fields(
    response_id: str,
    body: ResponseUnlockBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(*CAN_MANAGE)),
):
    resp = await _get_response_or_404(db, response_id)
    resp.edit_unlocked_fields = list(body.fields or [])
    resp.locked_at = None
    if resp.status == "approved":
        resp.status = "submitted"
    flag_modified(resp, "edit_unlocked_fields")
    await db.flush()
    return {"id": str(resp.id), "edit_unlocked_fields": resp.edit_unlocked_fields}


# ─── Portal nav (also under /api/panel for convenience) ───────────


nav_router = APIRouter(prefix="/api/panel", tags=["PortalNav"])


@nav_router.get("/portal-nav-dynamic")
async def get_portal_nav_dynamic(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """آیتم‌های منوی ذخیره‌شده برای نقش جاری + حالت ادغام."""
    role = _norm_role(user.role)
    row = (await db.execute(select(PortalNavConfig).where(PortalNavConfig.role == role))).scalars().first()
    if not row:
        return {"role": role, "items": [], "merge_mode": "append"}
    return {"role": role, "items": row.items_json or [], "merge_mode": row.merge_mode or "append"}


@nav_router.put("/portal-nav-dynamic/{role}")
async def put_portal_nav_dynamic(
    role: str,
    body: PortalNavPut,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(*CAN_MANAGE)),
):
    rkey = role.strip().lower()
    row = (await db.execute(select(PortalNavConfig).where(PortalNavConfig.role == rkey))).scalars().first()
    if row:
        row.items_json = body.items_json
        row.merge_mode = body.merge_mode
    else:
        row = PortalNavConfig(
            id=uuid.uuid4(),
            role=rkey,
            items_json=body.items_json,
            merge_mode=body.merge_mode,
        )
        db.add(row)
    await db.flush()
    return {"ok": True}
