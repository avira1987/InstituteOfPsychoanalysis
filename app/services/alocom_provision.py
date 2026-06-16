"""Provision Alocom online class + persist link on TherapySession."""

from __future__ import annotations

import logging
import re
import secrets
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


def is_alocom_configured(settings=None) -> tuple[bool, int]:
    """Whether Alocom API credentials and default agent service id are set."""
    settings = settings or get_settings()
    agent_service_id = int(getattr(settings, "ALOCOM_DEFAULT_AGENT_SERVICE_ID", 0) or 0)
    ready = (
        bool(settings.ALOCOM_ENABLED)
        and bool((settings.ALOCOM_USERNAME or "").strip())
        and bool((settings.ALOCOM_PASSWORD or "").strip())
        and agent_service_id > 0
    )
    return ready, agent_service_id


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
    fa = (user.full_name_fa or user.username or "کاربر سامانه").strip()
    parts = fa.split()
    if len(parts) >= 2:
        name = parts[0][:100]
        surname = " ".join(parts[1:])[:100]
    else:
        name = fa[:100] if len(fa) >= 2 else "کاربر سامانه"
        surname = "آنالیستو"
    if len(name) < 2:
        name = "کاربر سامانه"
    if len(surname) < 2:
        surname = "آنالیستو"
    return name, surname


def _normalize_cellphone(phone: Optional[str]) -> Optional[str]:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) < 10:
        return None
    if digits.startswith("98") and len(digits) >= 12:
        return "0" + digits[2:12]
    if digits.startswith("9") and len(digits) == 10:
        return "0" + digits
    if digits.startswith("0") and len(digits) == 11:
        return digits
    return digits[:11] if len(digits) >= 11 else None


def _link_has_join_token(link: Optional[str]) -> bool:
    return bool(link) and "token=" in link


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
            cellphone=_normalize_cellphone(user.phone),
            email=user.email,
            password=secrets.token_urlsafe(16),
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
    start_by_admin: int = 0,
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
    session_title = f"{title[:440]} {session.id.hex[:8]}".strip()[:500]
    last_err: AlocomAPIError | None = None
    raw: dict[str, Any] | None = None
    for attempt in range(5):
        event_slug = slug if attempt == 0 else f"{slug}-r{uuid.uuid4().hex[:6]}"
        event_title = session_title if attempt == 0 else f"{session_title[:420]} {uuid.uuid4().hex[:6]}"
        try:
            raw = await client.create_event(
                title=event_title,
                agent_service_id=agent_service_id,
                slug=event_slug,
                start_by_admin=start_by_admin,
                status=1,
                duration_time=duration_minutes,
                users=users_payload or None,
            )
            slug = event_slug
            break
        except AlocomAPIError as e:
            last_err = e
            if e.status_code != 422:
                raise
            logger.warning(
                "Alocom create_event 422 therapy session=%s slug=%s body=%s",
                session.id,
                event_slug,
                getattr(e, "body", None),
            )
    if raw is None:
        if last_err is not None:
            raise last_err
        raise AlocomAPIError("Alocom create_event failed after retries")

    eid, link = _extract_event_id_and_link(raw)
    if not link and eid:
        logger.info("Create event response had no alocom_link; event_id=%s keys=%s", eid, list(raw.keys()))

    host_meeting_url: Optional[str] = None
    if eid and therapist_user:
        name, surname = _split_name(therapist_user)
        uname = f"anistito_u_{therapist_user.id.hex[:20]}"
        try:
            treg = await client.register_user_in_event(
                eid,
                name=name,
                surname=surname,
                username=uname,
                role="teacher",
                cellphone=_normalize_cellphone(therapist_user.phone),
            )
            host_meeting_url = _extract_register_link(treg)
        except AlocomAPIError as reg_err:
            logger.warning("Alocom teacher register failed: %s", reg_err)

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
                cellphone=_normalize_cellphone(student_user.phone),
            )
            direct = _extract_register_link(reg)
            if direct:
                meeting_url = direct
        except AlocomAPIError as reg_err:
            logger.warning("Alocom register-user failed (using class link if any): %s", reg_err)

    if not meeting_url:
        meeting_url = link
    if fetch_student_event_link and not _link_has_join_token(meeting_url):
        raise AlocomAPIError("Alocom did not return a participant token link", body=raw)
    if not meeting_url:
        raise AlocomAPIError("Alocom did not return a meeting link", body=raw)

    session.meeting_url = meeting_url
    session.host_meeting_url = host_meeting_url or link
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
        "host_meeting_url": session.host_meeting_url,
        "slug": slug,
        "raw_keys": list(raw.keys()) if isinstance(raw, dict) else [],
    }


async def refresh_therapy_session_alocom_links(
    db: AsyncSession,
    session: TherapySession,
) -> bool:
    """لینک‌های توکن‌دار دانشجو/درمانگر را برای رویداد موجود دوباره می‌سازد."""
    eid = (getattr(session, "alocom_event_id", None) or "").strip()
    if not eid or session.meeting_provider != "alocom":
        return bool((session.meeting_url or "").strip())

    student_user = None
    therapist_user = None
    st_r = await db.execute(select(Student).where(Student.id == session.student_id))
    student = st_r.scalars().first()
    if student:
        su_r = await db.execute(select(User).where(User.id == student.user_id))
        student_user = su_r.scalars().first()
    if session.therapist_id:
        tu_r = await db.execute(select(User).where(User.id == session.therapist_id))
        therapist_user = tu_r.scalars().first()

    student_ok = _link_has_join_token(session.meeting_url)
    host_ok = _link_has_join_token(getattr(session, "host_meeting_url", None))
    if student_ok and (host_ok or not therapist_user):
        return True
    if not student_user:
        return student_ok

    client = AlocomClient(get_settings())
    changed = False
    if therapist_user and not host_ok:
        teacher_direct = None
        name, surname = _split_name(therapist_user)
        uname = f"anistito_u_{therapist_user.id.hex[:20]}"
        try:
            treg = await client.register_user_in_event(
                eid,
                name=name,
                surname=surname,
                username=uname,
                role="teacher",
                cellphone=_normalize_cellphone(therapist_user.phone),
            )
            teacher_direct = _extract_register_link(treg)
        except AlocomAPIError as e:
            logger.warning("refresh therapy teacher link failed session=%s: %s", session.id, e)
        if teacher_direct:
            session.host_meeting_url = teacher_direct
            changed = True

    if not student_ok:
        name, surname = _split_name(student_user)
        uname = f"anistito_u_{student_user.id.hex[:20]}"
        try:
            reg = await client.register_user_in_event(
                eid,
                name=name,
                surname=surname,
                username=uname,
                role="participant",
                cellphone=_normalize_cellphone(student_user.phone),
            )
            direct = _extract_register_link(reg)
            if direct:
                session.meeting_url = direct
                changed = True
        except AlocomAPIError as e:
            logger.warning("refresh therapy student link failed session=%s: %s", session.id, e)

    if changed:
        await db.flush()
    return _link_has_join_token(session.meeting_url)


async def ensure_paid_session_alocom_links(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    title: Optional[str] = None,
) -> list[dict[str, Any]]:
    """پس از پرداخت موفق جلسات: برای هر جلسهٔ پرداخت‌شدهٔ زمان‌بندی‌شده که هنوز لینک ندارد،
    رویداد الوکام ساخته و لینک روی TherapySession (پروفایل دانشجو) ذخیره می‌شود."""
    settings = get_settings()
    alocom_ready, agent_service_id = is_alocom_configured(settings)
    if not alocom_ready:
        logger.info(
            "ensure_paid_session_alocom_links skipped (alocom not configured) student=%s",
            student_id,
        )
        return []

    st_r = await db.execute(select(Student).where(Student.id == student_id))
    student = st_r.scalars().first()
    base_title = (title or (f"جلسه درمان — {student.student_code}" if student else "جلسه درمان آنلاین")).strip()

    stmt = (
        select(TherapySession)
        .where(
            TherapySession.student_id == student_id,
            TherapySession.payment_status.in_(["paid", "waived"]),
            TherapySession.status == "scheduled",
        )
        .order_by(TherapySession.session_date.asc())
    )
    sessions = (await db.execute(stmt)).scalars().all()
    out: list[dict[str, Any]] = []
    for session in sessions:
        if (session.meeting_url or "").strip():
            continue
        try:
            detail = await provision_therapy_session_alocom(
                db,
                session=session,
                agent_service_id=agent_service_id,
                title=base_title[:500] or "جلسه درمان آنلاین",
                fetch_student_event_link=True,
            )
        except AlocomAPIError as e:
            logger.warning(
                "ensure_paid_session_alocom_links failed session=%s: %s", session.id, e
            )
            continue
        out.append({"session_id": str(session.id), **detail})
    return out
