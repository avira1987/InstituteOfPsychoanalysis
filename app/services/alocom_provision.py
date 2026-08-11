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


def is_stub_therapy_meeting_url(url: Optional[str]) -> bool:
    """لینک داخلی ساختگی سامانه (/meet/therapy/...) بدون توکن الوکام."""
    u = (url or "").strip()
    if not u:
        return True
    return "/meet/therapy/" in u


def is_tokenized_alocom_join_url(url: Optional[str]) -> bool:
    """لینک ورود با توکن (الوکام یا fixture تست)."""
    u = (url or "").strip()
    return bool(u) and u.startswith("http") and "token=" in u and not is_stub_therapy_meeting_url(u)


def therapy_session_needs_alocom_provision(session: TherapySession) -> bool:
    """آیا باید رویداد/لینک واقعی الوکام ساخته یا جایگزین استاب شود؟"""
    if (session.payment_status or "").strip() not in ("paid", "waived"):
        return False
    if (session.status or "").strip() not in ("scheduled", "completed"):
        return False
    student_ok = is_tokenized_alocom_join_url(session.meeting_url)
    host_ok = is_tokenized_alocom_join_url(getattr(session, "host_meeting_url", None))
    if student_ok and (host_ok or not session.therapist_id):
        return False
    provider = (session.meeting_provider or "").strip().lower()
    # لینک دستی/خارجی معتبر (غیر استاب) را بازنویسی نکن
    if (
        provider in ("manual", "skyroom", "voicoom")
        and (session.meeting_url or "").strip()
        and not is_stub_therapy_meeting_url(session.meeting_url)
    ):
        return False
    return True


async def _ensure_alocom_user_id(
    db: AsyncSession,
    client: AlocomClient,
    user: User,
) -> Optional[int]:
    if getattr(user, "alocom_agent_user_id", None):
        return int(user.alocom_agent_user_id)
    name, surname = _split_name(user)
    username = f"anistito_u_{user.id.hex[:20]}"
    cellphone = _normalize_cellphone(user.phone)
    email = (user.email or "").strip() or None
    # ایمیل‌های دمو/داخلی را به الوکام نفرست (گاهی ۴۲۲ می‌دهد)
    if email and (
        email.endswith(".local")
        or email.endswith("@demo.anistito.local")
        or "example.com" in email
    ):
        email = None
    try:
        resp = await client.create_agent_user(
            name=name,
            surname=surname,
            username=username,
            status=1,
            cellphone=cellphone,
            email=email,
            password=secrets.token_urlsafe(16),
        )
    except AlocomAPIError as e:
        # تلاش دوم بدون تلفن/ایمیل و با نام‌کاربری یکتا
        logger.warning("Alocom create user failed for %s: %s — retry unique username", user.id, e)
        try:
            resp = await client.create_agent_user(
                name=name,
                surname=surname,
                username=f"an_{user.id.hex[:18]}",
                status=1,
                cellphone=None,
                email=None,
                password=secrets.token_urlsafe(16),
            )
        except AlocomAPIError as e2:
            logger.warning("Alocom create user retry failed for %s: %s", user.id, e2)
            return None
    uid = extract_agent_user_id(resp)
    if uid is None:
        logger.warning("Alocom create user response had no id: %s", resp)
        return None
    user.alocom_agent_user_id = uid
    await db.flush()
    return uid


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
        # نام‌کاربری تکراری / تداخل — با پسوند یکتا دوباره
        logger.warning(
            "Alocom register-user role=%s user=%s event=%s: %s — retry unique username",
            role,
            user.id,
            event_id,
            reg_err,
        )
        try:
            reg = await client.register_user_in_event(
                event_id,
                name=name,
                surname=surname,
                username=f"an_{role[:3]}_{user.id.hex[:14]}",
                role=role,
                cellphone=None,
            )
            return _extract_register_link(reg)
        except AlocomAPIError as e2:
            logger.warning(
                "Alocom register-user retry failed role=%s user=%s event=%s: %s body=%s",
                role,
                user.id,
                event_id,
                e2,
                getattr(e2, "body", None),
            )
            return None


async def _create_therapy_alocom_event(
    client: AlocomClient,
    *,
    title: str,
    agent_service_id: int,
    base_slug: str,
    duration_minutes: Optional[int],
) -> tuple[dict[str, Any], str]:
    """رویداد درمان را مثل مصاحبه بدون users و با guest_access می‌سازد.

    نکته: start_by_admin باید 0 باشد؛ با 1 ثبت نقش participant با خطای
    backend_not_login_administrator شکست می‌خورد. نقش teacher همچنان توکن admin می‌گیرد.
    """
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
                duration_time=duration_minutes,
                users=None,
                guest_access=True,
            )
            return raw, slug
        except AlocomAPIError as e:
            last_err = e
            if e.status_code != 422:
                raise
            logger.warning(
                "Alocom create_event 422 therapy slug=%s title=%s body=%s",
                slug,
                event_title,
                getattr(e, "body", None),
            )
    if last_err is not None:
        raise last_err
    raise AlocomAPIError("Alocom create_event failed after retries")


async def _build_therapy_links_for_event(
    client: AlocomClient,
    *,
    event_id: str,
    default_link: Optional[str],
    student_user: User,
    therapist_user: Optional[User],
    fetch_student_event_link: bool,
) -> tuple[str, Optional[str]]:
    """برمی‌گرداند (student_meeting_url, host_meeting_url)."""
    host_link: Optional[str] = None
    student_link: Optional[str] = None

    # اول درمانگر (teacher → JWT role=admin) تا میزبان کلاس مشخص شود
    if therapist_user:
        host_link = await _register_event_role_link(
            client, event_id, user=therapist_user, role="teacher"
        )

    if fetch_student_event_link:
        direct = await _register_event_role_link(
            client, event_id, user=student_user, role="participant"
        )
        if direct and _link_has_join_token(direct):
            student_link = direct
        elif direct:
            logger.warning(
                "Alocom participant link without join token event_id=%s user=%s",
                event_id,
                student_user.id,
            )

    if not host_link and _link_has_join_token(default_link):
        host_link = default_link
    elif not host_link:
        host_link = (default_link or "").strip() or None

    student_ok = bool(student_link and _link_has_join_token(student_link))
    host_ok = bool(host_link and _link_has_join_token(host_link))

    if fetch_student_event_link and not student_ok:
        raise AlocomAPIError(
            f"Alocom did not return a participant token link for event_id={event_id}",
            body={"default_link": default_link, "host_link": host_link},
        )
    if therapist_user and not host_ok:
        raise AlocomAPIError(
            f"Alocom did not return a host/teacher token link for event_id={event_id}",
            body={"default_link": default_link, "student_link": student_link},
        )

    return student_link or "", host_link


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
    """Create Alocom event, set student/host token links on TherapySession.

    ``start_by_admin`` عمداً نادیده گرفته می‌شود (همیشه 0) تا لینک دانشجو ساخته شود؛
    دسترسی ادمین میزبان از نقش teacher در ثبت‌نام رویداد می‌آید.
    """
    del start_by_admin  # API الوکام با start_by_admin=1 لینک participant را می‌بندد
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
    base_slug = build_event_slug(student.student_code, session.id)
    session_title = f"{title[:440]} {session.id.hex[:8]}".strip()[:500]

    existing_event_id = (getattr(session, "alocom_event_id", None) or "").strip()
    if existing_event_id:
        default_link = (
            (getattr(session, "host_meeting_url", None) or "").strip()
            or (session.meeting_url or "").strip()
            or None
        )
        if is_stub_therapy_meeting_url(default_link):
            default_link = None
        try:
            meeting_url, host_meeting_url = await _build_therapy_links_for_event(
                client,
                event_id=existing_event_id,
                default_link=default_link,
                student_user=student_user,
                therapist_user=therapist_user,
                fetch_student_event_link=fetch_student_event_link,
            )
        except AlocomAPIError as recover_err:
            logger.warning(
                "Recover existing Alocom therapy event failed session=%s event=%s: %s — create new",
                session.id,
                existing_event_id,
                recover_err,
            )
            session.alocom_event_id = None
            if is_stub_therapy_meeting_url(session.meeting_url) or not _link_has_join_token(
                session.meeting_url
            ):
                session.meeting_url = None
            if not _link_has_join_token(getattr(session, "host_meeting_url", None)):
                session.host_meeting_url = None
            await db.flush()
        else:
            session.meeting_url = meeting_url or session.meeting_url
            session.host_meeting_url = host_meeting_url
            session.meeting_provider = "alocom"
            session.links_unlocked = True
            await db.flush()
            return {
                "alocom_event_id": existing_event_id,
                "meeting_url": session.meeting_url,
                "host_meeting_url": session.host_meeting_url,
                "slug": base_slug,
                "recovered_existing_event": True,
            }

    raw, slug = await _create_therapy_alocom_event(
        client,
        title=session_title,
        agent_service_id=agent_service_id,
        base_slug=base_slug,
        duration_minutes=duration_minutes,
    )
    eid, link = _extract_event_id_and_link(raw)
    if not eid:
        raise AlocomAPIError("Alocom create event did not return event id", body=raw)
    if not link:
        logger.info("Create therapy event had no alocom_link; event_id=%s keys=%s", eid, list(raw.keys()))

    meeting_url, host_meeting_url = await _build_therapy_links_for_event(
        client,
        event_id=eid,
        default_link=link,
        student_user=student_user,
        therapist_user=therapist_user,
        fetch_student_event_link=fetch_student_event_link,
    )

    session.meeting_url = meeting_url
    session.host_meeting_url = host_meeting_url
    session.meeting_provider = "alocom"
    session.links_unlocked = True
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
        return _link_has_join_token(session.meeting_url) and not is_stub_therapy_meeting_url(
            session.meeting_url
        )

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

    student_ok = _link_has_join_token(session.meeting_url) and not is_stub_therapy_meeting_url(
        session.meeting_url
    )
    host_ok = _link_has_join_token(getattr(session, "host_meeting_url", None))
    if student_ok and (host_ok or not therapist_user):
        return True
    if not student_user:
        return student_ok

    client = AlocomClient(get_settings())
    try:
        meeting_url, host_meeting_url = await _build_therapy_links_for_event(
            client,
            event_id=eid,
            default_link=(getattr(session, "host_meeting_url", None) or session.meeting_url),
            student_user=student_user,
            therapist_user=therapist_user,
            fetch_student_event_link=True,
        )
    except AlocomAPIError as e:
        logger.warning("refresh therapy links failed session=%s: %s", session.id, e)
        return student_ok

    changed = False
    if meeting_url and meeting_url != session.meeting_url:
        session.meeting_url = meeting_url
        changed = True
    if host_meeting_url and host_meeting_url != getattr(session, "host_meeting_url", None):
        session.host_meeting_url = host_meeting_url
        changed = True
    if changed:
        await db.flush()
    return _link_has_join_token(session.meeting_url)


async def ensure_paid_session_alocom_links(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    title: Optional[str] = None,
) -> list[dict[str, Any]]:
    """پس از پرداخت موفق: برای جلسات پرداخت‌شده لینک واقعی الوکام بساز/جایگزین استاب کن."""
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
        if not therapy_session_needs_alocom_provision(session):
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
                "ensure_paid_session_alocom_links failed session=%s: %s body=%s",
                session.id,
                e,
                getattr(e, "body", None),
            )
            continue
        out.append({"session_id": str(session.id), **detail})
    return out


async def ensure_therapy_session_alocom_links(
    db: AsyncSession,
    session: TherapySession,
    *,
    title: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """یک جلسهٔ مشخص را در صورت نیاز به الوکام وصل می‌کند (برای پنل درمانگر/دانشجو)."""
    if not therapy_session_needs_alocom_provision(session):
        if (getattr(session, "alocom_event_id", None) or "").strip() and session.meeting_provider == "alocom":
            await refresh_therapy_session_alocom_links(db, session)
        return None
    ready, agent_service_id = is_alocom_configured()
    if not ready:
        return None
    st = await db.get(Student, session.student_id)
    base_title = (
        title
        or (f"جلسه درمان — {st.student_code}" if st else None)
        or "جلسه درمان آنلاین"
    )
    return await provision_therapy_session_alocom(
        db,
        session=session,
        agent_service_id=agent_service_id,
        title=str(base_title)[:500],
        fetch_student_event_link=True,
    )
