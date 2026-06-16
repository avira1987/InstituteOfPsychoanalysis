"""Provision Alocom online class for interview slots."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.operational_models import InterviewSlot, Student, User
from app.services.alocom_client import AlocomAPIError, AlocomClient, _extract_event_id_and_link, _extract_register_link
from app.services.alocom_provision import _link_has_join_token, _normalize_cellphone, _split_name

logger = logging.getLogger(__name__)


def build_interview_event_slug(student_code: str, slot_id: uuid.UUID) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (student_code or "st").lower(), flags=re.I).strip("-")[:20] or "interview"
    return f"{base}-iv-{slot_id.hex[:10]}"


def build_interview_alocom_title(student_code: str, slot_id: uuid.UUID) -> str:
    """عنوان یکتا برای الوکام — API روی عنوان تکراری ۴۲۲ برمی‌گرداند."""
    code = (student_code or "student").strip()[:40] or "student"
    return f"مصاحبه پذیرش {code} {slot_id.hex[:8]}"[:500]


async def _create_interview_alocom_event(
    client: AlocomClient,
    *,
    title: str,
    agent_service_id: int,
    base_slug: str,
) -> tuple[dict, str]:
    """رویداد مصاحبه را بدون users بسازد (مطابق probe موفق الوکام). روی slug/عنوان تکراری دوباره تلاش می‌کند."""
    last_err: Optional[AlocomAPIError] = None
    for attempt in range(5):
        slug = base_slug if attempt == 0 else f"{base_slug}-r{uuid.uuid4().hex[:6]}"
        event_title = title if attempt == 0 else f"{title[:420]} {uuid.uuid4().hex[:6]}"
        try:
            raw = await client.create_event(
                title=event_title,
                agent_service_id=agent_service_id,
                slug=slug,
                start_by_admin=0,
                status=1,
                users=None,
                guest_access=True,
            )
            return raw, slug
        except AlocomAPIError as e:
            last_err = e
            if e.status_code != 422:
                raise
            logger.warning(
                "Alocom create_event 422 slug=%s title=%s body=%s",
                slug,
                event_title,
                getattr(e, "body", None),
            )
    if last_err is not None:
        raise last_err
    raise AlocomAPIError("Alocom create_event failed after retries")


async def _register_event_role_link(
    client: AlocomClient,
    event_id: str,
    *,
    user: User,
    role: str,
) -> Optional[str]:
    name, surname = _split_name(user)
    uname = f"anistito_u_{user.id.hex[:20]}"
    try:
        reg = await client.register_user_in_event(
            event_id,
            name=name,
            surname=surname,
            username=uname,
            role=role,
            cellphone=_normalize_cellphone(user.phone),
        )
        return _extract_register_link(reg)
    except AlocomAPIError as reg_err:
        logger.warning(
            "Alocom register-user role=%s user=%s event=%s: %s body=%s",
            role,
            user.id,
            event_id,
            reg_err,
            getattr(reg_err, "body", None),
        )
        return None


async def _persist_interview_slot_links(
    db: AsyncSession,
    slot: InterviewSlot,
    *,
    event_id: Optional[str],
    meeting_link: str,
    host_link: Optional[str],
    interviewer_link: Optional[str],
) -> None:
    slot.meeting_link = meeting_link
    slot.host_meeting_link = host_link or meeting_link
    slot.interviewer_meeting_link = interviewer_link
    slot.alocom_event_id = event_id
    await db.flush()


async def _build_links_for_event(
    client: AlocomClient,
    *,
    event_id: str,
    default_link: Optional[str],
    student_user: User,
    interviewer_user: Optional[User],
    fetch_student_event_link: bool,
) -> tuple[str, Optional[str], Optional[str]]:
    host_link = (default_link or "").strip() or None
    interviewer_meeting_link: Optional[str] = None
    meeting_link: Optional[str] = None

    if interviewer_user:
        interviewer_meeting_link = await _register_event_role_link(
            client, event_id, user=interviewer_user, role="teacher"
        )
        if interviewer_meeting_link:
            host_link = interviewer_meeting_link

    if fetch_student_event_link:
        direct = await _register_event_role_link(client, event_id, user=student_user, role="participant")
        if direct:
            meeting_link = direct

    if not meeting_link:
        meeting_link = host_link or default_link

    if fetch_student_event_link and not _link_has_join_token(meeting_link):
        raise AlocomAPIError(
            f"Alocom participant link missing join token for event_id={event_id}",
            body={"default_link": default_link, "host_link": host_link},
        )

    if not meeting_link:
        raise AlocomAPIError(f"Alocom did not return an interview meeting link for event_id={event_id}")

    if interviewer_user and not interviewer_meeting_link:
        interviewer_meeting_link = host_link or default_link

    return meeting_link, host_link or meeting_link, interviewer_meeting_link


async def provision_interview_slot_alocom(
    db: AsyncSession,
    *,
    slot: InterviewSlot,
    agent_service_id: int,
    title: str,
    fetch_student_event_link: bool = True,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ALOCOM_ENABLED:
        raise AlocomAPIError("Alocom integration is disabled (ALOCOM_ENABLED=false)")
    if slot.mode != "online":
        raise AlocomAPIError("Interview slot mode is not online")
    if not slot.assigned_student_id:
        raise AlocomAPIError("Interview slot has no assigned student")

    st_r = await db.execute(select(Student).where(Student.id == slot.assigned_student_id))
    student = st_r.scalars().first()
    if not student:
        raise AlocomAPIError("Student not found for interview slot")

    su_r = await db.execute(select(User).where(User.id == student.user_id))
    student_user = su_r.scalars().first()
    if not student_user:
        raise AlocomAPIError("Student user not found")

    interviewer_user: Optional[User] = None
    if slot.interviewer_user_id:
        iu_r = await db.execute(select(User).where(User.id == slot.interviewer_user_id))
        interviewer_user = iu_r.scalars().first()

    client = AlocomClient(settings)
    base_slug = build_interview_event_slug(student.student_code, slot.id)

    existing_event_id = (getattr(slot, "alocom_event_id", None) or "").strip()
    if existing_event_id:
        meeting_link, host_link, interviewer_link = await _build_links_for_event(
            client,
            event_id=existing_event_id,
            default_link=None,
            student_user=student_user,
            interviewer_user=interviewer_user,
            fetch_student_event_link=fetch_student_event_link,
        )
        await _persist_interview_slot_links(
            db,
            slot,
            event_id=existing_event_id,
            meeting_link=meeting_link,
            host_link=host_link,
            interviewer_link=interviewer_link,
        )
        return {
            "alocom_event_id": existing_event_id,
            "meeting_link": meeting_link,
            "host_meeting_link": slot.host_meeting_link,
            "interviewer_meeting_link": interviewer_link,
            "slug": base_slug,
            "recovered_existing_event": True,
        }

    raw, slug = await _create_interview_alocom_event(
        client,
        title=title,
        agent_service_id=agent_service_id,
        base_slug=base_slug,
    )
    eid, link = _extract_event_id_and_link(raw)
    if not eid:
        raise AlocomAPIError("Alocom create event did not return event id", body=raw)
    if not link:
        logger.info("Create interview event had no alocom_link; event_id=%s keys=%s", eid, list(raw.keys()))

    meeting_link, host_link, interviewer_link = await _build_links_for_event(
        client,
        event_id=eid,
        default_link=link,
        student_user=student_user,
        interviewer_user=interviewer_user,
        fetch_student_event_link=fetch_student_event_link,
    )
    await _persist_interview_slot_links(
        db,
        slot,
        event_id=eid,
        meeting_link=meeting_link,
        host_link=host_link,
        interviewer_link=interviewer_link,
    )
    return {
        "alocom_event_id": eid,
        "meeting_link": meeting_link,
        "host_meeting_link": slot.host_meeting_link,
        "interviewer_meeting_link": interviewer_link,
        "slug": slug,
        "raw_keys": list(raw.keys()) if isinstance(raw, dict) else [],
    }


async def refresh_interview_slot_alocom_links(
    db: AsyncSession,
    slot: InterviewSlot,
) -> bool:
    """برای رویداد موجود، لینک‌های توکن‌دار نقش‌ها را دوباره می‌گیرد."""
    eid = (getattr(slot, "alocom_event_id", None) or "").strip()
    if not eid or slot.mode != "online" or not slot.assigned_student_id:
        return bool((slot.meeting_link or "").strip())

    student_ok = _link_has_join_token(slot.meeting_link)
    iv_ok = _link_has_join_token(getattr(slot, "interviewer_meeting_link", None))
    if student_ok and (iv_ok or not slot.interviewer_user_id):
        return True

    st_r = await db.execute(select(Student).where(Student.id == slot.assigned_student_id))
    student = st_r.scalars().first()
    if not student:
        return student_ok
    su_r = await db.execute(select(User).where(User.id == student.user_id))
    student_user = su_r.scalars().first()
    if not student_user:
        return student_ok

    interviewer_user: Optional[User] = None
    if slot.interviewer_user_id:
        iu_r = await db.execute(select(User).where(User.id == slot.interviewer_user_id))
        interviewer_user = iu_r.scalars().first()

    client = AlocomClient(get_settings())
    default_link = (
        (getattr(slot, "host_meeting_link", None) or "").strip()
        or (slot.meeting_link or "").strip()
        or None
    )
    try:
        meeting_link, host_link, interviewer_link = await _build_links_for_event(
            client,
            event_id=eid,
            default_link=default_link,
            student_user=student_user,
            interviewer_user=interviewer_user,
            fetch_student_event_link=not student_ok,
        )
    except AlocomAPIError as e:
        logger.warning("refresh_interview_slot_alocom_links failed slot=%s: %s", slot.id, e)
        return student_ok

    if not student_ok:
        slot.meeting_link = meeting_link
    if interviewer_user and not iv_ok and interviewer_link:
        slot.interviewer_meeting_link = interviewer_link
    if host_link:
        slot.host_meeting_link = host_link
    await db.flush()
    return _link_has_join_token(slot.meeting_link)


async def ensure_interview_slot_host_meeting_link(
    db: AsyncSession,
    slot: InterviewSlot,
    *,
    viewer: Optional[User] = None,
) -> bool:
    """لینک‌های teacher/host قدیمی را در صورت نبود، از الوکام بازیابی می‌کند."""
    del viewer  # reserved for future per-viewer teacher links
    host_ok = bool((getattr(slot, "host_meeting_link", None) or "").strip())
    iv_ok = bool((getattr(slot, "interviewer_meeting_link", None) or "").strip())
    student_link = (slot.meeting_link or "").strip()
    host_distinct = host_ok and (slot.host_meeting_link or "").strip() != student_link
    if host_distinct and (iv_ok or not slot.interviewer_user_id):
        return True
    if iv_ok and not slot.interviewer_user_id:
        return True
    if not (slot.alocom_event_id or "").strip():
        return bool(student_link)

    settings = get_settings()
    if not settings.ALOCOM_ENABLED:
        return False

    if not slot.interviewer_user_id or iv_ok:
        return bool(host_ok or iv_ok or student_link)

    iu_r = await db.execute(select(User).where(User.id == slot.interviewer_user_id))
    interviewer_user = iu_r.scalars().first()
    if not interviewer_user:
        return bool(host_ok or student_link)

    client = AlocomClient(settings)
    teacher_direct = await _register_event_role_link(
        client,
        slot.alocom_event_id,
        user=interviewer_user,
        role="teacher",
    )
    if teacher_direct:
        slot.interviewer_meeting_link = teacher_direct
        if not host_ok:
            slot.host_meeting_link = teacher_direct
        await db.flush()
        return True
    return bool(host_ok or student_link)
