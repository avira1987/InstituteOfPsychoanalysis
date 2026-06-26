"""Pre-fill operator/student form fields from LMS and related context."""
from __future__ import annotations

from typing import Any, Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.operational_models import ProcessInstance, Student


def _ctx(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _course_name_from_ctx(context: dict[str, Any]) -> str:
    return (
        str(context.get("course_name") or "")
        or str(context.get("lesson_name") or "")
        or str((context.get("course") or {}).get("name_fa") if isinstance(context.get("course"), dict) else "")
        or ""
    )


def _build_students_grades_row(student: Student, course_name: str = "") -> list[dict[str, Any]]:
    extra = _ctx(student.extra_data)
    lms = _ctx(extra.get("lms"))
    enrolled = lms.get("enrolled_courses") or lms.get("course_links") or []
    rows: list[dict[str, Any]] = []
    user_label = student.student_code or str(student.id)
    if isinstance(enrolled, list) and enrolled:
        for entry in enrolled:
            if isinstance(entry, dict):
                cn = entry.get("course_name") or entry.get("name_fa") or entry.get("code") or course_name
                grade = entry.get("grade")
                status = entry.get("status_fa") or entry.get("status") or ""
                rows.append({
                    "student_name": user_label,
                    "student_id": str(student.id),
                    "grade": grade if grade is not None else "",
                    "course_name": cn or course_name,
                    "status": status,
                })
            elif entry:
                rows.append({
                    "student_name": user_label,
                    "student_id": str(student.id),
                    "grade": "",
                    "course_name": str(entry),
                })
    if not rows:
        rows.append({
            "student_name": user_label,
            "student_id": str(student.id),
            "grade": "",
            "course_name": course_name or "—",
        })
    return rows


def _build_attendance_rows(context: dict[str, Any], student: Optional[Student]) -> list[dict[str, Any]]:
    existing = context.get("attendance_rows") or context.get("students_attendance")
    if isinstance(existing, list) and existing:
        return list(existing)
    course = _course_name_from_ctx(context)
    if student:
        return [{
            "student_name": student.student_code or str(student.id),
            "student_id": str(student.id),
            "status": "present",
            "course_name": course,
        }]
    return []


TERMINATION_REASON_LABELS: dict[int, str] = {
    1: "۱ — دانشجو ترجیح می‌دهد درمانگر را تغییر دهد",
    2: "۲ — درمانگر ترجیح می‌دهد دانشجو با درمانگر دیگر ادامه دهد",
    3: "۳ — درمان تحلیلی نامناسب (پس از مشورت با کمیسیون تخصصی)",
    4: "۴ — دانشجو مناسب درمان تحلیلی نیست (درمانگر دوم/سوم/...)",
}


def _termination_reason_display(context: dict[str, Any]) -> str:
    raw = context.get("termination_reason_code") or context.get("reason_code")
    if raw is None:
        return "—"
    try:
        code = int(raw)
    except (TypeError, ValueError):
        return str(raw)
    return TERMINATION_REASON_LABELS.get(code, str(raw))


def _entry_source_display(context: dict[str, Any]) -> str:
    entry = context.get("entry_reason") or context.get("reason")
    label = context.get("label")
    if label:
        return str(label)
    if entry == "ineligibility_specialized_commission":
        return "ارجاع از کمیسیون تخصصی — عدم صلاحیت تخصصی"
    if entry == "termination_reason_4" or context.get("termination_reason_code") == 4:
        return "مسیر انضباطی — علت ۴ (گزارش درمانگر)"
    if context.get("parent_process_code") == "specialized_commission_review":
        return "ارجاع از کمیسیون تخصصی — عدم صلاحیت تخصصی"
    if context.get("parent_process_code") == "therapy_early_termination":
        return "ارجاع مستقیم از فرایند قطع زودرس درمان"
    return str(entry or "—")


def _nezarat_recommendation_display(context: dict[str, Any], student: Optional[Student]) -> str:
    text = context.get("nezarat_recommendation_fa") or context.get("recommendation_fa")
    if text:
        return str(text)
    if student:
        extra = _ctx(student.extra_data)
        conf = _ctx(extra.get("confidential"))
        nez = conf.get("nezarat_recommendation")
        if isinstance(nez, dict) and nez.get("text_fa"):
            return str(nez["text_fa"])
    code = context.get("nezarat_recommendation_code")
    if code == "continue":
        return "پیشنهاد الف — ادامه آموزش"
    if code == "terminate":
        return "پیشنهاد ب — قطع آموزش"
    return "—"


def _commission_opinion_display(context: dict[str, Any], student: Optional[Student]) -> str:
    text = (
        context.get("commission_opinion_fa")
        or context.get("commission_opinion_display")
    )
    if text:
        return str(text)
    if student:
        extra = _ctx(student.extra_data)
        results = extra.get("commission_results") or []
        if isinstance(results, list) and results:
            last = results[-1]
            if isinstance(last, dict):
                res = last.get("result")
                if res == "eligibility_confirmed":
                    return "تأیید صلاحیت توسط کمیسیون"
                if res:
                    return f"نتیجه کمیسیون: {res}"
    if context.get("entry_reason") == "ineligibility_specialized_commission":
        return "رد صلاحیت — ارجاع به کمیته‌ها"
    return "—"


async def _load_parent_context(
    db: AsyncSession,
    context_data: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(context_data)
    parent_id = context_data.get("parent_instance_id")
    if not parent_id:
        return merged
    try:
        parent = await db.get(ProcessInstance, uuid.UUID(str(parent_id)))
    except (ValueError, TypeError):
        return merged
    if not parent:
        return merged
    pctx = _ctx(parent.context_data)
    for key in (
        "termination_reason_code",
        "termination_note",
        "reason_code",
        "commission_opinion_fa",
        "commission_meeting_notes_fa",
        "entry_reason",
        "label",
        "reason",
    ):
        if pctx.get(key) is not None and merged.get(key) is None:
            merged[key] = pctx[key]
    if merged.get("parent_process_code") is None:
        merged["parent_process_code"] = parent.process_code
    gp_id = pctx.get("parent_instance_id")
    if gp_id and merged.get("termination_reason_code") is None:
        try:
            gp = await db.get(ProcessInstance, uuid.UUID(str(gp_id)))
        except (ValueError, TypeError):
            gp = None
        if gp:
            gctx = _ctx(gp.context_data)
            for key in ("termination_reason_code", "termination_note", "reason_code"):
                if gctx.get(key) is not None and merged.get(key) is None:
                    merged[key] = gctx[key]
    return merged


async def apply_pre_filled_fields(
    db: AsyncSession,
    process_code: str,
    state_code: str,
    context_data: dict[str, Any],
    *,
    student_id: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
    """Merge suggested field values for forms at the given state."""
    from app.services.semester_prep_service import apply_pre_filled_fields as semester_prefill
    from app.meta.process_forms import get_process_forms

    out = await semester_prefill(db, process_code, state_code, context_data)
    forms = get_process_forms(process_code, state_code=state_code)
    field_names: set[str] = set()
    for form in forms:
        for field in form.get("fields") or []:
            if isinstance(field, dict) and field.get("name"):
                field_names.add(str(field["name"]))

    student: Optional[Student] = None
    if student_id:
        student = await db.get(Student, student_id)

    course_name = _course_name_from_ctx({**context_data, **out})

    if process_code.endswith("_course_completion") and state_code == "grades_entry":
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = course_name or "درس جاری"
        if "students_grades" in field_names and not out.get("students_grades") and student:
            out["students_grades"] = _build_students_grades_row(student, course_name)

    if process_code == "class_attendance" and state_code == "attendance_list_ready":
        if "lesson_name" in field_names and not out.get("lesson_name"):
            out["lesson_name"] = course_name or context_data.get("lesson_name") or "—"
        if "students_attendance" in field_names and not out.get("students_attendance"):
            out["students_attendance"] = _build_attendance_rows(context_data, student)

    if process_code == "student_instructor_evaluation" and state_code == "evaluation_open":
        lms_course = course_name
        if student and not out.get("course_name"):
            extra = _ctx(student.extra_data)
            lms = _ctx(extra.get("lms"))
            courses = lms.get("enrolled_courses") or []
            if courses and isinstance(courses[0], dict):
                lms_course = courses[0].get("course_name") or courses[0].get("name_fa") or lms_course
            out.setdefault("course_name", lms_course or "درس جاری")
            out.setdefault("instructor_name", context_data.get("instructor_name") or "مدرس")

    if process_code == "educational_leave" and state_code in ("committee_review", "deputy_alerted"):
        merged = {**context_data, **out}
        if "leave_terms_display" in field_names and not out.get("leave_terms_display"):
            lt = merged.get("leave_terms")
            try:
                n = int(lt)
                out["leave_terms_display"] = "یک ترم" if n == 1 else "دو ترم" if n == 2 else str(lt or "—")
            except (TypeError, ValueError):
                out["leave_terms_display"] = str(lt or "—")
        if "clinical_status_display" in field_names and not out.get("clinical_status_display"):
            if student is not None:
                out["clinical_status_display"] = "انترن" if student.is_intern else "غیر انترن"
            else:
                out["clinical_status_display"] = merged.get("clinical_status_display") or "—"

    if process_code in ("committees_review", "specialized_commission_review"):
        merged = await _load_parent_context(db, {**context_data, **out})
        if "termination_reason_display" in field_names and not out.get("termination_reason_display"):
            out["termination_reason_display"] = _termination_reason_display(merged)
        if "termination_note_display" in field_names and not out.get("termination_note_display"):
            note = merged.get("termination_note")
            out["termination_note_display"] = str(note) if note else "—"
        if process_code == "committees_review":
            if "entry_source_display" in field_names and not out.get("entry_source_display"):
                out["entry_source_display"] = _entry_source_display(merged)
            if "commission_opinion_display" in field_names and not out.get("commission_opinion_display"):
                out["commission_opinion_display"] = _commission_opinion_display(merged, student)
            if state_code == "education_review":
                if "supervision_recommendation_display" in field_names and not out.get("supervision_recommendation_display"):
                    out["supervision_recommendation_display"] = _nezarat_recommendation_display(
                        {**merged, **context_data, **out}, student
                    )

    return out
