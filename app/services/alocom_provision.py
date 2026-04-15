"""Provision Alocom online class + persist link on TherapySession."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.config import get_settings
from app.models.operational_models import Student, TherapySession, User
from app.services.alocom_client import (
    AlocomAPIError,
    AlocomClient,
    _extract_event_id_and_link,
    _extract_register_link,
    extract_agent_user_id,
)

logger = logging.getLogger(__name__)


def _slug_part(text: str, max_len: int = 24) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s, flags=re.I)
    s = re.sub(r"-+", "-", s).strip("-")
    return (s[:max_len] if s else "session")


def build_event_slug(student_code: str, session_id: uuid.UUID) -> str:
    base = _slug_part(student_code or "st", 20)
    tail = session_id.hex[:10]
    return f"{base}-{tail}"


def _split_name(user: User) -> tuple[str, str]:
    fa = (user.full_name_fa or user.username or "user").strip()
    parts = fa.split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return fa[:40] or "user", "-"


async def _ensure_alocom_user_id(
    db: AsyncSession,
    client: AlocomClient,
    user: User,
) -> Optional[int]:
    if getattr(user, "alocom_agent_user_id", None):
        return int(user.alocom_agent_user_id)
    name, surname = _split_name(user)
    username = f"anistito_u_{user.id.hex[:20]}"
    try:
        resp = await client.create_agent_user(
            name=name,
            surname=surname,
            username=username,
            status=1,
            cellphone=user.phone,
            email=user.email,
        )
    except AlocomAPIError as e:
        logger.warning("Alocom create user failed for %s: %s", user.id, e)
        return None
    uid = extract_agent_user_id(resp)
    if uid is None:
        logger.warning("Alocom create user response had no id: %s", resp)
        return None
    user.alocom_agent_user_id = uid
    await db.flush()
    return uid


async def provision_therapy_session_alocom(
    db: AsyncSession,
    *,
    session: TherapySession,
    agent_service_id: int,
    title: str,
    duration_minutes: Optional[int] = None,
    start_by_admin: int = 1,
    fetch_student_event_link: bool = True,
) -> dict[str, Any]:
    """Create Alocom event, set session.meeting_url / alocom_event_id / links_unlocked."""
    settings = get_settings()
    if not settings.ALOCOM_ENABLED:
        raise AlocomAPIError("Alocom integration is disabled (ALOCOM_ENABLED=false)")

    st_r = await db.execute(select(Student).where(Student.id == session.student_id))
    student = st_r.scalars().first()
    if not student:
        raise AlocomAPIError("Student not found for session")

    su_r = await db.execute(select(User).where(User.id == student.user_id))
    student_user = su_r.scalars().first()
    if not student_user:
        raise AlocomAPIError("Student user not found")

    therapist_user: Optional[User] = None
    if session.therapist_id:
        tu_r = await db.execute(select(User).where(User.id == session.therapist_id))
        therapist_user = tu_r.scalars().first()

    client = AlocomClient(settings)
    su_alocom = await _ensure_alocom_user_id(db, client, student_user)
    users_payload: list[dict[str, Any]] = []
    if su_alocom is not None:
        users_payload.append({"userid": su_alocom, "role": "participant"})
    if therapist_user:
        th_alocom = await _ensure_alocom_user_id(db, client, therapist_user)
        if th_alocom is not None:
            users_payload.append({"userid": th_alocom, "role": "teacher"})

    slug = build_event_slug(student.student_code, session.id)
    try:
        raw = await client.create_event(
            title=title,
            agent_service_id=agent_service_id,
            slug=slug,
            start_by_admin=start_by_admin,
            status=1,
            duration_time=duration_minutes,
            users=users_payload or None,
        )
    except AlocomAPIError:
        raise

    eid, link = _extract_event_id_and_link(raw)
    if not link and eid:
        logger.info("Create event response had no alocom_link; event_id=%s keys=%s", eid, list(raw.keys()))

    meeting_url = link
    if fetch_student_event_link and eid and student_user:
        name, surname = _split_name(student_user)
        uname = f"anistito_u_{student_user.id.hex[:20]}"
        try:
            reg = await client.register_user_in_event(
                eid,
                name=name,
                surname=surname,
                username=uname,
                role="participant",
            )
            direct = _extract_register_link(reg)
            if direct:
                meeting_url = direct
        except AlocomAPIError as reg_err:
            logger.warning("Alocom register-user failed (using class link if any): %s", reg_err)

    if not meeting_url:
        meeting_url = link
    if not meeting_url:
        raise AlocomAPIError("Alocom did not return a meeting link", body=raw)

    session.meeting_url = meeting_url
    session.meeting_provider = "alocom"
    session.links_unlocked = True
    if eid:
        session.alocom_event_id = eid
    if session.session_starts_at is None:
        session.session_starts_at = datetime.combine(
            session.session_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

    await db.flush()
    return {
        "alocom_event_id": eid,
        "meeting_url": meeting_url,
        "slug": slug,
        "raw_keys": list(raw.keys()) if isinstance(raw, dict) else [],
    }
