"""API تیکتینگ داخلی برای کارکنان (ارجاع درخواست به فرد دارای دسترسی)."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.operational_models import User, Student, ProcessInstance, SupportTicket, TicketComment

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])

STATUS_LABELS_FA = {
    "open": "باز",
    "in_progress": "در حال رسیدگی",
    "resolved": "رفع‌شده",
    "closed": "بسته",
}
PRIORITY_LABELS_FA = {"low": "کم", "normal": "عادی", "high": "بالا"}

VALID_STATUSES = frozenset({"open", "in_progress", "resolved", "closed"})
VALID_PRIORITIES = frozenset({"low", "normal", "high"})
VALID_CATEGORIES = frozenset({
    "profile_edit_unlock",
    "process_general",
    "data_correction",
    "access_request",
    "other",
})


def _is_admin(u: User) -> bool:
    return u.role == "admin"


def _can_access_ticket(ticket: SupportTicket, u: User) -> bool:
    if _is_admin(u):
        return True
    return ticket.requester_id == u.id or ticket.assignee_id == u.id


async def _student_profile_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[uuid.UUID]:
    r = await db.execute(select(Student.id).where(Student.user_id == user_id))
    row = r.first()
    return row[0] if row else None


def _display_name(u: Optional[User]) -> str:
    if not u:
        return "—"
    return (u.full_name_fa or u.username or "").strip() or u.username


async def resolve_triage_assignee(db: AsyncSession) -> User:
    """یک مسئول واحد: از TICKET_TRIAGE_USERNAME یا اولین staff فعال یا اولین admin."""
    settings = get_settings()
    uname = (settings.TICKET_TRIAGE_USERNAME or "").strip()
    if uname:
        r = await db.execute(select(User).where(User.username == uname, User.is_active.is_(True)))
        u = r.scalars().first()
        if u and u.role != "student":
            return u
    r = await db.execute(
        select(User).where(User.role == "staff", User.is_active.is_(True)).order_by(User.created_at.asc())
    )
    u = r.scalars().first()
    if u:
        return u
    r = await db.execute(
        select(User).where(User.role == "admin", User.is_active.is_(True)).order_by(User.created_at.asc())
    )
    u = r.scalars().first()
    if u:
        return u
    raise HTTPException(
        status_code=503,
        detail="مسئول واحد تیکت تعریف نشده. در .env مقدار TICKET_TRIAGE_USERNAME را بگذارید یا حداقل یک کاربر staff فعال داشته باشید.",
    )


async def _append_system_comment(db: AsyncSession, ticket_id: uuid.UUID, body: str) -> None:
    db.add(
        TicketComment(
            id=uuid.uuid4(),
            ticket_id=ticket_id,
            author_id=None,
            kind="system",
            body=body,
        )
    )


def _user_brief(u: Optional[User]) -> Optional[dict[str, Any]]:
    if u is None:
        return None
    return {
        "id": str(u.id),
        "username": u.username,
        "full_name_fa": u.full_name_fa,
        "role": u.role,
    }


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    category: str = "other"
    priority: str = "normal"
    # فقط مدیر: ارجاع مستقیم؛ بقیه به مسئول واحد (triage) می‌رود
    assignee_id: Optional[str] = Field(None, description="اختیاری؛ فقط با نقش admin")
    student_id: Optional[str] = None
    process_instance_id: Optional[str] = None
    extra_context: Optional[dict[str, Any]] = None


class TicketPatch(BaseModel):
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    priority: Optional[str] = None


class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=8000)


def _ticket_dict(
    ticket: SupportTicket,
    requester: Optional[User] = None,
    assignee: Optional[User] = None,
    student_code: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "id": str(ticket.id),
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "status": ticket.status,
        "priority": ticket.priority,
        "requester": _user_brief(requester or ticket.requester),
        "assignee": _user_brief(assignee if assignee is not None else ticket.assignee),
        "student_id": str(ticket.student_id) if ticket.student_id else None,
        "student_code": student_code,
        "process_instance_id": str(ticket.process_instance_id) if ticket.process_instance_id else None,
        "extra_context": ticket.extra_context,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
    }


def _comment_dict(c: TicketComment, author: Optional[User]) -> dict[str, Any]:
    k = getattr(c, "kind", None) or "user"
    return {
        "id": str(c.id),
        "kind": k,
        "body": c.body,
        "author": _user_brief(author),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/triage")
async def get_triage_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """مسئول اولیهٔ واحد که تیکت‌ها به او می‌رسد و می‌تواند به دیگران ارجاع دهد."""
    u = await resolve_triage_assignee(db)
    return {
        "primary_handler": {
            "id": str(u.id),
            "username": u.username,
            "full_name_fa": u.full_name_fa,
            "role": u.role,
        },
        "hint_fa": "همهٔ تیکت‌های جدید ابتدا به این همکار ارجاع می‌شود؛ ایشان می‌تواند در صورت نیاز تیک را به فرد دارای دسترسی بسپارد.",
    }


@router.get("/assignable-users")
async def list_assignable_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فهرست کاربران غیردانشجو برای انتخاب به‌عنوان مسئول تیکت."""
    stmt = (
        select(User)
        .where(User.is_active.is_(True), User.role != "student")
        .order_by(User.username.asc())
    )
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "full_name_fa": u.full_name_fa,
            "role": u.role,
        }
        for u in users
    ]


@router.get("")
async def list_tickets(
    status_filter: Optional[str] = Query(None, alias="status"),
    mine: Optional[str] = Query(None, description="assigned | created | all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(SupportTicket).options(
        selectinload(SupportTicket.requester),
        selectinload(SupportTicket.assignee),
    )
    if not _is_admin(current_user):
        m = (mine or "all").lower()
        if m == "assigned":
            stmt = stmt.where(SupportTicket.assignee_id == current_user.id)
        elif m == "created":
            stmt = stmt.where(SupportTicket.requester_id == current_user.id)
        else:
            stmt = stmt.where(
                or_(
                    SupportTicket.requester_id == current_user.id,
                    SupportTicket.assignee_id == current_user.id,
                )
            )
    if status_filter:
        if status_filter not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="وضعیت نامعتبر")
        stmt = stmt.where(SupportTicket.status == status_filter)
    stmt = stmt.order_by(SupportTicket.updated_at.desc())
    result = await db.execute(stmt)
    rows = result.scalars().unique().all()

    student_ids = {t.student_id for t in rows if t.student_id}
    codes: dict[uuid.UUID, str] = {}
    if student_ids:
        sr = await db.execute(select(Student.id, Student.student_code).where(Student.id.in_(student_ids)))
        for sid, code in sr.all():
            codes[sid] = code

    return [
        _ticket_dict(
            t,
            requester=t.requester,
            assignee=t.assignee,
            student_code=codes.get(t.student_id) if t.student_id else None,
        )
        for t in rows
    ]


@router.post("", status_code=201)
async def create_ticket(
    body: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="دستهٔ درخواست نامعتبر")
    if body.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="اولویت نامعتبر")

    assignee_uuid: uuid.UUID
    direct_assign = bool(body.assignee_id and str(body.assignee_id).strip()) and _is_admin(current_user)
    if direct_assign:
        try:
            assignee_uuid = uuid.UUID(str(body.assignee_id).strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="شناسهٔ مسئول نامعتبر است")
        ar = await db.execute(select(User).where(User.id == assignee_uuid, User.is_active.is_(True)))
        assignee = ar.scalars().first()
        if not assignee or assignee.role == "student":
            raise HTTPException(status_code=400, detail="مسئول انتخاب‌شده معتبر نیست یا دانشجو است")
    else:
        triage = await resolve_triage_assignee(db)
        assignee_uuid = triage.id

    student_uuid: Optional[uuid.UUID] = None
    proc_uuid: Optional[uuid.UUID] = None

    if current_user.role == "student":
        sid = await _student_profile_id(db, current_user.id)
        if not sid:
            raise HTTPException(status_code=400, detail="پروفایل دانشجو یافت نشد؛ با پشتیبانی تماس بگیرید")
        student_uuid = sid
        if body.student_id and str(body.student_id).strip():
            try:
                claimed = uuid.UUID(str(body.student_id).strip())
            except ValueError:
                raise HTTPException(status_code=400, detail="شناسهٔ دانشجو نامعتبر است")
            if claimed != student_uuid:
                raise HTTPException(status_code=400, detail="فقط می‌توانید درخواست مربوط به خودتان ثبت کنید")
        if body.process_instance_id and str(body.process_instance_id).strip():
            try:
                proc_uuid = uuid.UUID(str(body.process_instance_id).strip())
            except ValueError:
                raise HTTPException(status_code=400, detail="شناسهٔ نمونهٔ فرایند نامعتبر است")
            pr = await db.execute(select(ProcessInstance).where(ProcessInstance.id == proc_uuid))
            pi = pr.scalars().first()
            if not pi:
                raise HTTPException(status_code=400, detail="نمونهٔ فرایند یافت نشد")
            if pi.student_id != student_uuid:
                raise HTTPException(status_code=400, detail="این نمونهٔ فرایند متعلق به شما نیست")
    else:
        if body.student_id and str(body.student_id).strip():
            try:
                student_uuid = uuid.UUID(str(body.student_id).strip())
            except ValueError:
                raise HTTPException(status_code=400, detail="شناسهٔ دانشجو نامعتبر است")
            sr = await db.execute(select(Student).where(Student.id == student_uuid))
            if not sr.scalars().first():
                raise HTTPException(status_code=400, detail="دانشجو یافت نشد")

        if body.process_instance_id and str(body.process_instance_id).strip():
            try:
                proc_uuid = uuid.UUID(str(body.process_instance_id).strip())
            except ValueError:
                raise HTTPException(status_code=400, detail="شناسهٔ نمونهٔ فرایند نامعتبر است")
            pr = await db.execute(select(ProcessInstance).where(ProcessInstance.id == proc_uuid))
            pi = pr.scalars().first()
            if not pi:
                raise HTTPException(status_code=400, detail="نمونهٔ فرایند یافت نشد")
            if student_uuid and pi.student_id != student_uuid:
                raise HTTPException(status_code=400, detail="نمونهٔ فرایند با دانشجوی انتخاب‌شده هم‌خوان نیست")

    now = datetime.now(timezone.utc)
    ticket = SupportTicket(
        id=uuid.uuid4(),
        title=body.title.strip(),
        description=body.description,
        category=body.category,
        status="open",
        priority=body.priority,
        requester_id=current_user.id,
        assignee_id=assignee_uuid,
        student_id=student_uuid,
        process_instance_id=proc_uuid,
        extra_context=body.extra_context,
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket, ["requester", "assignee"])

    rq = ticket.requester
    asg = ticket.assignee
    req_name = _display_name(rq)
    asg_name = _display_name(asg)
    log_line = (
        f"تیکت ثبت شد. ثبت‌کننده: {req_name} — مسئول فعلی: {asg_name}."
        + (" (ارجاع مستقیم توسط مدیر)" if direct_assign else " تیکت در صف رسیدگی واحد است.")
    )
    await _append_system_comment(db, ticket.id, log_line)
    await db.flush()

    scode = None
    if ticket.student_id:
        scr = await db.execute(select(Student.student_code).where(Student.id == ticket.student_id))
        scode = scr.scalar_one_or_none()
    return _ticket_dict(ticket, student_code=scode)


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tid = uuid.UUID(ticket_id)
    result = await db.execute(
        select(SupportTicket)
        .where(SupportTicket.id == tid)
        .options(
            selectinload(SupportTicket.requester),
            selectinload(SupportTicket.assignee),
        )
    )
    ticket = result.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")
    if not _can_access_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="دسترسی به این تیکت ندارید")

    scode = None
    if ticket.student_id:
        scr = await db.execute(select(Student.student_code).where(Student.id == ticket.student_id))
        scode = scr.scalar_one_or_none()

    cr = await db.execute(
        select(TicketComment, User)
        .outerjoin(User, TicketComment.author_id == User.id)
        .where(TicketComment.ticket_id == tid)
        .order_by(TicketComment.created_at.asc())
    )
    comments = [_comment_dict(c, u) for c, u in cr.all()]

    out = _ticket_dict(ticket, student_code=scode)
    out["comments"] = comments
    return out


@router.patch("/{ticket_id}")
async def patch_ticket(
    ticket_id: str,
    body: TicketPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tid = uuid.UUID(ticket_id)
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == tid))
    ticket = result.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")
    if not _can_access_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="دسترسی به این تیکت ندارید")

    old_status = ticket.status
    old_assignee_id = ticket.assignee_id
    old_assignee = None
    if old_assignee_id:
        ar0 = await db.execute(select(User).where(User.id == old_assignee_id))
        old_assignee = ar0.scalars().first()

    now = datetime.now(timezone.utc)

    if body.priority is not None:
        if body.priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=400, detail="اولویت نامعتبر")
        if not _is_admin(current_user) and ticket.requester_id != current_user.id:
            raise HTTPException(status_code=403, detail="تغییر اولویت فقط برای ثبت‌کننده یا مدیر مجاز است")
        if ticket.priority != body.priority:
            ticket.priority = body.priority
            actor_name = _display_name(current_user)
            await _append_system_comment(
                db,
                tid,
                f"اولویت توسط «{actor_name}» به «{PRIORITY_LABELS_FA.get(body.priority, body.priority)}» تغییر کرد.",
            )

    if body.assignee_id is not None:
        if current_user.role == "student":
            raise HTTPException(status_code=403, detail="دانشجو نمی‌تواند مسئول را تغییر دهد")
        if not (
            _is_admin(current_user)
            or ticket.requester_id == current_user.id
            or ticket.assignee_id == current_user.id
        ):
            raise HTTPException(
                status_code=403,
                detail="تغییر مسئول فقط برای مسئول فعلی، ثبت‌کننده (غیردانشجو) یا مدیر مجاز است",
            )
        new_aid = uuid.UUID(body.assignee_id)
        ar = await db.execute(select(User).where(User.id == new_aid, User.is_active.is_(True)))
        nu = ar.scalars().first()
        if not nu or nu.role == "student":
            raise HTTPException(status_code=400, detail="مسئول جدید معتبر نیست")
        if new_aid != old_assignee_id:
            from_name = _display_name(old_assignee)
            to_name = _display_name(nu)
            actor_name = _display_name(current_user)
            ticket.assignee_id = new_aid
            await _append_system_comment(
                db,
                tid,
                f"ارجاع توسط «{actor_name}»: مسئول از «{from_name}» به «{to_name}» تغییر کرد.",
            )

    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="وضعیت نامعتبر")
        allowed = _is_admin(current_user)
        if ticket.assignee_id == current_user.id:
            allowed = True
        if ticket.requester_id == current_user.id and body.status in ("closed", "resolved"):
            allowed = True
        if not allowed:
            raise HTTPException(status_code=403, detail="تغییر وضعیت مجاز نیست")
        if body.status != old_status:
            actor_name = _display_name(current_user)
            old_l = STATUS_LABELS_FA.get(old_status, old_status)
            new_l = STATUS_LABELS_FA.get(body.status, body.status)
            if body.status == "in_progress":
                tail = " تیکت در حال پیگیری توسط مسئول است."
            elif body.status in ("resolved", "closed"):
                tail = ""
            else:
                tail = " منتظر اقدام بعدی است."
            await _append_system_comment(
                db,
                tid,
                f"وضعیت توسط «{actor_name}» از «{old_l}» به «{new_l}» تغییر کرد.{tail}",
            )
        ticket.status = body.status
        if body.status == "closed":
            ticket.closed_at = now

    ticket.updated_at = now
    await db.flush()
    await db.refresh(ticket, ["requester", "assignee"])
    scode = None
    if ticket.student_id:
        scr = await db.execute(select(Student.student_code).where(Student.id == ticket.student_id))
        scode = scr.scalar_one_or_none()
    return _ticket_dict(ticket, student_code=scode)


@router.post("/{ticket_id}/comments", status_code=201)
async def add_comment(
    ticket_id: str,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tid = uuid.UUID(ticket_id)
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == tid))
    ticket = result.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="تیکت یافت نشد")
    if not _can_access_ticket(ticket, current_user):
        raise HTTPException(status_code=403, detail="دسترسی به این تیکت ندارید")

    comment = TicketComment(
        id=uuid.uuid4(),
        ticket_id=tid,
        author_id=current_user.id,
        kind="user",
        body=body.body.strip(),
    )
    db.add(comment)
    ticket.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _comment_dict(comment, current_user)
