"""مرحلهٔ یکپارچهٔ «مصاحبه‌ها» در آماده‌سازی ترم (ادغام گام‌های ۷ و ۸).

کاربر مصاحبه‌گرها (از میان کارمندان اتوماسیون) را انتخاب می‌کند و برای هر نفر
می‌تواند روزها و بازهٔ ساعت مستقل بگذارد؛ این سرویس از همان ورودی، مقادیر فرم
دو مرحله و فهرست اسلات‌های قابل رزرو را می‌سازد. فرمت قدیمی (روز/ساعت مشترک)
همچنان پذیرفته می‌شود.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Optional

from app.utils.shamsi_calendar_utils import TEHRAN, parse_iso_date

COURSE_TYPE_LABELS_FA: dict[str, str] = {
    "comprehensive": "دوره جامع",
    "introductory": "دوره آشنایی",
}

COURSE_TYPES: tuple[str, ...] = ("comprehensive", "introductory")

INTERVIEW_MODES_FA: tuple[str, ...] = ("حضوری", "آنلاین")

# طول مجاز هر نوبت مصاحبه (دقیقه)
MIN_SESSION_MINUTES = 10
MAX_SESSION_MINUTES = 240
DEFAULT_SESSION_MINUTES = 45

# سقف اسلات تولیدی در یک بار ثبت — جلوگیری از ساخت انبوه ناخواسته
MAX_GENERATED_SLOTS = 400


def parse_time_hhmm(raw: Any) -> Optional[time]:
    """«۰۹:۳۰» یا «09:30» → time؛ در صورت نامعتبر بودن None."""
    if isinstance(raw, time):
        return raw
    s = str(raw or "").strip()
    if not s:
        return None
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    parts = s.split(":")
    if len(parts) < 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour, minute)


def _normalized_ids(raw: Any) -> list[str]:
    if raw is None:
        return []
    values = raw if isinstance(raw, (list, tuple)) else [raw]
    out: list[str] = []
    for item in values:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _normalized_dates(raw: Any) -> list[date]:
    if raw is None:
        return []
    values = raw if isinstance(raw, (list, tuple)) else [raw]
    out: list[date] = []
    for item in values:
        d = parse_iso_date(item)
        if d is not None and d not in out:
            out.append(d)
    return sorted(out)


def _session_minutes(raw: Any) -> Optional[int]:
    if raw in (None, ""):
        return DEFAULT_SESSION_MINUTES
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if not (MIN_SESSION_MINUTES <= value <= MAX_SESSION_MINUTES):
        return None
    return value


def tehran_local_to_utc(day: date, at: time) -> datetime:
    """تاریخ/ساعت محلی تهران → لحظهٔ UTC."""
    return datetime.combine(day, at, tzinfo=TEHRAN).astimezone(timezone.utc)


def normalize_interviewer_schedule(raw: Any) -> dict[str, Any]:
    """برنامهٔ یک مصاحبه‌گر (روزها و بازهٔ ساعت اختصاصی)."""
    data = raw if isinstance(raw, dict) else {}
    ids = _normalized_ids(
        data.get("interviewer_id")
        if data.get("interviewer_id") not in (None, "")
        else data.get("interviewer_ids")
    )
    return {
        "interviewer_id": ids[0] if ids else "",
        "dates": _normalized_dates(data.get("dates")),
        "start_time": parse_time_hhmm(data.get("start_time")),
        "end_time": parse_time_hhmm(data.get("end_time")),
    }


def _legacy_shared_schedules(data: dict[str, Any]) -> list[dict[str, Any]]:
    """فرمت قدیمی (روز/ساعت مشترک برای همه) → فهرست برنامهٔ جداگانه."""
    dates = _normalized_dates(data.get("dates"))
    start = parse_time_hhmm(data.get("start_time"))
    end = parse_time_hhmm(data.get("end_time"))
    return [
        {
            "interviewer_id": uid,
            "dates": list(dates),
            "start_time": start,
            "end_time": end,
        }
        for uid in _normalized_ids(data.get("interviewer_ids"))
    ]


def normalize_interview_group(raw: Any) -> dict[str, Any]:
    """ورودی خام یک دورهٔ مصاحبه را به ساختار یکدست تبدیل می‌کند.

    هر مصاحبه‌گر می‌تواند روزها و بازهٔ ساعت مستقل داشته باشد.
    فرمت قدیمی (interviewer_ids + dates/start/end مشترک) همچنان پذیرفته می‌شود.
    """
    data = raw if isinstance(raw, dict) else {}
    raw_schedules = data.get("interviewers")
    schedules: list[dict[str, Any]] = []
    if isinstance(raw_schedules, (list, tuple)) and raw_schedules:
        seen: set[str] = set()
        for item in raw_schedules:
            schedule = normalize_interviewer_schedule(item)
            uid = schedule["interviewer_id"]
            if not uid or uid in seen:
                continue
            seen.add(uid)
            schedules.append(schedule)
    else:
        schedules = _legacy_shared_schedules(data)

    all_dates = sorted({d for s in schedules for d in (s.get("dates") or [])})
    return {
        "interviewers": schedules,
        "interviewer_ids": [s["interviewer_id"] for s in schedules],
        "dates": all_dates,
        "start_time": schedules[0].get("start_time") if schedules else None,
        "end_time": schedules[0].get("end_time") if schedules else None,
        "session_minutes": _session_minutes(data.get("session_minutes")),
    }


def _schedule_label(index: int) -> str:
    return f"مصاحبه‌گر {index}"


def interview_group_errors(group: dict[str, Any], label_fa: str) -> list[str]:
    errors: list[str] = []
    schedules = group.get("interviewers") or []
    if not schedules:
        errors.append(f"برای {label_fa} حداقل یک مصاحبه‌گر انتخاب کنید.")

    minutes = group.get("session_minutes")
    if minutes is None:
        errors.append(
            f"مدت هر نوبت مصاحبه {label_fa} باید عددی بین "
            f"{MIN_SESSION_MINUTES} تا {MAX_SESSION_MINUTES} دقیقه باشد."
        )

    for idx, schedule in enumerate(schedules, start=1):
        who = _schedule_label(idx)
        if not schedule.get("interviewer_id"):
            errors.append(f"برای {label_fa} شناسهٔ {_schedule_label(idx)} معتبر نیست.")
            continue
        if not schedule.get("dates"):
            errors.append(f"برای {label_fa} ({who}) حداقل یک روز مصاحبه انتخاب کنید.")
        start, end = schedule.get("start_time"), schedule.get("end_time")
        if start is None or end is None:
            errors.append(f"ساعت شروع و پایان مصاحبه {label_fa} ({who}) را وارد کنید.")
        elif end <= start:
            errors.append(
                f"ساعت پایان مصاحبه {label_fa} ({who}) باید بعد از ساعت شروع باشد."
            )
        elif minutes is not None and _minutes_between(start, end) < minutes:
            errors.append(
                f"بازهٔ ساعت مصاحبه {label_fa} ({who}) کوتاه‌تر از مدت یک نوبت است."
            )
    return errors


def _minutes_between(start: time, end: time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def build_group_slot_specs(
    group: dict[str, Any],
    *,
    course_type: str,
    mode: str,
    location_fa: Optional[str],
) -> list[dict[str, Any]]:
    """برای هر مصاحبه‌گر، روزها و بازهٔ ساعت خودش را به نوبت‌های هم‌اندازه می‌شکند."""
    minutes = group.get("session_minutes")
    if not minutes:
        return []
    specs: list[dict[str, Any]] = []
    for schedule in group.get("interviewers") or []:
        start, end = schedule.get("start_time"), schedule.get("end_time")
        interviewer_id = schedule.get("interviewer_id")
        if start is None or end is None or not interviewer_id:
            continue
        for day in schedule.get("dates") or []:
            day_start = datetime.combine(day, start, tzinfo=TEHRAN)
            day_end = datetime.combine(day, end, tzinfo=TEHRAN)
            cursor = day_start
            while cursor + timedelta(minutes=minutes) <= day_end:
                finish = cursor + timedelta(minutes=minutes)
                specs.append(
                    {
                        "starts_at": cursor.astimezone(timezone.utc),
                        "ends_at": finish.astimezone(timezone.utc),
                        "course_type": course_type,
                        "mode": mode,
                        "location_fa": location_fa,
                        "interviewer_user_id": interviewer_id,
                    }
                )
                cursor = finish
    specs.sort(key=lambda s: (s["starts_at"], s["interviewer_user_id"]))
    return specs


def interview_mode_errors(mode_fa: Any, location_fa: Any) -> list[str]:
    errors: list[str] = []
    mode = str(mode_fa or "").strip()
    if mode not in INTERVIEW_MODES_FA:
        errors.append("نوع برگزاری مصاحبه را مشخص کنید (حضوری یا آنلاین).")
    elif mode == "حضوری" and not str(location_fa or "").strip():
        errors.append("برای مصاحبهٔ حضوری، آدرس یا محل برگزاری را وارد کنید.")
    return errors


def normalize_interview_setup_payload(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    return {
        "interview_mode": str(data.get("interview_mode") or "").strip(),
        "interview_location_fa": str(data.get("interview_location_fa") or "").strip(),
        "comprehensive": normalize_interview_group(data.get("comprehensive")),
        "introductory": normalize_interview_group(data.get("introductory")),
    }


def interview_setup_errors(payload: dict[str, Any]) -> list[str]:
    """همهٔ خطاهای فارسی ورودی مرحلهٔ یکپارچهٔ مصاحبه."""
    errors = interview_mode_errors(
        payload.get("interview_mode"), payload.get("interview_location_fa")
    )
    for course_type in COURSE_TYPES:
        errors.extend(
            interview_group_errors(
                payload.get(course_type) or {}, COURSE_TYPE_LABELS_FA[course_type]
            )
        )
    if not errors:
        total = len(build_interview_slot_specs(payload))
        if total == 0:
            errors.append("با تنظیمات فعلی هیچ نوبت مصاحبه‌ای ساخته نمی‌شود.")
        elif total > MAX_GENERATED_SLOTS:
            errors.append(
                f"تعداد نوبت‌های ساخته‌شده ({total}) از سقف {MAX_GENERATED_SLOTS} بیشتر است؛ "
                "روزها یا مصاحبه‌گرهای کمتری انتخاب کنید."
            )
    return errors


def slot_mode_from_fa(mode_fa: Any) -> str:
    return "in_person" if str(mode_fa or "").strip() == "حضوری" else "online"


def build_interview_slot_specs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mode = slot_mode_from_fa(payload.get("interview_mode"))
    location = (
        str(payload.get("interview_location_fa") or "").strip() or None
        if mode == "in_person"
        else None
    )
    specs: list[dict[str, Any]] = []
    for course_type in COURSE_TYPES:
        specs.extend(
            build_group_slot_specs(
                payload.get(course_type) or {},
                course_type=course_type,
                mode=mode,
                location_fa=location,
            )
        )
    return specs


def _iso_or_empty(value: Optional[date]) -> str:
    return value.isoformat() if value else ""


def interviewer_assignment_form_values(payload: dict[str, Any]) -> dict[str, Any]:
    """مقادیر فرم گام «تعیین مصاحبه‌کنندگان» از ورودی یکپارچه."""
    out: dict[str, Any] = {}
    for course_type in COURSE_TYPES:
        group = payload.get(course_type) or {}
        dates = group.get("dates") or []
        out[f"{course_type}_interviewers"] = list(group.get("interviewer_ids") or [])
        out[f"{course_type}_date_range_start"] = _iso_or_empty(dates[0] if dates else None)
        out[f"{course_type}_date_range_end"] = _iso_or_empty(dates[-1] if dates else None)
    return out


def interview_scheduling_form_values(payload: dict[str, Any]) -> dict[str, Any]:
    """مقادیر فرم گام «زمان‌بندی مصاحبه» از ورودی یکپارچه."""
    mode = str(payload.get("interview_mode") or "").strip()
    values: dict[str, Any] = {"interview_mode": mode}
    if mode == "حضوری":
        values["interview_location_fa"] = str(payload.get("interview_location_fa") or "").strip()
    return values


def _schedule_to_plan(schedule: dict[str, Any]) -> dict[str, Any]:
    return {
        "interviewer_id": schedule.get("interviewer_id") or "",
        "dates": [d.isoformat() for d in schedule.get("dates") or []],
        "start_time": (
            schedule["start_time"].strftime("%H:%M") if schedule.get("start_time") else ""
        ),
        "end_time": (
            schedule["end_time"].strftime("%H:%M") if schedule.get("end_time") else ""
        ),
    }


def interview_plan_context_values(payload: dict[str, Any]) -> dict[str, Any]:
    """طرح زمان‌بندی برای بازگرداندن در فرم هنگام ویرایش مجدد."""
    plan: dict[str, Any] = {}
    for course_type in COURSE_TYPES:
        group = payload.get(course_type) or {}
        schedules = [_schedule_to_plan(s) for s in (group.get("interviewers") or [])]
        # فیلدهای تخت برای سازگاری با خواننده‌های قدیمی نگه داشته می‌شوند
        plan[course_type] = {
            "interviewers": schedules,
            "interviewer_ids": list(group.get("interviewer_ids") or []),
            "dates": [d.isoformat() for d in group.get("dates") or []],
            "start_time": (
                group["start_time"].strftime("%H:%M") if group.get("start_time") else ""
            ),
            "end_time": (
                group["end_time"].strftime("%H:%M") if group.get("end_time") else ""
            ),
            "session_minutes": group.get("session_minutes"),
        }
    return {"interview_setup_plan": plan}


def summarize_slot_specs(specs: Iterable[dict[str, Any]]) -> dict[str, int]:
    """شمارش نوبت‌ها به تفکیک نوع دوره — برای پیام تأیید به کاربر."""
    counts = {course_type: 0 for course_type in COURSE_TYPES}
    total = 0
    for spec in specs:
        total += 1
        ct = spec.get("course_type")
        if ct in counts:
            counts[ct] += 1
    counts["total"] = total
    return counts


# ─── اجرای مرحله روی نمونهٔ فرایند ──────────────────────────

INTERVIEW_SETUP_STATES: tuple[str, ...] = (
    "interviewer_assignment",
    "interview_scheduling",
)

# مصاحبه‌گرها از میان کارمندان اتوماسیون انتخاب می‌شوند
INTERVIEWER_CANDIDATE_ROLES: tuple[str, ...] = ("interviewer", "staff")

# برچسب نوبت‌های ساخته‌شده در این مرحله — مبنای پاک‌سازی هنگام ثبت مجدد
GENERATED_SLOT_LABEL_FA = "مصاحبهٔ آماده‌سازی ترم"


class SemesterPrepInterviewSetupError(Exception):
    def __init__(self, detail: Any, status_code: int = 400) -> None:
        super().__init__(str(detail))
        self.detail = detail
        self.status_code = status_code


async def _resolve_interviewers(db, interviewer_ids: Iterable[str]) -> dict[str, Any]:
    """اعتبارسنجی شناسه‌ها و بازگرداندن نگاشت شناسه → کاربر."""
    import uuid as _uuid

    from sqlalchemy import select

    from app.models.operational_models import User

    wanted: list[_uuid.UUID] = []
    for raw in interviewer_ids:
        try:
            wanted.append(_uuid.UUID(str(raw)))
        except ValueError:
            raise SemesterPrepInterviewSetupError(
                "فهرست مصاحبه‌گرها معتبر نیست؛ لطفاً از فهرست کارمندان انتخاب کنید."
            )
    if not wanted:
        return {}
    rows = list((await db.execute(select(User).where(User.id.in_(wanted)))).scalars().all())
    by_id = {str(u.id): u for u in rows}
    for uid in wanted:
        user = by_id.get(str(uid))
        if user is None or not user.is_active:
            raise SemesterPrepInterviewSetupError(
                "یکی از مصاحبه‌گرهای انتخاب‌شده یافت نشد یا غیرفعال است."
            )
        if (user.role or "").strip() not in INTERVIEWER_CANDIDATE_ROLES:
            name = (user.full_name_fa or user.username or "").strip()
            raise SemesterPrepInterviewSetupError(
                f"«{name}» جزو کارمندان قابل انتخاب برای مصاحبه نیست."
            )
    return by_id


async def _delete_unbooked_prep_slots(db) -> int:
    """نوبت‌های آزادِ ساخته‌شده توسط همین مرحله را پیش از ثبت مجدد پاک می‌کند."""
    from sqlalchemy import select

    from app.models.operational_models import InterviewSlot

    now = datetime.now(timezone.utc)
    stmt = select(InterviewSlot).where(
        InterviewSlot.assigned_student_id.is_(None),
        InterviewSlot.ends_at >= now,
        InterviewSlot.label_fa == GENERATED_SLOT_LABEL_FA,
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for slot in rows:
        await db.delete(slot)
    return len(rows)


async def apply_semester_prep_interview_setup(
    db,
    *,
    instance_id: str,
    payload: dict[str, Any],
    actor,
) -> dict[str, Any]:
    """ثبت یک‌بارهٔ مصاحبه‌گرها، روز/ساعت و انتشار — معادل گام‌های ۷ و ۸."""
    import uuid as _uuid

    from app.core.engine import StateMachineEngine
    from app.meta.student_step_forms import apply_register_to_context
    from app.models.operational_models import InterviewSlot, ProcessInstance
    from app.services.semester_prep_service import PREP_PROCESS_CODES
    from sqlalchemy.orm.attributes import flag_modified

    try:
        iid = _uuid.UUID(str(instance_id))
    except ValueError:
        raise SemesterPrepInterviewSetupError("شناسهٔ فرایند نامعتبر است.")

    instance = await db.get(ProcessInstance, iid)
    if instance is None:
        raise SemesterPrepInterviewSetupError("فرایند یافت نشد.", status_code=404)
    if instance.process_code not in PREP_PROCESS_CODES:
        raise SemesterPrepInterviewSetupError("این مرحله فقط در آماده‌سازی ترم است.")
    if instance.is_completed or instance.is_cancelled:
        raise SemesterPrepInterviewSetupError("فرایند تکمیل یا لغو شده است.")
    state = (instance.current_state_code or "").strip()
    if state not in INTERVIEW_SETUP_STATES:
        raise SemesterPrepInterviewSetupError(
            "مرحلهٔ فعلی فرایند «مصاحبه‌ها» نیست؛ صفحه را تازه کنید."
        )

    normalized = normalize_interview_setup_payload(payload)
    errors = interview_setup_errors(normalized)
    if errors:
        raise SemesterPrepInterviewSetupError({"error": "validation_failed", "missing": errors})

    all_ids = [
        uid
        for course_type in COURSE_TYPES
        for uid in (normalized[course_type].get("interviewer_ids") or [])
    ]
    await _resolve_interviewers(db, set(all_ids))

    ctx = apply_register_to_context(
        instance.context_data or {},
        "interviewer_assignment",
        {
            **interviewer_assignment_form_values(normalized),
            **interview_plan_context_values(normalized),
        },
    )
    ctx = apply_register_to_context(
        ctx, "interview_scheduling", interview_scheduling_form_values(normalized)
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db.flush()

    removed = 0
    if payload.get("replace_existing_slots", True):
        removed = await _delete_unbooked_prep_slots(db)

    specs = build_interview_slot_specs(normalized)
    for spec in specs:
        db.add(
            InterviewSlot(
                id=_uuid.uuid4(),
                starts_at=spec["starts_at"],
                ends_at=spec["ends_at"],
                course_type=spec["course_type"],
                mode=spec["mode"],
                location_fa=spec["location_fa"],
                interviewer_user_id=_uuid.UUID(spec["interviewer_user_id"]),
                label_fa=GENERATED_SLOT_LABEL_FA,
                created_by=actor.id,
            )
        )
    await db.flush()

    engine = StateMachineEngine(db)
    actor_role = (actor.role or "").strip()
    triggers = (
        ["interviewers_assigned", "interview_times_set"]
        if state == "interviewer_assignment"
        else ["interview_times_set"]
    )
    for trigger in triggers:
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event=trigger,
            actor_id=actor.id,
            actor_role=actor_role,
            payload=None,
        )
        if not result.success:
            raise SemesterPrepInterviewSetupError(
                result.error or "پیشروی مرحلهٔ مصاحبه‌ها انجام نشد."
            )

    await db.refresh(instance)
    counts = summarize_slot_specs(specs)
    return {
        "success": True,
        "instance_id": str(instance.id),
        "current_state": instance.current_state_code,
        "removed_slots": removed,
        "created_slots": counts,
        "context_data": instance.context_data,
    }
