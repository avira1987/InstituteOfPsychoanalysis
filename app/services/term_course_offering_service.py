"""Publish and query term course offerings from semester prep."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, TermCourseOffering
from app.services.course_committee_roster_service import (
    _slug_code,
    catalog_units_for_course,
    get_catalog_course,
    list_course_catalog_options,
    resolve_track_for_course,
)
from app.services.institute_calendar_service import get_active_calendar
from app.services.semester_prep_service import FALL_PREP, WINTER_PREP

# Legacy intro codes → catalog codes for display of old student records
LEGACY_COURSE_CODE_MAP: dict[str, str] = {
    "theory_1": "theory_psychoanalysis_1",
    "theory_2": "theory_psychoanalysis_2",
    "theory_3": "theory_psychoanalysis_3",
    "theory_4": "theory_psychoanalysis_4",
    "theory_5": "theory_psychoanalysis_5",
}
_LEGACY_REVERSE = {v: k for k, v in LEGACY_COURSE_CODE_MAP.items()}

NO_OFFERINGS_REASON_FA = (
    "لیست دروس این ترم هنوز از فرایند آماده‌سازی ترم منتشر نشده است؛ "
    "پس از انتشار توسط انستیتو این بخش فعال می‌شود."
)
NO_SCHEDULE_REASON_FA = "برنامهٔ کلاسی این درس هنوز منتشر نشده است."
NO_TUITION_REASON_FA = "شهریهٔ این ترم ثبت نشده است."
SINGLE_COURSE_MISSING_REASON_FA = (
    "درس مجاز پذیرش تک‌درس در فهرست ارائه‌شدهٔ این ترم نیست."
)
# پذیرش تک‌درس: فقط تئوری روانکاوی همان ترم (نه اولین آیتم الفبایی)
SINGLE_COURSE_ALLOWED_BY_TERM: dict[int, str] = {
    1: "theory_psychoanalysis_1",
    2: "theory_psychoanalysis_2",
}

_COURSE_SELECTION_STATES: dict[str, frozenset[str]] = {
    "introductory_course_registration": frozenset({"course_selection", "payment"}),
    "intro_second_semester_registration": frozenset(
        {"course_selection", "payment_method", "payment_processing"}
    ),
    "comprehensive_course_registration": frozenset({"course_display", "course_selection", "payment"}),
}

_PROCESS_PROGRAM_TERM: dict[str, tuple[str, int]] = {
    "introductory_course_registration": ("introductory", 1),
    "intro_second_semester_registration": ("introductory", 2),
    "comprehensive_course_registration": ("comprehensive", 3),
    "comprehensive_term_start": ("comprehensive", 3),
}

# فیلد انتخاب دانشجو — available_courses در ترم ۱ فهرست ارائه‌شده است نه انتخاب
_PROCESS_SELECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "introductory_course_registration": ("selected_courses",),
    "intro_second_semester_registration": ("selected_courses", "available_courses"),
    "comprehensive_course_registration": ("selected_courses", "available_courses"),
    "comprehensive_term_start": ("selected_courses", "available_courses"),
}

_DIGIT_TRANSLATE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _normalize_name(name: str) -> str:
    return (name or "").strip().replace("ي", "ی")


def resolve_course_code_from_name(course_name: str) -> str:
    """Map Persian course name to stable catalog code."""
    raw = (course_name or "").strip()
    if not raw:
        return _slug_code("course", "unknown")
    if raw in LEGACY_COURSE_CODE_MAP:
        return LEGACY_COURSE_CODE_MAP[raw]
    # exact catalog match (value, label, SOP alias)
    catalog = get_catalog_course(raw)
    if catalog:
        return str(catalog.get("value") or _slug_code("course", raw))
    return _slug_code("course", raw)


def normalize_legacy_course_code(code: str) -> str:
    """Convert legacy theory_N codes and informal Persian names to catalog codes."""
    c = (code or "").strip()
    if c in LEGACY_COURSE_CODE_MAP:
        return LEGACY_COURSE_CODE_MAP[c]
    catalog = get_catalog_course(c)
    if catalog and catalog.get("value"):
        return str(catalog["value"])
    return c


def parse_positive_int(value: Any) -> int:
    """Parse units/counts; Persian digits allowed. 0 if missing/invalid."""
    if value in (None, ""):
        return 0
    s = str(value).strip().translate(_DIGIT_TRANSLATE)
    try:
        n = int(round(float(s)))
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def extract_course_codes(raw: Any) -> list[str]:
    """Normalize selected-course payloads (list, JSON string, CSV, dict items)."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, dict):
        val = raw.get("value") or raw.get("code") or raw.get("course_code")
        return extract_course_codes(val)
    if isinstance(raw, (list, tuple, set)):
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            for code in extract_course_codes(item):
                if code not in seen:
                    seen.add(code)
                    out.append(code)
        return out
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                import json

                parsed = json.loads(s)
                if isinstance(parsed, (list, dict)):
                    return extract_course_codes(parsed)
            except (json.JSONDecodeError, TypeError, ValueError):
                return []
        parts = [p.strip() for p in s.replace("،", ",").split(",") if p.strip()]
        out: list[str] = []
        seen: set[str] = set()
        for part in parts:
            code = normalize_legacy_course_code(part)
            if code and code not in seen:
                seen.add(code)
                out.append(code)
        return out
    code = normalize_legacy_course_code(str(raw).strip())
    return [code] if code else []


def selected_course_codes_for_tuition(process_code: str, ctx: dict[str, Any]) -> list[str]:
    """Student-chosen courses for tuition — not the full published catalog."""
    data = ctx if isinstance(ctx, dict) else {}
    fields = _PROCESS_SELECTION_FIELDS.get(str(process_code or ""), ("selected_courses",))
    for key in fields:
        codes = extract_course_codes(data.get(key))
        if codes:
            return codes
    lms = data.get("lms") if isinstance(data.get("lms"), dict) else {}
    enrolled = extract_course_codes(
        lms.get("enrolled_courses") or data.get("enrolled_courses")
    )
    return enrolled


def _row_from_prep(
    row: dict[str, Any],
    *,
    program_kind: str,
    term_number: int,
    term_code: str,
    per_unit_cost_rial: Optional[int],
    prerequisite_codes: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    name = str(row.get("course_name") or row.get("name") or "").strip()
    if not name:
        return None
    code = resolve_course_code_from_name(name)
    track = (row.get("track") or resolve_track_for_course(name) or "").strip() or None
    catalog = get_catalog_course(code) or get_catalog_course(name)
    units = catalog_units_for_course(code)
    raw_units = row.get("units")
    if raw_units not in (None, ""):
        try:
            parsed = int(raw_units)
            if parsed > 0:
                units = parsed
        except (TypeError, ValueError):
            pass
    catalog_prereqs = []
    if catalog and isinstance(catalog.get("prerequisite_codes"), list):
        catalog_prereqs = [
            normalize_legacy_course_code(str(c).strip())
            for c in catalog["prerequisite_codes"]
            if str(c).strip()
        ]
    if "prerequisite_codes" in row and isinstance(row.get("prerequisite_codes"), list):
        prereqs = [
            normalize_legacy_course_code(str(c).strip())
            for c in row["prerequisite_codes"]
            if str(c).strip()
        ]
    elif prerequisite_codes is not None:
        prereqs = [
            normalize_legacy_course_code(str(c).strip())
            for c in prerequisite_codes
            if str(c).strip()
        ]
    else:
        prereqs = catalog_prereqs
    return {
        "term_code": term_code,
        "course_code": code,
        "course_name_fa": name,
        "track": track,
        "program_kind": program_kind,
        "term_number": term_number,
        "day": str(row.get("day") or row.get("proposed_day") or "").strip() or None,
        "time_text": str(row.get("time") or row.get("proposed_time") or "").strip() or None,
        "classroom_location": str(row.get("classroom_location") or "").strip() or None,
        "instructor_name": str(row.get("instructor") or "").strip() or None,
        "teaching_assistant_name": str(row.get("teaching_assistant") or "").strip() or None,
        "units": units,
        "per_unit_cost_rial": per_unit_cost_rial,
        "prerequisite_codes": prereqs,
    }


def _prep_rows_from_context(
    ctx: dict[str, Any],
    process_code: str,
) -> list[tuple[list[Any], str, int]]:
    """Return list of (rows, program_kind, term_number) to publish."""
    batches: list[tuple[list[Any], str, int]] = []
    if process_code == FALL_PREP:
        fall_rows = ctx.get("courses_finalized_fall") or ctx.get("courses_fall") or ctx.get("courses")
        winter_rows = ctx.get("courses_finalized_winter") or ctx.get("courses_winter")
        if isinstance(fall_rows, list) and fall_rows:
            batches.append((fall_rows, "introductory", 1))
        if isinstance(winter_rows, list) and winter_rows:
            batches.append((winter_rows, "introductory", 2))
            batches.append((winter_rows, "comprehensive", 3))
    elif process_code == WINTER_PREP:
        rows = ctx.get("courses_finalized") or ctx.get("courses")
        if isinstance(rows, list) and rows:
            batches.append((rows, "introductory", 2))
            batches.append((rows, "comprehensive", 3))
    return batches


def _per_unit_cost_for_program(ctx: dict[str, Any], program_kind: str) -> Optional[int]:
    key = (
        "per_unit_cost_introductory"
        if program_kind == "introductory"
        else "per_unit_cost_comprehensive"
    )
    raw = ctx.get(key)
    try:
        return int(raw) if raw is not None and str(raw).strip() != "" else None
    except (TypeError, ValueError):
        return None


def single_course_allowed_codes(term_number: int) -> list[str]:
    """کدهای کاتالوگ مجاز تک‌درس برای این شماره ترم (پرچم کاتالوگ، وگرنه پیش‌فرض SOP)."""
    try:
        n = int(term_number)
    except (TypeError, ValueError):
        n = 1
    if n < 1:
        n = 1
    flagged: list[str] = []
    for opt in list_course_catalog_options():
        if not isinstance(opt, dict) or not opt.get("single_course_allowed"):
            continue
        try:
            term = int(opt.get("curriculum_term") or 0)
        except (TypeError, ValueError):
            continue
        value = str(opt.get("value") or "").strip()
        if term == n and value:
            flagged.append(normalize_legacy_course_code(value))
    if flagged:
        return flagged
    fallback = SINGLE_COURSE_ALLOWED_BY_TERM.get(n)
    if not fallback and n <= 1:
        fallback = SINGLE_COURSE_ALLOWED_BY_TERM[1]
    return [fallback] if fallback else []


def single_course_allowed_code(term_number: int) -> Optional[str]:
    """کد کاتالوگ درس مجاز تک‌درس برای این شماره ترم."""
    codes = single_course_allowed_codes(term_number)
    return codes[0] if codes else None


def _option_code(opt: dict[str, Any]) -> str:
    return normalize_legacy_course_code(str(opt.get("value") or opt.get("course_code") or ""))


def canonicalize_course_option(opt: dict[str, Any]) -> dict[str, Any]:
    """کد کاتالوگ پایدار + پیش‌نیاز/پرچم تک‌درس از کاتالوگ."""
    extra = dict(opt)
    raw = str(opt.get("value") or opt.get("course_code") or "").strip()
    name = str(opt.get("label_fa") or opt.get("course_name") or "").strip()
    cat = get_catalog_course(raw) or get_catalog_course(name)
    if cat and cat.get("value"):
        code = str(cat["value"])
    else:
        code = normalize_legacy_course_code(raw or name)
    extra["value"] = code or raw
    if cat:
        if cat.get("label_fa") and not extra.get("label_fa"):
            extra["label_fa"] = cat["label_fa"]
        extra["single_course_allowed"] = bool(cat.get("single_course_allowed"))
        stored = extra.get("prerequisite_codes")
        if not (isinstance(stored, list) and stored):
            raw_prereqs = cat.get("prerequisite_codes") or []
            extra["prerequisite_codes"] = [
                normalize_legacy_course_code(str(c).strip())
                for c in raw_prereqs
                if str(c).strip()
            ]
        else:
            extra["prerequisite_codes"] = [
                normalize_legacy_course_code(str(c).strip())
                for c in stored
                if str(c).strip()
            ]
    return extra


async def publish_term_tuition_from_prep(
    db: AsyncSession,
    ctx: dict[str, Any],
    *,
    published_by: Optional[uuid.UUID] = None,
) -> bool:
    from app.services.financial_program_defaults_service import sync_term_tuition_from_prep_context

    # یک منبع حقیقت با داشبورد مالی
    await sync_term_tuition_from_prep_context(db, ctx)

    cal = await get_active_calendar(db)
    if cal is None:
        return False
    extra = dict(cal.extra_data or {})
    tuition = dict(extra.get("tuition") or {})
    changed = False
    for key in (
        "per_unit_cost_introductory",
        "per_unit_cost_comprehensive",
        "interview_fee_introductory",
        "interview_fee_comprehensive",
    ):
        val = ctx.get(key)
        if val is not None and str(val).strip() != "":
            tuition[key] = val
            changed = True
    if changed:
        tuition["published_at"] = datetime.now(timezone.utc).isoformat()
        if published_by:
            tuition["published_by"] = str(published_by)
        extra["tuition"] = tuition
        cal.extra_data = extra
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(cal, "extra_data")
    return changed


async def publish_offerings_from_prep(
    db: AsyncSession,
    instance: ProcessInstance,
    context: Optional[dict[str, Any]] = None,
    *,
    published_by: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
    ctx = StateMachineEngine._as_mapping(context or instance.context_data)
    cal = await get_active_calendar(db)
    if cal is None:
        return {
            "published": False,
            "reason_fa": "تقویم آموزشی فعال نیست؛ ابتدا تقویم را منتشر کنید.",
            "count": 0,
        }
    term_code = cal.term_code
    now = datetime.now(timezone.utc)
    batches = _prep_rows_from_context(ctx, instance.process_code)
    if not batches:
        return {
            "published": False,
            "reason_fa": NO_OFFERINGS_REASON_FA,
            "count": 0,
            "term_code": term_code,
        }

    published_codes: set[str] = set()
    upserted = 0

    for rows, program_kind, term_number in batches:
        per_unit = _per_unit_cost_for_program(ctx, program_kind)
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = _row_from_prep(
                row,
                program_kind=program_kind,
                term_number=term_number,
                term_code=term_code,
                per_unit_cost_rial=per_unit,
            )
            if not payload:
                continue
            code = payload["course_code"]
            key = f"{program_kind}:{term_number}:{code}"
            if key in published_codes:
                continue
            published_codes.add(key)

            stmt = select(TermCourseOffering).where(
                TermCourseOffering.term_code == term_code,
                TermCourseOffering.course_code == code,
                TermCourseOffering.program_kind == program_kind,
                TermCourseOffering.term_number == term_number,
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing:
                for field, val in payload.items():
                    setattr(existing, field, val)
                existing.is_active = True
                existing.published_at = now
                existing.source_process_instance_id = instance.id
            else:
                db.add(
                    TermCourseOffering(
                        id=uuid.uuid4(),
                        **payload,
                        is_active=True,
                        published_at=now,
                        source_process_instance_id=instance.id,
                    )
                )
            upserted += 1

    await publish_term_tuition_from_prep(db, ctx, published_by=published_by)
    await db.flush()

    return {
        "published": upserted > 0,
        "count": upserted,
        "term_code": term_code,
        "reason_fa": "" if upserted > 0 else NO_OFFERINGS_REASON_FA,
    }


async def list_offerings(
    db: AsyncSession,
    *,
    term_code: Optional[str] = None,
    program_kind: Optional[str] = None,
    term_number: Optional[int] = None,
    active_only: bool = True,
) -> list[TermCourseOffering]:
    if not term_code:
        cal = await get_active_calendar(db)
        term_code = cal.term_code if cal else None
    if not term_code:
        return []
    stmt = select(TermCourseOffering).where(TermCourseOffering.term_code == term_code)
    if active_only:
        stmt = stmt.where(TermCourseOffering.is_active.is_(True))
    if program_kind:
        stmt = stmt.where(TermCourseOffering.program_kind == program_kind)
    if term_number is not None:
        stmt = stmt.where(TermCourseOffering.term_number == term_number)
    stmt = stmt.order_by(
        TermCourseOffering.term_number,
        TermCourseOffering.course_name_fa,
    )
    return list((await db.execute(stmt)).scalars().all())


def _prereq_codes_for_offering(row: TermCourseOffering) -> list[str]:
    stored = row.prerequisite_codes if isinstance(row.prerequisite_codes, list) else []
    codes = [normalize_legacy_course_code(str(c).strip()) for c in stored if str(c).strip()]
    if codes:
        return codes
    catalog = get_catalog_course(row.course_code) or get_catalog_course(row.course_name_fa or "")
    raw = (catalog or {}).get("prerequisite_codes") or []
    if not isinstance(raw, list):
        return []
    return [normalize_legacy_course_code(str(c).strip()) for c in raw if str(c).strip()]


def offering_to_option(
    row: TermCourseOffering,
    *,
    live_per_unit_rial: Optional[int] = None,
) -> dict[str, Any]:
    opt: dict[str, Any] = {
        "value": row.course_code,
        "label_fa": row.course_name_fa,
        "day": row.day,
        "time_text": row.time_text,
        "classroom_location": row.classroom_location,
        "instructor_name": row.instructor_name,
        "teaching_assistant_name": row.teaching_assistant_name,
        "units": row.units,
        "prerequisite_codes": _prereq_codes_for_offering(row),
        "track": row.track,
    }
    try:
        units = parse_positive_int(row.units)
        live = parse_positive_int(live_per_unit_rial)
        stored = parse_positive_int(row.per_unit_cost_rial)
        unit_cost = live or stored
        if units and unit_cost:
            opt["line_amount_rial"] = units * unit_cost
            opt["per_unit_cost_rial"] = unit_cost
    except (TypeError, ValueError):
        pass
    return canonicalize_course_option(opt)


async def get_offering_options(
    db: AsyncSession,
    *,
    program_kind: str,
    term_number: int,
    term_code: Optional[str] = None,
) -> list[dict[str, Any]]:
    rows = await list_offerings(
        db,
        term_code=term_code,
        program_kind=program_kind,
        term_number=term_number,
    )
    live = await _live_per_unit_rial(db, program_kind)
    return [offering_to_option(r, live_per_unit_rial=live) for r in rows]


async def get_offering_by_code(
    db: AsyncSession,
    course_code: str,
    *,
    term_code: Optional[str] = None,
) -> Optional[TermCourseOffering]:
    code = normalize_legacy_course_code(course_code)
    if not term_code:
        cal = await get_active_calendar(db)
        term_code = cal.term_code if cal else None
    if not term_code:
        return None
    stmt = (
        select(TermCourseOffering)
        .where(
            TermCourseOffering.term_code == term_code,
            TermCourseOffering.course_code == code,
            TermCourseOffering.is_active.is_(True),
        )
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row:
        return row
    # try legacy code directly
    if code != course_code:
        stmt2 = (
            select(TermCourseOffering)
            .where(
                TermCourseOffering.term_code == term_code,
                TermCourseOffering.course_code == course_code,
                TermCourseOffering.is_active.is_(True),
            )
            .limit(1)
        )
        return (await db.execute(stmt2)).scalar_one_or_none()
    return None


async def has_published_offerings(
    db: AsyncSession,
    *,
    program_kind: str = "introductory",
    term_number: int = 1,
    term_code: Optional[str] = None,
) -> bool:
    rows = await list_offerings(
        db,
        term_code=term_code,
        program_kind=program_kind,
        term_number=term_number,
    )
    return len(rows) > 0


async def build_term_offerings_response(
    db: AsyncSession,
    *,
    program_kind: str,
    term_number: int,
    term_code: Optional[str] = None,
) -> dict[str, Any]:
    if not term_code:
        cal = await get_active_calendar(db)
        term_code = cal.term_code if cal else None
    options = await get_offering_options(
        db,
        program_kind=program_kind,
        term_number=term_number,
        term_code=term_code,
    )
    return {
        "term_code": term_code,
        "program_kind": program_kind,
        "term_number": term_number,
        "offerings": options,
        "published": len(options) > 0,
        "reason_fa": "" if options else NO_OFFERINGS_REASON_FA,
    }


def _filter_by_admission_kind(
    options: list[dict[str, Any]],
    ctx: dict[str, Any],
    *,
    term_number: int,
) -> tuple[list[dict[str, Any]], Optional[int], Optional[str]]:
    from app.meta.course_selection_validation import resolve_admission_kind

    kind = resolve_admission_kind(ctx)
    if not kind:
        return (
            [],
            None,
            "نتیجهٔ مصاحبه در پرونده ثبت نشده است؛ تا زمان ثبت نتیجه توسط مصاحبه‌گر انتخاب درس ممکن نیست.",
        )
    if not options:
        return ([], None, NO_OFFERINGS_REASON_FA)
    options = [
        canonicalize_course_option(o) for o in options if isinstance(o, dict)
    ]

    def _parse_allowed_count() -> Optional[int]:
        n = ctx.get("allowed_course_count")
        if n is None or n == "":
            return None
        try:
            x = int(n)
            return x if x > 0 else None
        except (TypeError, ValueError):
            return None

    if kind == "single_course":
        allowed_codes = {
            normalize_legacy_course_code(c) for c in single_course_allowed_codes(term_number) if c
        }
        if not allowed_codes:
            return ([], 1, SINGLE_COURSE_MISSING_REASON_FA)
        pick = [o for o in options if _option_code(o) in allowed_codes]
        if not pick:
            return ([], 1, SINGLE_COURSE_MISSING_REASON_FA)
        coreq_codes: set[str] = set()
        for o in pick:
            for c in o.get("corequisite_codes") or []:
                n = normalize_legacy_course_code(str(c))
                if n:
                    coreq_codes.add(n)
        extras = [
            o
            for o in options
            if _option_code(o) in coreq_codes and _option_code(o) not in allowed_codes
        ]
        combined = list(pick) + extras
        return (combined, max(1, len(combined)), None)

    cap = _parse_allowed_count()
    max_select = cap if cap is not None else len(options)
    return (list(options), max_select, None)


def _filter_by_prerequisites(
    options: list[dict[str, Any]],
    completed_codes: set[str],
    failed_codes: Optional[set[str]] = None,
) -> list[dict[str, Any]]:
    from app.services.course_prerequisite_service import partition_options_by_prerequisites

    allowed, _blocked = partition_options_by_prerequisites(
        options,
        set(completed_codes or []),
        set(failed_codes or []),
    )
    return allowed


async def merge_offerings_into_instance_context(
    db: AsyncSession,
    process_code: str,
    ctx: dict[str, Any],
    *,
    student: Optional[Any] = None,
    state_codes: Optional[list] = None,
) -> dict[str, Any]:
    """Attach available courses from published term offerings to process context."""
    spec = _PROCESS_PROGRAM_TERM.get(process_code)
    if not spec:
        return dict(ctx or {})
    program_kind, term_number = spec
    from app.services.admission_type_service import overlay_admission_on_context

    out = overlay_admission_on_context(ctx, student, state_codes=state_codes)
    cal = await get_active_calendar(db)
    term_code = cal.term_code if cal else out.get("term_code")
    options = await get_offering_options(
        db,
        program_kind=program_kind,
        term_number=term_number,
        term_code=term_code,
    )

    from app.services.course_prerequisite_service import (
        classify_student_course_progress,
        partition_options_by_prerequisites,
    )

    passed, failed = classify_student_course_progress(out, student)
    options, blocked = partition_options_by_prerequisites(options, passed, failed)

    filtered, max_select, hint = _filter_by_admission_kind(
        options, out, term_number=term_number
    )
    from app.meta.course_selection_validation import resolve_admission_kind

    kind = resolve_admission_kind(out)
    allowed_codes = {
        normalize_legacy_course_code(c) for c in single_course_allowed_codes(term_number) if c
    }
    if kind == "single_course" and allowed_codes:
        blocked = [
            b
            for b in blocked
            if normalize_legacy_course_code(str(b.get("value") or "")) in allowed_codes
        ]
    codes = [o["value"] for o in filtered]
    labels = {o["value"]: o["label_fa"] for o in filtered}

    out["term_code"] = term_code
    out["available_course_options"] = filtered
    out["available_courses"] = codes
    out["blocked_course_options"] = blocked
    out["course_labels"] = labels
    out["course_selection_max"] = max_select
    if hint:
        out["course_selection_hint_fa"] = hint
    elif not codes:
        out["course_selection_hint_fa"] = NO_OFFERINGS_REASON_FA
    else:
        out.pop("course_selection_hint_fa", None)

    lms = dict(out.get("lms") or {})
    lms["available_courses"] = codes
    lms["available_course_options"] = filtered
    lms["available_loaded_at"] = datetime.now(timezone.utc).isoformat()
    if not codes:
        lms["unavailable_reason_fa"] = out.get("course_selection_hint_fa") or NO_OFFERINGS_REASON_FA
    else:
        lms.pop("unavailable_reason_fa", None)
    out["lms"] = lms
    out["prep_source"] = "term_course_offerings"
    return out


async def resolve_program_term_for_process(
    process_code: str,
    student: Optional[Any] = None,
) -> Optional[tuple[str, int]]:
    if process_code in _PROCESS_PROGRAM_TERM:
        return _PROCESS_PROGRAM_TERM[process_code]
    if student is not None:
        ct = getattr(student, "course_type", None)
        term = int(getattr(student, "current_term", None) or 1)
        if ct == "comprehensive":
            return ("comprehensive", max(term, 3))
        return ("introductory", term)
    return None


def get_term_tuition_from_calendar(cal: Any) -> dict[str, Any]:
    if cal is None:
        return {}
    extra = cal.extra_data or {}
    tuition = extra.get("tuition") or {}
    return tuition if isinstance(tuition, dict) else {}


async def _live_per_unit_rial(db: AsyncSession, program_kind: str) -> Optional[int]:
    """نرخ هر واحد از پنل مالی / تقویم فعال — نه مقدار کهنه روی ردیف ارائه."""
    key = f"per_unit_cost_{program_kind}"
    cal = await get_active_calendar(db)
    n = parse_positive_int(get_term_tuition_from_calendar(cal).get(key))
    if n >= 1000:
        return n
    from app.services.financial_program_defaults_service import get_effective_financial_program_defaults

    fd = await get_effective_financial_program_defaults(db)
    n = parse_positive_int(fd.get(key))
    return n if n > 0 else None


def _options_by_code_from_ctx(ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    blobs: list[Any] = []
    if isinstance(ctx.get("available_course_options"), list):
        blobs.extend(ctx["available_course_options"])
    lms = ctx.get("lms") if isinstance(ctx.get("lms"), dict) else {}
    if isinstance(lms.get("available_course_options"), list):
        blobs.extend(lms["available_course_options"])
    for opt in blobs:
        if not isinstance(opt, dict):
            continue
        code = normalize_legacy_course_code(str(opt.get("value") or opt.get("course_code") or "").strip())
        if code:
            out[code] = opt
    return out


async def resolve_registration_fees(
    db: AsyncSession,
    process_code: str,
    ctx: dict[str, Any],
    current_state: str,
) -> dict[str, Any]:
    """Resolve interview fee and tuition from prep-published calendar tuition."""
    from app.services.financial_program_defaults_service import get_effective_financial_program_defaults

    fd = await get_effective_financial_program_defaults(db)
    cal = await get_active_calendar(db)
    tuition = get_term_tuition_from_calendar(cal)
    spec = _PROCESS_PROGRAM_TERM.get(process_code)
    program_kind = spec[0] if spec else "introductory"

    interview_key = f"interview_fee_{program_kind}"
    per_unit_key = f"per_unit_cost_{program_kind}"

    interview_fee = tuition.get(interview_key)
    per_unit = tuition.get(per_unit_key)
    fee_source = "site_defaults"

    try:
        interview_rial = int(interview_fee) if interview_fee is not None else None
    except (TypeError, ValueError):
        interview_rial = None
    try:
        per_unit_rial = int(per_unit) if per_unit is not None else None
    except (TypeError, ValueError):
        per_unit_rial = None

    # منبع مشترک داشبورد مالی / آماده‌سازی ترم (اگر تقویم هنوز خالی باشد)
    if not interview_rial or interview_rial < 1000:
        try:
            fd_iv = int(fd.get(interview_key) or 0)
        except (TypeError, ValueError):
            fd_iv = 0
        if fd_iv >= 1000:
            interview_rial = fd_iv
            fee_source = "term_prep"
    if not per_unit_rial or per_unit_rial <= 0:
        try:
            fd_pu = int(fd.get(per_unit_key) or 0)
        except (TypeError, ValueError):
            fd_pu = 0
        if fd_pu > 0:
            per_unit_rial = fd_pu

    if interview_rial and interview_rial >= 1000 and tuition.get(interview_key) is not None:
        fee_source = "term_prep"
    elif interview_rial and interview_rial >= 1000 and int(fd.get(interview_key) or 0) >= 1000:
        fee_source = "term_prep"
    elif current_state == "interview_payment":
        interview_rial = int(fd["registration_interview_fee_rial"])

    selected_codes = selected_course_codes_for_tuition(process_code, ctx)

    tuition_toman: Optional[float] = None
    tuition_total_rial: Optional[int] = None
    tuition_lines: list[dict[str, Any]] = []
    if per_unit_rial and per_unit_rial > 0 and selected_codes:
        from app.services.course_committee_roster_service import (
            catalog_units_for_course,
            get_catalog_course,
        )

        by_code: dict[str, Any] = {}
        if cal:
            spec = _PROCESS_PROGRAM_TERM.get(process_code, (program_kind, 1))
            _, term_number = spec
            offerings = await list_offerings(
                db,
                term_code=cal.term_code,
                program_kind=program_kind,
                term_number=term_number,
            )
            by_code = {normalize_legacy_course_code(o.course_code): o for o in offerings}
        options_by_code = _options_by_code_from_ctx(ctx)
        total_rial = 0
        live_unit_cost = int(per_unit_rial)
        for code in selected_codes:
            off = by_code.get(code)
            opt = options_by_code.get(code) or {}
            units = parse_positive_int(getattr(off, "units", None) if off is not None else None)
            if units < 1:
                units = parse_positive_int(opt.get("units"))
            if units < 1:
                units = catalog_units_for_course(code, default=1)
            if units < 1:
                units = 1
            # نرخ پنل مالی / تقویم فعال بر نرخ کهنهٔ ارائه اولویت دارد
            unit_cost = live_unit_cost
            if unit_cost <= 0:
                unit_cost = parse_positive_int(
                    getattr(off, "per_unit_cost_rial", None) if off is not None else None
                ) or parse_positive_int(opt.get("per_unit_cost_rial"))
            if off is not None:
                name_fa = off.course_name_fa or code
            else:
                catalog = get_catalog_course(code)
                name_fa = (
                    str(opt.get("label_fa") or (catalog or {}).get("label_fa") or code).strip()
                    or code
                )
            line_rial = units * int(unit_cost)
            total_rial += line_rial
            tuition_lines.append(
                {
                    "course_code": code,
                    "course_name_fa": name_fa,
                    "units": units,
                    "per_unit_cost_rial": int(unit_cost),
                    "line_amount_rial": line_rial,
                }
            )
        if total_rial > 0:
            tuition_total_rial = total_rial
            tuition_toman = total_rial / 10.0
            fee_source = "term_prep"
    if tuition_toman is None:
        tuition_toman = float(fd["registration_tuition_invoice_toman"])
        if not per_unit_rial:
            fee_source = "site_defaults"
        try:
            tuition_total_rial = int(round(float(tuition_toman) * 10))
        except (TypeError, ValueError):
            tuition_total_rial = None

    return {
        "registration_interview_fee_rial": interview_rial or int(fd["registration_interview_fee_rial"]),
        "registration_tuition_invoice_toman": tuition_toman,
        "tuition_total_rial": tuition_total_rial,
        "tuition_lines": tuition_lines,
        "fee_source": fee_source,
        "tuition_missing": not per_unit_rial and fee_source == "site_defaults",
        "tuition_reason_fa": NO_TUITION_REASON_FA if not per_unit_rial else "",
    }
