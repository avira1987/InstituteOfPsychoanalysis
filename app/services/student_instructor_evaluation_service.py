"""فرایند ۵۷ — ارزیابی دانشجو از مدرسین (ثبت ناشناس، تجمیع، داشبورد)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import InstituteCalendar, ProcessInstance, Student, User
from app.services.instructor_course_roster_service import (
    assigned_course_codes_for_user,
    get_course_roster,
)
from app.services.institute_calendar_service import get_active_calendar

SCORE_FIELDS = ("overall_score", "teaching_clarity", "interaction_quality")
CHART_QUESTIONS = {
    "overall_score": "نمره کلی کیفیت تدریس",
    "teaching_clarity": "شفافیت و انتقال مطلب",
    "interaction_quality": "کیفیت تعامل با دانشجویان",
}


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _course_code(entry: Any) -> str:
    if isinstance(entry, str):
        return str(entry).strip()
    if not isinstance(entry, dict):
        return ""
    return str(
        entry.get("course_code")
        or entry.get("code")
        or entry.get("course_name")
        or entry.get("name_fa")
        or ""
    ).strip()


def _course_name(entry: Any, code: str) -> str:
    if isinstance(entry, dict):
        return str(
            entry.get("course_name")
            or entry.get("name_fa")
            or entry.get("title_fa")
            or entry.get("label_fa")
            or code
        ).strip()
    return code


def _instructor_from_entry(entry: Any) -> tuple[str, str]:
    if not isinstance(entry, dict):
        return "", "مدرس"
    iid = str(entry.get("instructor_id") or entry.get("instructor_user_id") or "").strip()
    iname = str(
        entry.get("instructor_name")
        or entry.get("instructor")
        or entry.get("teacher_name")
        or "مدرس"
    ).strip()
    return iid, iname


def list_evaluable_courses(student: Student, term_code: str | None = None) -> list[dict[str, Any]]:
    """فهرست دروس قابل ارزیابی از lms.enrolled_courses."""
    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    enrolled = lms.get("enrolled_courses") or lms.get("course_links") or []
    instructors_by = _as_mapping(lms.get("instructors_by_course"))
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    if not isinstance(enrolled, list):
        return rows
    for entry in enrolled:
        code = _course_code(entry)
        if not code or code in seen:
            continue
        seen.add(code)
        iid, iname = _instructor_from_entry(entry)
        if not iid and not iname:
            ibc = instructors_by.get(code) or instructors_by.get(str(code))
            if isinstance(ibc, dict):
                iid, iname = _instructor_from_entry(ibc)
            elif isinstance(ibc, str) and ibc.strip():
                iname = ibc.strip()
        rows.append({
            "course_code": code,
            "course_name": _course_name(entry, code),
            "instructor_id": iid or None,
            "instructor_name": iname or "مدرس",
            "term_code": term_code,
        })
    return rows


def _calendar_extra(cal: InstituteCalendar | None) -> dict[str, Any]:
    if cal is None:
        return {}
    return _as_mapping(cal.extra_data)


def _set_calendar_extra(cal: InstituteCalendar, extra: dict[str, Any]) -> None:
    cal.extra_data = extra
    flag_modified(cal, "extra_data")


def _parse_score(value: Any, field: str) -> int:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"مقدار نامعتبر برای {field}") from e
    if n < 1 or n > 5:
        raise HTTPException(status_code=400, detail=f"امتیاز {field} باید بین ۱ تا ۵ باشد")
    return n


def _submitted_codes(instance: ProcessInstance) -> set[str]:
    ctx = _as_mapping(instance.context_data)
    raw = ctx.get("submitted_course_codes") or []
    if not isinstance(raw, list):
        return set()
    return {str(c).strip() for c in raw if str(c).strip()}


def _instance_term_code(instance: ProcessInstance, cal: InstituteCalendar | None) -> str:
    ctx = _as_mapping(instance.context_data)
    tc = str(ctx.get("term_code") or "").strip()
    if tc:
        return tc
    if cal and cal.term_code:
        return cal.term_code
    return "default"


async def get_evaluation_courses_for_instance(
    db: AsyncSession,
    instance: ProcessInstance,
    student: Student,
) -> dict[str, Any]:
    cal = await get_active_calendar(db)
    term_code = _instance_term_code(instance, cal)
    courses = list_evaluable_courses(student, term_code)
    submitted = _submitted_codes(instance)
    for row in courses:
        row["submitted"] = row["course_code"] in submitted
    return {
        "term_code": term_code,
        "evaluation_close_at": cal.evaluation_close_at.isoformat() if cal and cal.evaluation_close_at else None,
        "evaluation_open_at": cal.evaluation_open_at.isoformat() if cal and cal.evaluation_open_at else None,
        "courses": courses,
        "submitted_course_codes": sorted(submitted),
    }


async def submit_course_evaluation(
    db: AsyncSession,
    instance: ProcessInstance,
    student: Student,
    course_code: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if instance.process_code != "student_instructor_evaluation":
        raise HTTPException(status_code=400, detail="فرایند نامعتبر")
    if instance.current_state_code != "evaluation_open":
        raise HTTPException(status_code=400, detail="مهلت ارزیابی بسته شده است")
    if instance.is_completed or instance.is_cancelled:
        raise HTTPException(status_code=400, detail="پرونده ارزیابی بسته است")

    code = str(course_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="کد درس الزامی است")

    cal = await get_active_calendar(db)
    term_code = _instance_term_code(instance, cal)
    courses = list_evaluable_courses(student, term_code)
    match = next((c for c in courses if c["course_code"] == code), None)
    if not match:
        raise HTTPException(status_code=400, detail="این درس در فهرست دروس شما نیست")

    submitted = _submitted_codes(instance)
    if code in submitted:
        raise HTTPException(status_code=400, detail="این درس قبلاً ارزیابی شده است")

    scores = {f: _parse_score(payload.get(f), f) for f in SCORE_FIELDS}
    comments = str(payload.get("comments") or "").strip() or None

    if cal is None:
        raise HTTPException(status_code=400, detail="تقویم آموزشی فعال یافت نشد")

    extra = _calendar_extra(cal)
    submissions = list(extra.get("evaluation_submissions") or [])
    submissions.append({
        "id": str(uuid.uuid4()),
        "term_code": term_code,
        "course_code": code,
        "course_name": match["course_name"],
        "instructor_id": match.get("instructor_id"),
        "instructor_name": match.get("instructor_name"),
        "overall_score": scores["overall_score"],
        "teaching_clarity": scores["teaching_clarity"],
        "interaction_quality": scores["interaction_quality"],
        "comments": comments,
        "submitted_at": _now_iso(),
    })
    extra["evaluation_submissions"] = submissions
    _set_calendar_extra(cal, extra)

    ctx = _as_mapping(instance.context_data)
    codes = sorted(submitted | {code})
    ctx["submitted_course_codes"] = codes
    ctx["last_evaluation_submitted_at"] = _now_iso()
    instance.context_data = ctx
    flag_modified(instance, "context_data")

    return {
        "success": True,
        "course_code": code,
        "submitted_course_codes": codes,
    }


def _distribution(values: list[int]) -> dict[str, int]:
    dist = {str(i): 0 for i in range(1, 6)}
    for v in values:
        if 1 <= v <= 5:
            dist[str(v)] += 1
    return dist


def _avg(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


async def aggregate_term_results(db: AsyncSession, term_code: str) -> dict[str, Any]:
    """تجمیع نتایج ارزیابی برای یک ترم."""
    stmt = select(InstituteCalendar).where(InstituteCalendar.term_code == term_code)
    cal = (await db.execute(stmt)).scalars().first()
    if cal is None:
        cal = await get_active_calendar(db)
    if cal is None:
        return {"term_code": term_code, "courses": [], "aggregated_at": _now_iso()}

    extra = _calendar_extra(cal)
    submissions = [
        s for s in (extra.get("evaluation_submissions") or [])
        if isinstance(s, dict) and str(s.get("term_code") or term_code) == term_code
    ]

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sub in submissions:
        code = str(sub.get("course_code") or "").strip()
        iname = str(sub.get("instructor_name") or "مدرس").strip()
        key = (code, iname)
        groups.setdefault(key, []).append(sub)

    history = _as_mapping(extra.get("evaluation_history"))
    past_terms = {
        k: v for k, v in history.items()
        if k != term_code and isinstance(v, dict)
    }

    course_rows: list[dict[str, Any]] = []
    for (code, iname), subs in sorted(groups.items(), key=lambda x: x[0][0]):
        roster = await get_course_roster(db, code)
        enrolled_count = len(roster) if roster else 0
        participation_count = len(subs)
        participation_rate = (
            round(participation_count / enrolled_count, 4) if enrolled_count > 0 else None
        )

        overall_vals = [int(s["overall_score"]) for s in subs if s.get("overall_score") is not None]
        chart_data = {}
        for field, label in CHART_QUESTIONS.items():
            vals = [int(s[field]) for s in subs if s.get(field) is not None]
            chart_data[field] = {
                "label_fa": label,
                "distribution": _distribution(vals),
                "average": _avg(vals),
            }

        historical_average = None
        past_avgs: list[float] = []
        for past_data in past_terms.values():
            for prow in past_data.get("courses") or []:
                if (
                    isinstance(prow, dict)
                    and str(prow.get("course_code")) == code
                    and str(prow.get("instructor_name") or "") == iname
                    and prow.get("average_score") is not None
                ):
                    try:
                        past_avgs.append(float(prow["average_score"]))
                    except (TypeError, ValueError):
                        pass
        if past_avgs:
            historical_average = round(sum(past_avgs) / len(past_avgs), 2)

        sample = subs[0] if subs else {}
        course_rows.append({
            "course_code": code,
            "course_name": sample.get("course_name") or code,
            "instructor_id": sample.get("instructor_id"),
            "instructor_name": iname,
            "participation_count": participation_count,
            "enrolled_count": enrolled_count,
            "participation_rate": participation_rate,
            "average_score": _avg(overall_vals),
            "chart_data": chart_data,
            "historical_average": historical_average,
        })

    aggregated = {
        "term_code": term_code,
        "aggregated_at": _now_iso(),
        "courses": course_rows,
    }
    extra["evaluation_aggregated"] = aggregated
    history[term_code] = aggregated
    extra["evaluation_history"] = history
    _set_calendar_extra(cal, extra)
    return aggregated


def _get_aggregated(cal: InstituteCalendar | None, term_code: str | None = None) -> dict[str, Any] | None:
    if cal is None:
        return None
    extra = _calendar_extra(cal)
    agg = extra.get("evaluation_aggregated")
    if isinstance(agg, dict):
        if term_code and str(agg.get("term_code") or "") != term_code:
            pass
        else:
            return agg
    if term_code:
        hist = _as_mapping(extra.get("evaluation_history"))
        h = hist.get(term_code)
        if isinstance(h, dict):
            return h
    return None


async def results_for_instructor(
    db: AsyncSession,
    user: User,
    term_code: str | None = None,
) -> dict[str, Any]:
    cal = await get_active_calendar(db)
    tc = term_code or (cal.term_code if cal else "default")
    agg = _get_aggregated(cal, tc)
    if not agg:
        return {
            "term_code": tc,
            "aggregated_at": None,
            "evaluation_close_at": cal.evaluation_close_at.isoformat() if cal and cal.evaluation_close_at else None,
            "courses": [],
        }

    role = (user.role or "").strip()
    if role in ("admin", "staff"):
        courses = list(agg.get("courses") or [])
    else:
        allowed = assigned_course_codes_for_user(user)
        courses = [
            c for c in (agg.get("courses") or [])
            if isinstance(c, dict) and str(c.get("course_code") or "") in allowed
        ]

    return {
        "term_code": tc,
        "aggregated_at": agg.get("aggregated_at"),
        "evaluation_close_at": cal.evaluation_close_at.isoformat() if cal and cal.evaluation_close_at else None,
        "courses": courses,
    }


_COMMITTEE_ROLES = frozenset({
    "admin",
    "staff",
    "course_committee",
    "course_committee_scientific",
    "course_committee_executive",
    "scientific_officer_course_committee",
    "deputy_education",
    "deputy_education_director",
})


async def results_for_committee(
    db: AsyncSession,
    user: User,
    term_code: str | None = None,
) -> dict[str, Any]:
    role = (user.role or "").strip()
    if role not in _COMMITTEE_ROLES:
        raise HTTPException(status_code=403, detail="دسترسی به نتایج کمیته مجاز نیست")

    cal = await get_active_calendar(db)
    tc = term_code or (cal.term_code if cal else "default")
    agg = _get_aggregated(cal, tc)
    if not agg:
        return {
            "term_code": tc,
            "aggregated_at": None,
            "evaluation_close_at": cal.evaluation_close_at.isoformat() if cal and cal.evaluation_close_at else None,
            "courses": [],
        }
    return {
        "term_code": tc,
        "aggregated_at": agg.get("aggregated_at"),
        "evaluation_close_at": cal.evaluation_close_at.isoformat() if cal and cal.evaluation_close_at else None,
        "courses": list(agg.get("courses") or []),
    }


async def load_instance_for_student(
    db: AsyncSession,
    instance_id: uuid.UUID,
    user: User,
) -> tuple[ProcessInstance, Student]:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="فقط دانشجو")
    st = (await db.execute(select(Student).where(Student.user_id == user.id))).scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="پروفایل دانشجو یافت نشد")
    inst = (
        await db.execute(select(ProcessInstance).where(ProcessInstance.id == instance_id))
    ).scalars().first()
    if not inst:
        raise HTTPException(status_code=404, detail="پرونده یافت نشد")
    if inst.student_id != st.id:
        raise HTTPException(status_code=403, detail="دسترسی به این پرونده مجاز نیست")
    return inst, st
