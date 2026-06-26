"""تجمیع جلسات و لینک‌های آنلاین دانشجو برای پنل."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.interview_slots_routes import _slot_to_dict
from app.core.engine import StateMachineEngine
from app.models.operational_models import InterviewSlot, Student, TherapySession, User
from app.services.alocom_provision import refresh_therapy_session_alocom_links
from app.services.interview_slot_service import (
    expire_interview_booking_payment_deadlines,
    maybe_provision_interview_slot_alocom_link,
)

logger = logging.getLogger(__name__)

_KIND_LABELS = {
    "therapy": "جلسه درمان آموزشی",
    "interview": "مصاحبهٔ پذیرش",
    "supervision": "جلسه سوپرویژن",
    "course": "کلاس آنلاین",
}

_PAYMENT_STATUS_FA = {
    "pending": "در انتظار پرداخت",
    "paid": "پرداخت‌شده",
    "waived": "معاف",
}

_SESSION_STATUS_FA = {
    "scheduled": "زمان‌بندی‌شده",
    "completed": "برگزار شده",
    "cancelled": "لغوشده",
    "no_show": "غیبت",
}


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_starts_at(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    try:
        if len(s) <= 10:
            return datetime.combine(date.fromisoformat(s[:10]), time.min, tzinfo=timezone.utc)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _therapy_status_fa(session: TherapySession) -> str:
    parts: list[str] = []
    pay = _PAYMENT_STATUS_FA.get(session.payment_status or "", session.payment_status or "")
    if pay:
        parts.append(pay)
    st = _SESSION_STATUS_FA.get(session.status or "", session.status or "")
    if st:
        parts.append(st)
    if not session.links_unlocked:
        parts.append("لینک هنوز فعال نشده")
    elif not (session.meeting_url or "").strip():
        parts.append("در انتظار لینک از درمانگر")
    return " · ".join(parts) if parts else "—"


def _therapy_item(session: TherapySession, *, viewer: User) -> dict[str, Any]:
    starts = session.session_starts_at
    if starts is None and session.session_date:
        starts = datetime.combine(session.session_date, time.min, tzinfo=timezone.utc)
    ends = None
    link_visible = bool(session.links_unlocked)
    meeting_link = (session.meeting_url or "").strip() if link_visible else None
    return {
        "id": str(session.id),
        "kind": "therapy",
        "title_fa": _KIND_LABELS["therapy"],
        "starts_at": _iso(starts),
        "ends_at": _iso(ends),
        "meeting_link": meeting_link or None,
        "meeting_link_is_visible": bool(link_visible and meeting_link),
        "meeting_link_open_at": None,
        "status_fa": _therapy_status_fa(session),
        "payment_status": session.payment_status,
        "session_status": session.status,
        "student_join_open": False,
        "source_ref": f"therapy_session:{session.id}",
        "meeting_provider": session.meeting_provider if link_visible else None,
        "links_unlocked": bool(session.links_unlocked),
    }


def _interview_item(slot_dict: dict[str, Any]) -> dict[str, Any]:
    label = (slot_dict.get("label_fa") or "").strip() or _KIND_LABELS["interview"]
    course = slot_dict.get("course_type")
    if course == "introductory":
        label = "مصاحبهٔ پذیرش — دوره آشنایی"
    elif course == "comprehensive":
        label = "مصاحبهٔ پذیرش — دوره جامع"
    status_parts = ["رزرو تأیید‌شده"]
    if not slot_dict.get("meeting_link_is_visible"):
        if slot_dict.get("meeting_link_open_at"):
            status_parts.append("لینک در زمان مقرر فعال می‌شود")
        else:
            status_parts.append("در انتظار لینک آنلاین")
    return {
        "id": slot_dict["id"],
        "kind": "interview",
        "title_fa": label,
        "starts_at": slot_dict.get("starts_at"),
        "ends_at": slot_dict.get("ends_at"),
        "meeting_link": slot_dict.get("meeting_link"),
        "meeting_link_is_visible": bool(slot_dict.get("meeting_link_is_visible")),
        "meeting_link_open_at": slot_dict.get("meeting_link_open_at"),
        "status_fa": " · ".join(status_parts),
        "payment_status": None,
        "session_status": None,
        "student_join_open": bool(slot_dict.get("student_join_open")),
        "source_ref": f"interview_slot:{slot_dict['id']}",
        "meeting_provider": "alocom" if slot_dict.get("alocom_event_id") else None,
        "links_unlocked": None,
    }


def _lms_supervision_item(link: dict[str, Any], index: int) -> dict[str, Any]:
    lid = str(link.get("id") or f"supervision-{index}")
    kind_raw = (link.get("kind") or "").strip()
    title = _KIND_LABELS["supervision"]
    if kind_raw == "supervision_50th":
        title = "جلسه سوپرویژن — تکمیل ۵۰ ساعت"
    url = (link.get("url") or "").strip()
    created = link.get("created_at")
    return {
        "id": lid,
        "kind": "supervision",
        "title_fa": title,
        "starts_at": _iso(_parse_starts_at(created)) if created else None,
        "ends_at": None,
        "meeting_link": url or None,
        "meeting_link_is_visible": bool(url),
        "meeting_link_open_at": None,
        "status_fa": "لینک فعال" if url else "در انتظار لینک",
        "payment_status": None,
        "session_status": None,
        "student_join_open": False,
        "source_ref": f"lms_online_link:{lid}",
        "meeting_provider": None,
        "links_unlocked": None,
    }


def _lms_course_item(course_code: str, url: str) -> dict[str, Any]:
    cid = f"course-{course_code}"
    link = (url or "").strip()
    return {
        "id": cid,
        "kind": "course",
        "title_fa": f"{_KIND_LABELS['course']} — {course_code}",
        "starts_at": None,
        "ends_at": None,
        "meeting_link": link or None,
        "meeting_link_is_visible": bool(link),
        "meeting_link_open_at": None,
        "status_fa": "لینک کلاس" if link else "در انتظار لینک",
        "payment_status": None,
        "session_status": None,
        "student_join_open": False,
        "source_ref": f"lms_course_link:{course_code}",
        "meeting_provider": None,
        "links_unlocked": None,
    }


def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
    starts = item.get("starts_at")
    if starts:
        return (0, str(starts))
    return (1, item.get("title_fa") or "")


async def list_student_online_sessions(
    db: AsyncSession,
    student: Student,
    viewer: User,
    *,
    include_past: bool = False,
) -> dict[str, Any]:
    """همهٔ جلسات/لینک‌های آنلاین دانشجو را در یک لیست مرتب‌شده برمی‌گرداند."""
    now = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []

    # ── Therapy sessions ──
    t_stmt = (
        select(TherapySession)
        .where(TherapySession.student_id == student.id)
        .order_by(TherapySession.session_date.desc())
    )
    therapy_rows = (await db.execute(t_stmt)).scalars().all()
    for session in therapy_rows:
        if not include_past:
            ref = session.session_starts_at
            if ref is None and session.session_date:
                ref = datetime.combine(session.session_date, time.max, tzinfo=timezone.utc)
            if ref and ref < now and session.status != "scheduled":
                continue
        if session.meeting_provider == "alocom" and session.links_unlocked:
            try:
                await refresh_therapy_session_alocom_links(db, session)
            except Exception:
                logger.exception(
                    "refresh_therapy_session_alocom_links failed session=%s", session.id
                )
        items.append(_therapy_item(session, viewer=viewer))

    # ── Interview slots (online, payment confirmed) ──
    await expire_interview_booking_payment_deadlines(db, now=now)
    iv_stmt = select(InterviewSlot).where(
        InterviewSlot.assigned_student_id == student.id,
        InterviewSlot.mode == "online",
        InterviewSlot.booking_payment_deadline_at.is_(None),
    )
    if not include_past:
        iv_stmt = iv_stmt.where(InterviewSlot.ends_at >= now)
    iv_stmt = iv_stmt.order_by(InterviewSlot.starts_at)
    interview_rows = (await db.execute(iv_stmt)).scalars().all()
    for slot in interview_rows:
        await maybe_provision_interview_slot_alocom_link(
            db, slot, payment_confirmed=True
        )
        slot_dict = _slot_to_dict(slot, viewer=viewer, now=now)
        items.append(_interview_item(slot_dict))

    # ── LMS links from extra_data ──
    extra = StateMachineEngine._as_mapping(student.extra_data)
    lms = StateMachineEngine._as_mapping(extra.get("lms"))
    for i, link in enumerate(lms.get("online_links") or []):
        if isinstance(link, dict):
            items.append(_lms_supervision_item(link, i))
    for course_code, url in (lms.get("portal_course_links") or {}).items():
        if course_code:
            items.append(_lms_course_item(str(course_code), str(url or "")))

    items.sort(key=_sort_key)
    with_join = sum(1 for x in items if x.get("meeting_link_is_visible") and (x.get("meeting_link") or "").strip())

    return {
        "items": items,
        "summary": {
            "total": len(items),
            "with_join_link": with_join,
        },
    }
