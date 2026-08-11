"""تولید و تکمیل جلسات درمان آموزشی تا پایان ترم جاری."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import EducationalTherapistSlot, Student, TherapySession
from app.utils.shamsi_calendar_utils import TEHRAN, parse_iso_date, tehran_today

logger = logging.getLogger(__name__)

DEFAULT_TERM_WEEKS = 16
MAX_SESSIONS_PER_SEED = 120
ENSURE_NOTE_TAG = "therapy_schedule_until_term"


async def resolve_term_end_date(
    db: AsyncSession,
    student: Optional[Student] = None,
    *,
    fallback_from: Optional[date] = None,
) -> date:
    """پایان ترم جاری: تقویم فعال → extra_data دانشجو → fallback_from + ۱۶ هفته.

    اگر تاریخ تقویم گذشته یا خیلی نزدیک باشد، حداقل افق DEFAULT_TERM_WEEKS از امروز
    (یا fallback_from) تضمین می‌شود تا بذر جلسات متوقف نشود.
    """
    from app.services.institute_calendar_service import get_active_calendar

    base = fallback_from or tehran_today()
    floor = base + timedelta(weeks=DEFAULT_TERM_WEEKS)
    candidates: list[date] = []

    cal = await get_active_calendar(db)
    if cal and cal.term_end_date:
        candidates.append(cal.term_end_date)
    if student is not None:
        extra = student.extra_data if isinstance(student.extra_data, dict) else {}
        parsed = parse_iso_date(extra.get("term_end_date"))
        if parsed:
            candidates.append(parsed)

    if not candidates:
        return floor
    return max(max(candidates), floor)


def expand_weekly_session_dates(
    first: date,
    weekdays: Sequence[int],
    until: date,
    *,
    max_sessions: int = MAX_SESSIONS_PER_SEED,
    week_interval: int = 1,
) -> list[date]:
    """همهٔ تاریخ‌های جلسه از first تا until روی روزهای هفتهٔ داده‌شده.

    week_interval=1 هر هفته؛ week_interval=2 هفته‌درمیان (هر ۱۴ روز از اولین وقوع هر weekday).
    """
    if until < first:
        return []
    wd_set = sorted({int(w) % 7 for w in weekdays if w is not None})
    if not wd_set:
        return []
    interval = 2 if int(week_interval or 1) == 2 else 1
    if interval == 1:
        out: list[date] = []
        d = first
        guard = 0
        max_days = max(1, (until - first).days + 1)
        while d <= until and len(out) < max_sessions and guard < max_days + 7:
            if d.weekday() in wd_set:
                out.append(d)
            d += timedelta(days=1)
            guard += 1
        return out

    # هفته‌درمیان: برای هر weekday از اولین وقوع روی/بعد از first، هر ۱۴ روز
    out_set: set[date] = set()
    step = 7 * interval
    for wd in wd_set:
        d = first + timedelta(days=(wd - first.weekday()) % 7)
        while d <= until and len(out_set) < max_sessions:
            out_set.add(d)
            d += timedelta(days=step)
    return sorted(out_set)[:max_sessions]


def expand_session_dates_for_slots(
    first: date,
    slots: Sequence[Any],
    until: date,
    *,
    max_sessions: int = MAX_SESSIONS_PER_SEED,
) -> list[date]:
    """بذر تاریخ از اسلات‌ها با week_interval جداگانه برای هر اسلات."""
    if until < first or not slots:
        return []
    out_set: set[date] = set()
    for slot in slots:
        try:
            wd = int(getattr(slot, "day_of_week"))
        except (TypeError, ValueError, AttributeError):
            continue
        try:
            interval = int(getattr(slot, "week_interval", 1) or 1)
        except (TypeError, ValueError):
            interval = 1
        interval = 2 if interval == 2 else 1
        d = first + timedelta(days=(wd - first.weekday()) % 7)
        step = 7 * interval
        while d <= until and len(out_set) < max_sessions:
            out_set.add(d)
            d += timedelta(days=step)
    return sorted(out_set)[:max_sessions]


def fallback_weekdays(first: date, weekly_sessions: int) -> list[int]:
    """اگر اسلات نباشد: الگوی تقریبی ۱× یا ۲× در هفته از روی تاریخ شروع."""
    ws = max(1, min(int(weekly_sessions or 1), 7))
    base = int(first.weekday())
    if ws == 1:
        return [base]
    # دو جلسه: روز شروع و دو روز بعد (مثلاً یکشنبه+سه‌شنبه)
    second = (base + 2) % 7
    if ws == 2:
        return sorted({base, second})
    days = [base]
    step = max(1, 7 // ws)
    for i in range(1, ws):
        days.append((base + i * step) % 7)
    return sorted(set(days))


def therapy_debt_sessions_clause(
    student_id: uuid.UUID,
    *,
    as_of: Optional[date] = None,
):
    """فیلتر SQL بدهی جلسه طبق SOP.

    بدهی = بدون پرداخت + (completed یا تاریخ جلسه قبل از امروز تهران).
    جلسات آیندهٔ scheduled/pending بدهی نیستند؛ فقط پیش‌پرداخت اختیاری‌اند.
    """
    today = as_of or tehran_today()
    return and_(
        TherapySession.student_id == student_id,
        TherapySession.payment_status == "pending",
        TherapySession.status.in_(["scheduled", "completed"]),
        or_(
            TherapySession.status == "completed",
            TherapySession.session_date < today,
        ),
    )


async def count_therapy_debt_sessions(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    as_of: Optional[date] = None,
) -> int:
    """تعداد جلسات بدهکار واقعی (نه کل تقویم آیندهٔ بدون پرداخت)."""
    stmt = select(func.count()).select_from(TherapySession).where(
        therapy_debt_sessions_clause(student_id, as_of=as_of)
    )
    r = await db.execute(stmt)
    return int(r.scalar() or 0)


def session_counts_as_therapy_debt(
    *,
    payment_status: Optional[str],
    status: Optional[str],
    session_date: Optional[date],
    as_of: Optional[date] = None,
) -> bool:
    """هم‌تراز UI/تست با therapy_debt_sessions_clause."""
    if (payment_status or "").strip() != "pending":
        return False
    st = (status or "").strip()
    if st not in ("scheduled", "completed"):
        return False
    if st == "completed":
        return True
    today = as_of or tehran_today()
    return session_date is not None and session_date < today


def _starts_at_for_day(
    d: date,
    slot_by_weekday: dict[int, Any],
) -> Optional[datetime]:
    slot = slot_by_weekday.get(d.weekday())
    if slot is None:
        return None
    local_t = getattr(slot, "start_local_time", None)
    if local_t is None:
        return None
    if not isinstance(local_t, time):
        return None
    return datetime.combine(d, local_t, tzinfo=TEHRAN).astimezone(timezone.utc)


async def _weekdays_and_slots_for_student(
    db: AsyncSession,
    student: Student,
) -> tuple[list[int], dict[int, EducationalTherapistSlot]]:
    """روزهای هفته و اسلات‌های زمان از اسلات رزروشده یا جلسات موجود."""
    slot_by_weekday: dict[int, EducationalTherapistSlot] = {}
    if student.therapist_id:
        stmt = select(EducationalTherapistSlot).where(
            EducationalTherapistSlot.therapist_user_id == student.therapist_id,
            EducationalTherapistSlot.assigned_student_id == student.id,
        )
        rows = list((await db.execute(stmt)).scalars().all())
        for s in rows:
            try:
                wd = int(s.day_of_week)
            except (TypeError, ValueError):
                continue
            slot_by_weekday[wd] = s

    if slot_by_weekday:
        return sorted(slot_by_weekday.keys()), slot_by_weekday

    # از جلسات قبلی الگو بگیر
    sess_stmt = (
        select(TherapySession)
        .where(
            TherapySession.student_id == student.id,
            TherapySession.status.in_(["scheduled", "completed"]),
        )
        .order_by(TherapySession.session_date.desc())
        .limit(40)
    )
    sessions = list((await db.execute(sess_stmt)).scalars().all())
    counts: dict[int, int] = {}
    for ts in sessions:
        if ts.session_date:
            counts[ts.session_date.weekday()] = counts.get(ts.session_date.weekday(), 0) + 1
    if counts:
        # پرتکرارترین‌ها تا weekly_sessions
        ws = max(1, int(student.weekly_sessions or 1))
        top = sorted(counts.keys(), key=lambda w: (-counts[w], w))[:ws]
        return sorted(top), {}

    today = tehran_today()
    return fallback_weekdays(today, int(student.weekly_sessions or 1)), {}


async def _resolve_therapist_id(db: AsyncSession, student: Student) -> Optional[uuid.UUID]:
    if student.therapist_id:
        return student.therapist_id
    stmt = (
        select(TherapySession.therapist_id)
        .where(
            TherapySession.student_id == student.id,
            TherapySession.therapist_id.is_not(None),
        )
        .order_by(TherapySession.session_date.desc())
        .limit(1)
    )
    tid = (await db.execute(stmt)).scalar_one_or_none()
    if tid:
        student.therapist_id = tid
        return tid
    return None


async def ensure_therapy_sessions_until_term_end(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    note_tag: str = ENSURE_NOTE_TAG,
) -> dict[str, Any]:
    """
    برای دانشجوی با درمان فعال، جلسات scheduled گم‌شده تا پایان ترم را بسازد
    (بدون دست زدن به جلسات موجود / کنسل‌شده).
    """
    from app.services.attendance_tracking_sync import ensure_attendance_instance_for_session

    student = await db.get(Student, student_id)
    if not student or not student.therapy_started:
        return {"created": 0, "skipped": "not_eligible"}

    therapist_id = await _resolve_therapist_id(db, student)
    if not therapist_id:
        return {"created": 0, "skipped": "no_therapist"}

    weekdays, slot_by_weekday = await _weekdays_and_slots_for_student(db, student)
    if not weekdays:
        weekdays = fallback_weekdays(tehran_today(), int(student.weekly_sessions or 1))
    if not weekdays:
        return {"created": 0, "skipped": "no_weekdays"}

    today = tehran_today()
    term_end = await resolve_term_end_date(db, student, fallback_from=today)
    if term_end < today:
        term_end = today + timedelta(weeks=DEFAULT_TERM_WEEKS)

    # اولین تاریخ آینده روی الگوی هفتگی (از فردا اگر امروز گذشته)
    first = today
    for _ in range(14):
        if first.weekday() in weekdays:
            break
        first += timedelta(days=1)

    if slot_by_weekday:
        wanted = expand_session_dates_for_slots(first, list(slot_by_weekday.values()), term_end)
    else:
        wanted = expand_weekly_session_dates(first, weekdays, term_end)
    if not wanted:
        return {"created": 0, "skipped": "empty_range", "term_end": term_end.isoformat()}

    existing_stmt = select(TherapySession.session_date).where(
        TherapySession.student_id == student_id,
        TherapySession.status.in_(["scheduled", "completed", "cancelled"]),
        TherapySession.session_date >= today,
        TherapySession.session_date <= term_end,
    )
    existing_dates = {
        row[0] for row in (await db.execute(existing_stmt)).all() if row[0] is not None
    }

    created = 0
    created_ids: list[uuid.UUID] = []
    for d in wanted:
        if d in existing_dates:
            continue
        ts = TherapySession(
            id=uuid.uuid4(),
            student_id=student_id,
            therapist_id=therapist_id,
            session_date=d,
            session_starts_at=_starts_at_for_day(d, slot_by_weekday),
            status="scheduled",
            payment_status="pending",
            notes=note_tag,
        )
        db.add(ts)
        created_ids.append(ts.id)
        created += 1
        existing_dates.add(d)
    if created:
        await db.flush()
        for sid in created_ids:
            ts = await db.get(TherapySession, sid)
            if not ts:
                continue
            try:
                await ensure_attendance_instance_for_session(db, ts)
            except Exception:
                logger.exception(
                    "ensure_attendance_instance_for_session failed session=%s", ts.id
                )

    return {
        "created": created,
        "term_end": term_end.isoformat(),
        "weekdays": weekdays,
        "wanted": len(wanted),
        "therapist_id": str(therapist_id),
    }


async def repair_student_therapy_continuity(
    db: AsyncSession,
    student_id: uuid.UUID,
) -> dict[str, Any]:
    """بذر جلسات آینده + در صورت نیاز باز کردن session_payment و چسباندن primary."""
    from app.services.student_service import StudentService

    seed = await ensure_therapy_sessions_until_term_end(db, student_id)
    pay = await StudentService(db).ensure_active_session_payment_for_student(student_id)
    return {"seed": seed, "session_payment": pay}
