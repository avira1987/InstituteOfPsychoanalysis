"""Admin CRUD API endpoints for managing processes, states, transitions, and rules."""

import json
import os
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user, require_role, get_password_hash
from app.models.operational_models import User, ProcessInstance
from app.models.meta_models import ProcessDefinition, StateDefinition, TransitionDefinition, RuleDefinition
from app.models.audit_models import AuditLog
from app.core.audit import AuditLogger
from app.services.process_title import find_process_by_normalized_title

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# تصویر فلوچارت در دیتابیس (حداکثر ~۵ مگابایت)
_MAX_FLOWCHART_BYTES = 5 * 1024 * 1024
_ALLOWED_FLOWCHART_MEDIA = frozenset(
    {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
)


# ─── Process CRUD Schemas ──────────────────────────────────────

class ProcessCreate(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    initial_state_code: str
    config: Optional[dict] = None
    source_text: Optional[str] = None


class ProcessUpdate(BaseModel):
    name_fa: Optional[str] = None
    name_en: Optional[str] = None
    description: Optional[str] = None
    initial_state_code: Optional[str] = None
    is_active: Optional[bool] = None
    config: Optional[dict] = None
    source_text: Optional[str] = None
    clear_flowchart: Optional[bool] = Field(
        None, description="اگر true باشد تصویر فلوچارت ذخیره‌شده حذف می‌شود"
    )


class ProcessResponse(BaseModel):
    id: str
    code: str
    name_fa: str
    name_en: Optional[str] = None
    description: Optional[str] = None
    version: int
    is_active: bool
    initial_state_code: str
    config: Optional[dict] = None
    sop_order: Optional[int] = Field(None, description="شمارهٔ مرحله در سند SOP (INDEX / یادداشت‌ها)")
    source_text: Optional[str] = None
    has_flowchart: bool = False


class SopDocUpsertResponse(BaseModel):
    mode: Literal["updated", "created"]
    process: ProcessResponse


# ─── State CRUD Schemas ────────────────────────────────────────

class StateCreate(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    state_type: str = "intermediate"
    assigned_role: Optional[str] = None
    sla_hours: Optional[int] = None
    on_sla_breach_event: Optional[str] = None
    metadata_: Optional[dict] = Field(None, alias="metadata")

    model_config = {"populate_by_name": True}


class StateUpdate(BaseModel):
    name_fa: Optional[str] = None
    name_en: Optional[str] = None
    state_type: Optional[str] = None
    assigned_role: Optional[str] = None
    sla_hours: Optional[int] = None
    on_sla_breach_event: Optional[str] = None


class StateResponse(BaseModel):
    id: str
    process_id: str
    code: str
    name_fa: str
    state_type: str
    assigned_role: Optional[str] = None
    sla_hours: Optional[int] = None


# ─── Transition CRUD Schemas ───────────────────────────────────

class TransitionCreate(BaseModel):
    from_state_code: str
    to_state_code: str
    trigger_event: str
    condition_rules: Optional[list[str]] = None
    required_role: Optional[str] = None
    actions: Optional[list[dict]] = None
    priority: int = 0
    description_fa: Optional[str] = None


class TransitionUpdate(BaseModel):
    from_state_code: Optional[str] = None
    to_state_code: Optional[str] = None
    trigger_event: Optional[str] = None
    condition_rules: Optional[list[str]] = None
    required_role: Optional[str] = None
    actions: Optional[list[dict]] = None
    priority: Optional[int] = None
    description_fa: Optional[str] = None


class TransitionResponse(BaseModel):
    id: str
    process_id: str
    from_state_code: str
    to_state_code: str
    trigger_event: str
    condition_rules: Optional[list[str]] = None
    required_role: Optional[str] = None
    actions: Optional[list[dict]] = None
    priority: int
    description_fa: Optional[str] = None


# ─── Rule CRUD Schemas ─────────────────────────────────────────

class RuleCreate(BaseModel):
    code: str
    name_fa: str
    name_en: Optional[str] = None
    rule_type: str = "condition"
    expression: dict
    parameters: Optional[dict] = None
    error_message_fa: Optional[str] = None


class RuleUpdate(BaseModel):
    name_fa: Optional[str] = None
    name_en: Optional[str] = None
    rule_type: Optional[str] = None
    expression: Optional[dict] = None
    parameters: Optional[dict] = None
    error_message_fa: Optional[str] = None
    is_active: Optional[bool] = None


class RuleResponse(BaseModel):
    id: str
    code: str
    name_fa: str
    rule_type: str
    expression: dict
    parameters: Optional[dict] = None
    error_message_fa: Optional[str] = None
    is_active: bool
    version: int


# ─── Process CRUD Endpoints ────────────────────────────────────

@router.post("/processes", response_model=ProcessResponse)
async def create_process(
    data: ProcessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Create a new process definition."""
    process = ProcessDefinition(
        id=uuid.uuid4(),
        code=data.code,
        name_fa=data.name_fa,
        name_en=data.name_en,
        description=data.description,
        initial_state_code=data.initial_state_code,
        config=data.config,
        source_text=data.source_text,
        updated_by=current_user.id,
    )
    db.add(process)
    await db.flush()
    return _process_response(process)


@router.post("/processes/sop-doc-upsert", response_model=SopDocUpsertResponse)
async def upsert_process_sop_doc(
    name_fa: str = Form(..., description="عنوان فرایند؛ تشخیص تکراری فقط با عنوان نرمال‌شده"),
    source_text: Optional[str] = Form(None, description="اگر ارسال شود، متن خام SOP به‌روز می‌شود (رشتهٔ خالی = پاک کردن)"),
    code: Optional[str] = Form(None, description="برای فرایند جدید الزامی است"),
    initial_state_code: Optional[str] = Form(None, description="برای فرایند جدید الزامی است"),
    name_en: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    sop_order: Optional[str] = Form(None, description="اعداد؛ در config ذخیره می‌شود"),
    file: Optional[UploadFile] = File(None, description="تصویر فلوچارت (فقط در صورت ارسال جایگزین می‌شود)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    اگر فرایندی با عنوان فارسی یکسان (پس از نرمال‌سازی) وجود داشته باشد: فقط `source_text` و در صورت ارسال، تصویر فلوچارت به‌روز می‌شود
    (state machine و کد فرایند تغییر نمی‌کند).

    اگر وجود نداشته باشد: فرایند جدید با `code` و `initial_state_code` ایجاد می‌شود؛ `sop_order` در `config` ذخیره می‌شود.
    """
    existing = await find_process_by_normalized_title(db, name_fa)

    if existing is not None:
        changed = False
        if source_text is not None:
            existing.source_text = source_text
            changed = True
        if file is not None:
            body = await file.read()
            if len(body) > _MAX_FLOWCHART_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail="حجم فایل بیش از حد مجاز است (حداکثر ۵ مگابایت)",
                )
            ct = (file.content_type or "").split(";")[0].strip().lower()
            if ct == "image/jpg":
                ct = "image/jpeg"
            if ct not in _ALLOWED_FLOWCHART_MEDIA:
                raise HTTPException(
                    status_code=400,
                    detail="نوع فایل مجاز نیست. فقط PNG، JPEG، GIF یا WebP.",
                )
            existing.flowchart_image = body
            existing.flowchart_content_type = ct
            changed = True
        if not changed:
            raise HTTPException(
                status_code=400,
                detail="برای به‌روزرسانی سند موجود، حداقل یکی از source_text یا فایل تصویر را ارسال کنید.",
            )
        existing.version += 1
        existing.updated_by = current_user.id
        audit = AuditLogger(db)
        await audit.log(
            action_type="process_updated",
            actor_id=current_user.id,
            actor_role=current_user.role,
            process_code=existing.code,
            details={"sop_doc_upsert": "updated", "title_match": name_fa[:200]},
        )
        await db.flush()
        return SopDocUpsertResponse(mode="updated", process=_process_response(existing))

    if not code or not str(code).strip():
        raise HTTPException(
            status_code=400,
            detail="برای فرایند جدید، فیلدهای code و initial_state_code الزامی است.",
        )
    if not initial_state_code or not str(initial_state_code).strip():
        raise HTTPException(
            status_code=400,
            detail="برای فرایند جدید، فیلدهای code و initial_state_code الزامی است.",
        )

    code_s = str(code).strip()
    initial_s = str(initial_state_code).strip()

    so: Optional[int] = None
    if sop_order is not None and str(sop_order).strip() != "":
        try:
            so = int(str(sop_order).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
        except ValueError:
            raise HTTPException(status_code=400, detail="sop_order باید عدد صحیح باشد")

    cfg: Optional[dict] = None
    if so is not None:
        cfg = {"sop_order": so}

    process = ProcessDefinition(
        id=uuid.uuid4(),
        code=code_s,
        name_fa=name_fa.strip(),
        name_en=name_en.strip() if name_en else None,
        description=description.strip() if description else None,
        initial_state_code=initial_s,
        config=cfg,
        source_text=source_text if source_text is not None else None,
        updated_by=current_user.id,
    )
    if file is not None:
        body = await file.read()
        if len(body) > _MAX_FLOWCHART_BYTES:
            raise HTTPException(
                status_code=413,
                detail="حجم فایل بیش از حد مجاز است (حداکثر ۵ مگابایت)",
            )
        ct = (file.content_type or "").split(";")[0].strip().lower()
        if ct == "image/jpg":
            ct = "image/jpeg"
        if ct not in _ALLOWED_FLOWCHART_MEDIA:
            raise HTTPException(
                status_code=400,
                detail="نوع فایل مجاز نیست. فقط PNG، JPEG، GIF یا WebP.",
            )
        process.flowchart_image = body
        process.flowchart_content_type = ct

    db.add(process)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="کد فرایند تکراری است یا تضاد یکتایی رخ داده است.",
        ) from None

    audit = AuditLogger(db)
    await audit.log(
        action_type="process_created",
        actor_id=current_user.id,
        actor_role=current_user.role,
        process_code=process.code,
        details={"sop_doc_upsert": "created", "sop_order": so},
    )
    await db.flush()
    return SopDocUpsertResponse(mode="created", process=_process_response(process))


@router.get("/processes", response_model=list[ProcessResponse])
async def list_processes(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all process definitions."""
    stmt = select(ProcessDefinition)
    if is_active is not None:
        stmt = stmt.where(ProcessDefinition.is_active == is_active)
    stmt = stmt.order_by(ProcessDefinition.code)
    result = await db.execute(stmt)
    processes = result.scalars().all()
    rows = [_process_response(p, include_source_text=False) for p in processes]

    def _proc_sort_key(r: ProcessResponse) -> tuple:
        s = r.sop_order
        return (s is None, s if s is not None else 10**9, r.code or "")

    return sorted(rows, key=_proc_sort_key)


@router.get("/processes/{process_id}", response_model=ProcessResponse)
async def get_process(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Get a process definition by ID."""
    process = await _get_process_or_404(db, process_id)
    return _process_response(process)


@router.get("/processes/{process_id}/flowchart")
async def get_process_flowchart(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """دانلود تصویر فلوچارت ذخیره‌شده (PNG/JPEG/GIF/WebP)."""
    process = await _get_process_or_404(db, process_id)
    data = process.flowchart_image
    if not data:
        raise HTTPException(status_code=404, detail="فلوچارتی ثبت نشده است")
    raw = bytes(data) if not isinstance(data, (bytes, bytearray)) else data
    ct = process.flowchart_content_type or "application/octet-stream"
    return Response(content=raw, media_type=ct)


@router.post("/processes/{process_id}/flowchart", response_model=ProcessResponse)
async def upload_process_flowchart(
    process_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """بارگذاری یا جایگزینی تصویر فلوچارت."""
    process = await _get_process_or_404(db, process_id)
    body = await file.read()
    if len(body) > _MAX_FLOWCHART_BYTES:
        raise HTTPException(status_code=413, detail="حجم فایل بیش از حد مجاز است (حداکثر ۵ مگابایت)")
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct == "image/jpg":
        ct = "image/jpeg"
    if ct not in _ALLOWED_FLOWCHART_MEDIA:
        raise HTTPException(
            status_code=400,
            detail="نوع فایل مجاز نیست. فقط PNG، JPEG، GIF یا WebP.",
        )
    process.flowchart_image = body
    process.flowchart_content_type = ct
    process.version += 1
    process.updated_by = current_user.id
    audit = AuditLogger(db)
    await audit.log(
        action_type="process_updated",
        actor_id=current_user.id,
        actor_role=current_user.role,
        process_code=process.code,
        details={"flowchart_uploaded": True, "bytes": len(body), "content_type": ct},
    )
    await db.flush()
    return _process_response(process)


@router.delete("/processes/{process_id}/flowchart", response_model=ProcessResponse)
async def delete_process_flowchart(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """حذف تصویر فلوچارت ذخیره‌شده."""
    process = await _get_process_or_404(db, process_id)
    process.flowchart_image = None
    process.flowchart_content_type = None
    process.version += 1
    process.updated_by = current_user.id
    audit = AuditLogger(db)
    await audit.log(
        action_type="process_updated",
        actor_id=current_user.id,
        actor_role=current_user.role,
        process_code=process.code,
        details={"flowchart_deleted": True},
    )
    await db.flush()
    return _process_response(process)


@router.patch("/processes/{process_id}", response_model=ProcessResponse)
async def update_process(
    process_id: str,
    data: ProcessUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a process definition."""
    process = await _get_process_or_404(db, process_id)
    raw = data.model_dump(exclude_unset=True)
    clear_fc = raw.pop("clear_flowchart", None)
    if clear_fc:
        process.flowchart_image = None
        process.flowchart_content_type = None
    audit_changes = dict(raw)
    if "source_text" in audit_changes and audit_changes["source_text"] is not None:
        st = audit_changes["source_text"]
        if isinstance(st, str):
            audit_changes["source_text"] = f"<{len(st)} chars>"
    for key, value in raw.items():
        if hasattr(process, key):
            setattr(process, key, value)
    process.version += 1
    process.updated_by = current_user.id

    # Audit
    audit = AuditLogger(db)
    await audit.log(
        action_type="process_updated",
        actor_id=current_user.id,
        actor_role=current_user.role,
        process_code=process.code,
        details={"changes": audit_changes, "cleared_flowchart": bool(clear_fc)},
    )
    await db.flush()
    return _process_response(process)


@router.delete("/processes/{process_id}")
async def delete_process(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete (deactivate) a process definition."""
    process = await _get_process_or_404(db, process_id)
    process.is_active = False
    await db.flush()
    return {"message": f"Process '{process.code}' deactivated"}


# ─── State CRUD Endpoints ──────────────────────────────────────

@router.post("/processes/{process_id}/states", response_model=StateResponse)
async def create_state(
    process_id: str,
    data: StateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Add a state to a process."""
    await _get_process_or_404(db, process_id)
    state = StateDefinition(
        id=uuid.uuid4(),
        process_id=uuid.UUID(process_id),
        code=data.code,
        name_fa=data.name_fa,
        name_en=data.name_en,
        state_type=data.state_type,
        assigned_role=data.assigned_role,
        sla_hours=data.sla_hours,
        on_sla_breach_event=data.on_sla_breach_event,
        metadata_=data.metadata_,
    )
    db.add(state)
    await db.flush()
    return _state_response(state)


@router.get("/processes/{process_id}/states", response_model=list[StateResponse])
async def list_states(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all states in a process."""
    stmt = select(StateDefinition).where(
        StateDefinition.process_id == uuid.UUID(process_id)
    )
    result = await db.execute(stmt)
    states = result.scalars().all()
    return [_state_response(s) for s in states]


@router.patch("/states/{state_id}", response_model=StateResponse)
async def update_state(
    state_id: str,
    data: StateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a state definition."""
    stmt = select(StateDefinition).where(StateDefinition.id == uuid.UUID(state_id))
    result = await db.execute(stmt)
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(state, key, value)
    await db.flush()
    return _state_response(state)


@router.delete("/states/{state_id}")
async def delete_state(
    state_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete a state definition."""
    stmt = select(StateDefinition).where(StateDefinition.id == uuid.UUID(state_id))
    result = await db.execute(stmt)
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    await db.delete(state)
    await db.flush()
    return {"message": "State deleted"}


# ─── Transition CRUD Endpoints ─────────────────────────────────

@router.post("/processes/{process_id}/transitions", response_model=TransitionResponse)
async def create_transition(
    process_id: str,
    data: TransitionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Add a transition to a process."""
    await _get_process_or_404(db, process_id)
    transition = TransitionDefinition(
        id=uuid.uuid4(),
        process_id=uuid.UUID(process_id),
        from_state_code=data.from_state_code,
        to_state_code=data.to_state_code,
        trigger_event=data.trigger_event,
        condition_rules=data.condition_rules,
        required_role=data.required_role,
        actions=data.actions,
        priority=data.priority,
        description_fa=data.description_fa,
    )
    db.add(transition)
    await db.flush()
    return _transition_response(transition)


@router.get("/processes/{process_id}/transitions", response_model=list[TransitionResponse])
async def list_transitions(
    process_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all transitions in a process."""
    stmt = select(TransitionDefinition).where(
        TransitionDefinition.process_id == uuid.UUID(process_id)
    )
    result = await db.execute(stmt)
    transitions = result.scalars().all()
    return [_transition_response(t) for t in transitions]


@router.patch("/transitions/{transition_id}", response_model=TransitionResponse)
async def update_transition(
    transition_id: str,
    data: TransitionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a transition definition."""
    stmt = select(TransitionDefinition).where(TransitionDefinition.id == uuid.UUID(transition_id))
    result = await db.execute(stmt)
    transition = result.scalars().first()
    if not transition:
        raise HTTPException(status_code=404, detail="Transition not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(transition, key, value)
    await db.flush()
    return _transition_response(transition)


@router.delete("/transitions/{transition_id}")
async def delete_transition(
    transition_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete a transition definition."""
    stmt = select(TransitionDefinition).where(TransitionDefinition.id == uuid.UUID(transition_id))
    result = await db.execute(stmt)
    transition = result.scalars().first()
    if not transition:
        raise HTTPException(status_code=404, detail="Transition not found")
    await db.delete(transition)
    await db.flush()
    return {"message": "Transition deleted"}


# ─── Rule CRUD Endpoints ───────────────────────────────────────

@router.post("/rules", response_model=RuleResponse)
async def create_rule(
    data: RuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Create a new rule definition."""
    rule = RuleDefinition(
        id=uuid.uuid4(),
        code=data.code,
        name_fa=data.name_fa,
        name_en=data.name_en,
        rule_type=data.rule_type,
        expression=data.expression,
        parameters=data.parameters,
        error_message_fa=data.error_message_fa,
    )
    db.add(rule)

    audit = AuditLogger(db)
    await audit.log_rule_change(
        rule_code=data.code,
        change_type="created",
        actor_id=current_user.id,
        actor_role=current_user.role,
        new_value=data.model_dump(),
    )
    await db.flush()
    return _rule_response(rule)


@router.get("/rules", response_model=list[RuleResponse])
async def list_rules(
    rule_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all rule definitions."""
    stmt = select(RuleDefinition)
    if rule_type:
        stmt = stmt.where(RuleDefinition.rule_type == rule_type)
    if is_active is not None:
        stmt = stmt.where(RuleDefinition.is_active == is_active)
    stmt = stmt.order_by(RuleDefinition.code)
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return [_rule_response(r) for r in rules]


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Get a rule definition by ID."""
    stmt = select(RuleDefinition).where(RuleDefinition.id == uuid.UUID(rule_id))
    result = await db.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _rule_response(rule)


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    data: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update a rule definition."""
    stmt = select(RuleDefinition).where(RuleDefinition.id == uuid.UUID(rule_id))
    result = await db.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    old_value = _rule_response(rule).model_dump() if hasattr(_rule_response(rule), 'model_dump') else {}
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    rule.version += 1

    audit = AuditLogger(db)
    await audit.log_rule_change(
        rule_code=rule.code,
        change_type="updated",
        actor_id=current_user.id,
        actor_role=current_user.role,
        old_value=old_value,
        new_value=data.model_dump(exclude_unset=True),
    )
    await db.flush()
    return _rule_response(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Deactivate a rule definition."""
    stmt = select(RuleDefinition).where(RuleDefinition.id == uuid.UUID(rule_id))
    result = await db.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = False
    await db.flush()
    return {"message": f"Rule '{rule.code}' deactivated"}


# ─── Audit Log Endpoints ───────────────────────────────────────

@router.get("/audit-logs")
async def list_audit_logs(
    action_type: Optional[str] = Query(None),
    process_code: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """List audit logs with filters."""
    stmt = select(AuditLog)
    if action_type:
        stmt = stmt.where(AuditLog.action_type == action_type)
    if process_code:
        stmt = stmt.where(AuditLog.process_code == process_code)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == uuid.UUID(actor_id))
    stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    logs = result.scalars().all()

    # Count total
    count_stmt = select(func.count(AuditLog.id))
    if action_type:
        count_stmt = count_stmt.where(AuditLog.action_type == action_type)
    if process_code:
        count_stmt = count_stmt.where(AuditLog.process_code == process_code)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": [
            {
                "id": str(log.id),
                "action_type": log.action_type,
                "process_code": log.process_code,
                "from_state": log.from_state,
                "to_state": log.to_state,
                "trigger_event": log.trigger_event,
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "actor_role": log.actor_role,
                "actor_name": log.actor_name,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ],
    }


# ─── Dashboard Stats ───────────────────────────────────────────

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Get dashboard statistics."""
    from app.models.operational_models import ProcessInstance, Student

    process_count = await db.execute(select(func.count(ProcessDefinition.id)).where(ProcessDefinition.is_active == True))
    rule_count = await db.execute(select(func.count(RuleDefinition.id)).where(RuleDefinition.is_active == True))
    student_count = await db.execute(select(func.count(Student.id)))
    active_instances = await db.execute(select(func.count(ProcessInstance.id)).where(ProcessInstance.is_completed == False, ProcessInstance.is_cancelled == False))

    return {
        "active_processes": process_count.scalar(),
        "active_rules": rule_count.scalar(),
        "total_students": student_count.scalar(),
        "active_instances": active_instances.scalar(),
    }


@router.post("/sync-metadata")
async def sync_metadata_from_json(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Sync rule and process definitions from metadata. Adds only missing items."""
    import json
    from pathlib import Path
    from app.meta.seed import load_process, sync_rules

    METADATA_DIR = Path(__file__).resolve().parents[2].parent / "metadata"
    PROCESSES_DIR = METADATA_DIR / "processes"
    if not PROCESSES_DIR.exists():
        raise HTTPException(status_code=500, detail="metadata/processes directory not found")

    # 1. Sync rules
    rules_added = await sync_rules(db)
    await db.commit()

    # 2. Sync processes
    result = await db.execute(select(ProcessDefinition.code))
    existing_codes = set(result.scalars().all())

    processes_added = 0
    for pf in sorted(PROCESSES_DIR.glob("*.json")):
        with open(pf, "r", encoding="utf-8") as f:
            data = json.load(f)
        code = data.get("process", {}).get("code")
        if not code or code in existing_codes:
            continue
        await load_process(db, pf)
        existing_codes.add(code)
        processes_added += 1

    await db.commit()
    msg = []
    if rules_added:
        msg.append(f"{rules_added} قانون")
    if processes_added:
        msg.append(f"{processes_added} فرایند")
    return {
        "added_rules": rules_added,
        "added_processes": processes_added,
        "message": f"اضافه شد: {', '.join(msg) or 'هیچ مورد جدیدی'}" if msg else "هیچ مورد جدیدی یافت نشد",
    }


class SeedDemoMatrixRequest(BaseModel):
    """همان منطق scripts/seed_demo_process_matrix.py — روی دیتابیس همین سرور (نه SQLite جدا روی میزبان)."""

    matrix: bool = True
    scenarios: bool = True
    profiles: bool = True
    force: bool = False


@router.post("/seed-demo-matrix")
async def seed_demo_matrix(
    body: SeedDemoMatrixRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    ایجاد کاربران/دانشجویان دمو (AUTO-DEMO-*, DEMO-SCEN-*, AUTO-PROFILE-*) در **همین** دیتابیسی که API به آن وصل است.
    اگر فقط اسکریپت را روی میزبان بدون DATABASE_URL مشابه Docker اجرا کرده‌اید، داده در SQLite محلی مانده و در پنل دیده نمی‌شود — از این endpoint یا docker exec استفاده کنید.
    """
    os.environ.setdefault("SMS_PROVIDER", "log")
    os.environ.setdefault("OTP_RESTRICT_TO_STUDENT_PHONES", "false")
    demo_pass = os.environ.get("DEMO_MATRIX_STUDENT_PASSWORD", "demo_student_123")

    from app.demo_process_walker import (
        delete_demo_seed_users,
        seed_branch_scenarios,
        seed_full_matrix,
        seed_profile_state_students,
    )

    out: dict = {"admin_login": {"username": "admin", "password": "admin123", "note": "password tab + math challenge"}}

    if body.force:
        prefixes: list[str] = []
        if body.matrix:
            prefixes.append("AUTO-DEMO-")
        if body.scenarios:
            prefixes.append("DEMO-SCEN-")
        if body.profiles:
            prefixes.append("AUTO-PROFILE-")
        if not prefixes:
            prefixes = ["AUTO-DEMO-", "DEMO-SCEN-", "AUTO-PROFILE-"]
        out["deleted_demo_rows"] = await delete_demo_seed_users(db, prefixes=tuple(prefixes))

    # سناریوها سبک‌ترند — اول تا در پنل سریع‌تر چیزی ببینید؛ ماتریس کامل بعداً (می‌تواند دقیقه‌ها طول بکشد)
    if body.scenarios:
        out["scenarios"] = await seed_branch_scenarios(db, None, None, demo_pass)
    if body.matrix:
        out["matrix"] = await seed_full_matrix(db, None, None, demo_pass)
    if body.profiles:
        out["profiles"] = await seed_profile_state_students(db, demo_pass)

    return out


# ─── User Management Endpoints ──────────────────────────────────

@router.get("/users")
async def list_users(
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """List all users (admin and staff; staff use this to set passwords for students)."""
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    stmt = stmt.order_by(User.created_at.desc())
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "full_name_fa": u.full_name_fa,
            "full_name_en": u.full_name_en,
            "role": u.role,
            "phone": u.phone,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "staff")),
):
    """Update a user. Admin can change any field; staff can only set password and edit name/email/phone."""
    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed_fields = {"full_name_fa", "full_name_en", "role", "phone", "email", "is_active"}
    if current_user.role == "staff":
        allowed_fields = {"full_name_fa", "full_name_en", "phone", "email"}
    for key, value in data.items():
        if key in allowed_fields:
            setattr(user, key, value)
    if "password" in data and data.get("password"):
        user.hashed_password = get_password_hash(data["password"])
    await db.flush()
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name_fa": user.full_name_fa,
        "full_name_en": user.full_name_en,
        "role": user.role,
        "phone": user.phone,
        "is_active": user.is_active,
    }


@router.post("/process-instances/{instance_id}/cancel")
async def cancel_process_instance(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """لغو نمونهٔ فرایند (مثلاً بستن ثبت‌نام اولیه برای ادامهٔ مسیر آزمایشی)."""
    stmt = select(ProcessInstance).where(ProcessInstance.id == uuid.UUID(instance_id))
    result = await db.execute(stmt)
    instance = result.scalars().first()
    if not instance:
        raise HTTPException(status_code=404, detail="Process instance not found")
    if instance.is_completed:
        raise HTTPException(status_code=400, detail="Instance already completed")
    if instance.is_cancelled:
        return {"ok": True, "instance_id": instance_id, "already_cancelled": True}
    instance.is_cancelled = True
    await db.flush()
    return {"ok": True, "instance_id": instance_id}


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Deactivate a user."""
    if str(current_user.id) == user_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    stmt = select(User).where(User.id == uuid.UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.flush()
    return {"message": f"User '{user.username}' deactivated"}


# ─── Test SMS (Dev) ───────────────────────────────────────────────

class TestSMSRequest(BaseModel):
    phone: str = Field(..., description="شماره موبایل (مثلاً 09123456789)")
    message: str = Field(..., description="متن پیامک")


@router.post("/test-sms", summary="تست ارسال پیامک")
async def test_sms(
    req: TestSMSRequest,
    current_user: User = Depends(require_role("admin")),
):
    """ارسال یک پیامک تستی برای اطمینان از عملکرد درگاه پیامکی."""
    from app.services.sms_gateway import send_sms
    result = await send_sms(req.phone, req.message)
    return {"success": result.get("success", False), "provider": result.get("provider", ""), "response": result}


# ─── Helper Functions ───────────────────────────────────────────

async def _get_process_or_404(db: AsyncSession, process_id: str) -> ProcessDefinition:
    stmt = select(ProcessDefinition).where(ProcessDefinition.id == uuid.UUID(process_id))
    result = await db.execute(stmt)
    process = result.scalars().first()
    if not process:
        raise HTTPException(status_code=404, detail="Process not found")
    return process


def _normalize_process_config(val) -> Optional[dict]:
    """ProcessDefinition.config is JSONB; legacy rows may store a JSON string — Pydantic expects dict."""
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _normalize_rule_json_dict(val) -> dict:
    """RuleDefinition.expression/parameters: JSONB may arrive as str — RuleResponse expects dict."""
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _normalize_rule_json_optional_dict(val) -> Optional[dict]:
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if parsed is None:
                return None
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _process_response(p: ProcessDefinition, *, include_source_text: bool = True) -> ProcessResponse:
    from app.meta.sop_registry import get_sop_order_for_process_code

    cfg = _normalize_process_config(p.config)
    co = cfg.get("sop_order") if isinstance(cfg, dict) else None
    sop_order = int(co) if isinstance(co, int) else get_sop_order_for_process_code(p.code)
    img = p.flowchart_image
    has_fc = bool(img) and (len(img) > 0 if hasattr(img, "__len__") else True)
    return ProcessResponse(
        id=str(p.id), code=p.code, name_fa=p.name_fa, name_en=p.name_en,
        description=p.description, version=p.version, is_active=p.is_active,
        initial_state_code=p.initial_state_code, config=cfg,
        sop_order=sop_order,
        source_text=(p.source_text if include_source_text else None),
        has_flowchart=has_fc,
    )


def _state_response(s: StateDefinition) -> StateResponse:
    return StateResponse(
        id=str(s.id), process_id=str(s.process_id), code=s.code,
        name_fa=s.name_fa, state_type=s.state_type, assigned_role=s.assigned_role,
        sla_hours=s.sla_hours,
    )


def _transition_response(t: TransitionDefinition) -> TransitionResponse:
    return TransitionResponse(
        id=str(t.id), process_id=str(t.process_id),
        from_state_code=t.from_state_code, to_state_code=t.to_state_code,
        trigger_event=t.trigger_event, condition_rules=t.condition_rules,
        required_role=t.required_role, actions=t.actions, priority=t.priority,
        description_fa=t.description_fa,
    )


def _rule_response(r: RuleDefinition) -> RuleResponse:
    return RuleResponse(
        id=str(r.id), code=r.code, name_fa=r.name_fa, rule_type=r.rule_type,
        expression=_normalize_rule_json_dict(r.expression),
        parameters=_normalize_rule_json_optional_dict(r.parameters),
        error_message_fa=r.error_message_fa, is_active=r.is_active, version=r.version,
    )
