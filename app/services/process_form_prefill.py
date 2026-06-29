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


def _compute_attendance_score(absence_count: Any) -> int:
    try:
        n = int(absence_count or 0)
    except (TypeError, ValueError):
        n = 0
    if n < 0:
        n = 0
    return max(0, 8 - 2 * n)


def _build_ta_attendance_grades_rows(roster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in roster:
        if not isinstance(entry, dict):
            continue
        absence = entry.get("absence_count") or entry.get("term_absences") or 0
        rows.append({
            "student_id": str(entry.get("student_id") or ""),
            "student_name": entry.get("name_fa") or entry.get("student_name") or entry.get("student_code") or "",
            "participation_score": entry.get("participation_score") or entry.get("grade") or "",
            "attendance_score": _compute_attendance_score(absence),
            "grade": entry.get("grade") or entry.get("participation_score") or "",
        })
    return rows


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


def _build_referral_rows_for_state(state_code: str, rows: list) -> list[dict[str, Any]]:
    """ردیف‌های جدول را برای مرحلهٔ فعلی با فیلدهای مناسب برمی‌گرداند."""
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        base = {
            "row_id": str(row.get("row_id") or f"row-{i + 1}"),
            "patient_name": str(row.get("patient_name") or "").strip(),
            "patient_phone": str(row.get("patient_phone") or "").strip(),
        }
        if not base["patient_name"]:
            continue
        if state_code == "student_patient_log":
            base["contacted"] = bool(row.get("contacted"))
            base["contact_notes"] = str(row.get("contact_notes") or "").strip()
        elif state_code == "general_therapy_committee_review":
            base["contact_notes"] = str(row.get("contact_notes") or "").strip()
            base["committee_contacted"] = bool(row.get("committee_contacted"))
            base["referral_notes"] = str(row.get("referral_notes") or "").strip()
            base["replacement_therapist"] = str(row.get("replacement_therapist") or "").strip()
        elif state_code == "coordination_followup":
            base["replacement_therapist"] = str(row.get("replacement_therapist") or "").strip()
            base["referral_notes"] = str(row.get("referral_notes") or "").strip()
            base["followup_done"] = bool(row.get("followup_done"))
        out.append(base)
    return out

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

    if process_code == "live_supervision_course_completion":
        merged = {**context_data, **out}
        course_code = (
            merged.get("course_code")
            or merged.get("course_id")
            or merged.get("lesson_course_label")
            or course_name
            or "live_supervision"
        )
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = str(course_code)
        if state_code == "mirror_implementation_pending":
            if "mirror_session_index" in field_names and not out.get("mirror_session_index"):
                out["mirror_session_index"] = merged.get("mirror_session_index") or merged.get("last_mirror_session_index") or "—"
            if "mirror_session_date" in field_names and not out.get("mirror_session_date"):
                out["mirror_session_date"] = merged.get("mirror_session_date") or "—"
        if state_code == "mirror_eval_pending":
            if student and "student_name" in field_names and not out.get("student_name"):
                out["student_name"] = student.student_code or str(student.id)
        if state_code == "final_eval_pending":
            if student and "student_name" in field_names and not out.get("student_name"):
                out["student_name"] = student.student_code or str(student.id)
        if state_code == "sessions_in_progress" and student:
            from app.services.live_supervision_course_service import live_supervision_bucket

            lms = _ctx(student.extra_data).get("lms") or {}
            bucket = live_supervision_bucket(lms, str(course_code))
            out.setdefault("live_supervision_normal_count", bucket.get("normal_count", 0))
            out.setdefault("live_supervision_mirror_count", bucket.get("mirror_count", 0))

    if process_code == "group_supervision_course_completion":
        merged = {**context_data, **out}
        course_code = (
            merged.get("course_code")
            or merged.get("course_id")
            or merged.get("lesson_course_label")
            or course_name
        )
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = str(course_code or course_name or "سوپرویژن گروهی")
        if state_code == "qualitative_eval_pending" and student:
            if "student_name" in field_names and not out.get("student_name"):
                out["student_name"] = student.student_code or str(student.id)
        if state_code == "ta_evaluation_entry":
            if "ta_name" in field_names and not out.get("ta_name"):
                out["ta_name"] = merged.get("ta_name") or "—"
        if state_code in ("session_18_pass_fail_entry", "ta_evaluation_entry"):
            roster_code = str(course_code or "")
            if roster_code and "students_grades" in field_names and not out.get("students_grades"):
                from app.services.instructor_course_roster_service import get_course_roster
                from app.services.group_supervision_course_completion_service import (
                    enrich_pass_fail_row,
                    group_supervision_hours_total,
                )

                roster = await get_course_roster(db, roster_code)
                rows = []
                for entry in roster:
                    if (entry.get("role") or "student") == "teaching_assistant":
                        continue
                    sid = entry.get("student_id")
                    hours = 0.0
                    if sid:
                        st_row = await db.get(Student, sid)
                        if st_row:
                            hours = group_supervision_hours_total(_ctx(st_row.extra_data))
                    rows.append(enrich_pass_fail_row({
                        "student_id": str(sid) if sid else "",
                        "student_name": entry.get("name_fa") or str(sid),
                        "pass_fail": "PASS",
                    }, hours))
                if rows:
                    out["students_grades"] = rows

    if process_code == "theory_course_completion":
        merged = {**context_data, **out}
        course_code = (
            merged.get("course_code")
            or merged.get("course_id")
            or merged.get("lesson_course_label")
            or course_name
        )
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = str(course_code or course_name or "درس تئوری")
        if state_code == "qualitative_eval_pending" and student:
            if "student_name" in field_names and not out.get("student_name"):
                out["student_name"] = student.student_code or str(student.id)
        if state_code == "session_18_entry":
            roster_code = str(course_code or "")
            if roster_code and "students_grades" in field_names and not out.get("students_grades"):
                from app.services.instructor_course_roster_service import get_course_roster
                from app.services.theory_course_completion_service import enrich_grade_row

                roster = await get_course_roster(db, roster_code)
                rows = []
                for entry in roster:
                    if (entry.get("role") or "student") == "teaching_assistant":
                        continue
                    sid = entry.get("student_id")
                    base = {**entry, "student_id": sid, "student_name": entry.get("name_fa") or sid}
                    rows.append(enrich_grade_row(base, absence_count=entry.get("absence_count") or 0))
                if rows:
                    out["students_grades"] = rows

    if process_code.endswith("_course_completion") and state_code == "grades_entry":
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = course_name or "درس جاری"
        if "students_grades" in field_names and not out.get("students_grades") and student:
            out["students_grades"] = _build_students_grades_row(student, course_name)

    if process_code == "film_observation_course_completion" and state_code == "grades_entry":
        if "final_report_pdf" in field_names and not out.get("final_report_pdf"):
            existing = context_data.get("final_report_pdf")
            if existing:
                out["final_report_pdf"] = existing
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = (
                course_name
                or context_data.get("course_name")
                or context_data.get("lesson_name")
                or "درس جاری"
            )

    if process_code.endswith("_ta_attendance_completion") and state_code == "grades_entry":
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = course_name or "درس جاری"
        if "students_grades" in field_names and not out.get("students_grades"):
            from app.services.instructor_course_roster_service import get_course_roster

            roster_course_code = (
                context_data.get("course_code")
                or context_data.get("lesson_course_label")
                or course_name
            )
            if roster_course_code:
                agg = await get_course_roster(db, str(roster_course_code))
                if agg:
                    out["students_grades"] = _build_ta_attendance_grades_rows(agg)
            if not out.get("students_grades") and student:
                out["students_grades"] = _build_students_grades_row(student, course_name)

    if process_code == "class_session_cancellation" and state_code == "cancellation_request":
        merged = {**context_data, **out}
        for key in (
            "lesson_id",
            "session_to_cancel",
            "makeup_date",
            "makeup_time",
            "makeup_summary_fa",
            "cancellation_ordinal",
            "cancellation_ordinal_fa",
            "usual_class_time",
            "term_week_makeup_label",
            "assignable_courses",
            "cancellable_sessions",
            "upcoming_cancellable_sessions",
        ):
            if key in field_names and merged.get(key) not in (None, "") and not out.get(key):
                out[key] = merged[key]

    if process_code == "class_attendance" and state_code == "attendance_list_ready":
        if "lesson_name" in field_names and not out.get("lesson_name"):
            out["lesson_name"] = course_name or context_data.get("lesson_name") or "—"
        if "students_attendance" in field_names and not out.get("students_attendance"):
            rows = _build_attendance_rows(context_data, student)
            if not rows:
                from app.services.instructor_course_roster_service import (
                    get_course_roster,
                    roster_to_attendance_rows,
                )
                course_code = (
                    context_data.get("course_code")
                    or context_data.get("lesson_course_label")
                    or course_name
                )
                if course_code:
                    agg = await get_course_roster(db, str(course_code))
                    rows = roster_to_attendance_rows(agg)
            out["students_attendance"] = rows
        if "attendees" in field_names and not out.get("attendees"):
            out["attendees"] = out.get("students_attendance") or _build_attendance_rows(context_data, student)

    if process_code == "student_instructor_evaluation" and state_code == "evaluation_open":
        if student and "enrolled_courses_eval" in field_names and not out.get("enrolled_courses_eval"):
            from app.services.student_instructor_evaluation_service import list_evaluable_courses

            term_code = str(context_data.get("term_code") or "").strip() or None
            out["enrolled_courses_eval"] = list_evaluable_courses(student, term_code)
        if student and not out.get("course_name"):
            extra = _ctx(student.extra_data)
            lms = _ctx(extra.get("lms"))
            courses = lms.get("enrolled_courses") or []
            lms_course = course_name
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

    if process_code == "full_education_leave":
        merged = {**context_data, **out}
        if state_code in ("committee_review", "deputy_alerted"):
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
        if state_code == "therapist_assignment":
            from app.services.full_education_leave_service import build_leave_context

            if student is not None:
                leave_ctx = await build_leave_context(db, student.id, merged)
                merged = {**merged, **leave_ctx}
            if "student_name_display" in field_names and not out.get("student_name_display"):
                out["student_name_display"] = merged.get("student_name_display") or "—"
            if "current_therapist_display" in field_names and not out.get("current_therapist_display"):
                out["current_therapist_display"] = merged.get("current_therapist_display") or "—"
            if "current_session_times_display" in field_names and not out.get("current_session_times_display"):
                out["current_session_times_display"] = merged.get("current_session_times_display") or "—"
            if "therapist_deadline_display" in field_names and not out.get("therapist_deadline_display"):
                out["therapist_deadline_display"] = merged.get("therapist_deadline_display") or "—"

    if process_code == "upgrade_to_educational_therapist":
        merged = {**context_data, **out}
        if student is not None:
            from app.services.educational_therapist_upgrade_service import build_et_upgrade_context

            et_ctx = await build_et_upgrade_context(db, student.id, merged)
            merged = {**merged, **et_ctx}
        if "et_eligibility_summary_fa" in field_names and not out.get("et_eligibility_summary_fa"):
            out["et_eligibility_summary_fa"] = merged.get("et_eligibility_summary_fa") or "—"

    if process_code == "upgrade_to_ta":
        merged = {**context_data, **out}
        if student is not None:
            from app.services.ta_upgrade_service import build_ta_upgrade_context

            ta_ctx = await build_ta_upgrade_context(db, student.id, merged)
            merged = {**merged, **ta_ctx}
        if "ta_eligibility_summary_fa" in field_names and not out.get("ta_eligibility_summary_fa"):
            out["ta_eligibility_summary_fa"] = merged.get("ta_eligibility_summary_fa") or "—"
        if state_code == "track_selection" and "tracks" in field_names and not out.get("tracks"):
            prev = merged.get("tracks")
            if isinstance(prev, list) and prev:
                out["tracks"] = prev

    if process_code == "ta_track_change":
        merged = {**context_data, **out}
        if student is not None:
            from app.services.ta_track_change_service import build_ta_track_change_context

            ttc_ctx = await build_ta_track_change_context(db, student.id, merged)
            merged = {**merged, **ttc_ctx}
        if "current_tracks" in field_names and not out.get("current_tracks"):
            prev = merged.get("current_tracks")
            if isinstance(prev, list) and prev:
                out["current_tracks"] = prev
        if state_code == "ta_click" and not out.get("path") and merged.get("path"):
            out["path"] = merged.get("path")

    if process_code == "ta_to_assistant_faculty":
        merged = {**context_data, **out}
        if student is not None:
            from app.services.ta_to_assistant_faculty_service import build_ta_assistant_faculty_context

            taf_ctx = await build_ta_assistant_faculty_context(db, student.id, merged)
            merged = {**merged, **taf_ctx}
        if "student_name_fa" in field_names and not out.get("student_name_fa"):
            out["student_name_fa"] = merged.get("student_name_fa") or (
                student.student_code if student is not None else "—"
            )
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = merged.get("course_name_fa") or merged.get("course_name") or "—"
        if "current_analytic_rank_fa" in field_names and not out.get("current_analytic_rank_fa"):
            out["current_analytic_rank_fa"] = merged.get("current_analytic_rank_fa") or "—"
        if "ta_pass_history_fa" in field_names and not out.get("ta_pass_history_fa"):
            count = merged.get("ta_pass_count")
            out["ta_pass_history_fa"] = (
                f"{count} بار موفق به‌عنوان کمک‌مدرس (تأیید سیستمی)"
                if count is not None
                else merged.get("ta_upgrade_summary_fa") or "—"
            )

    if process_code == "supervision_interruption" and state_code == "committee_scheduling":
        merged = {**context_data, **out}
        if "student_name" in field_names and not out.get("student_name") and student is not None:
            out["student_name"] = student.student_code or str(student.id)
        if "requested_pause_range" in field_names and not out.get("requested_pause_range"):
            start = merged.get("pause_start_date")
            end = merged.get("pause_end_date")
            if start and end:
                out["requested_pause_range"] = f"{start} تا {end}"
            elif start or end:
                out["requested_pause_range"] = str(start or end)

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

    if process_code == "article_writing_completion":
        merged = {**context_data, **out}
        article_course_code = (
            merged.get("course_code")
            or merged.get("course_id")
            or merged.get("lesson_course_label")
            or course_name
            or "article_writing_case_report"
        )
        if "course_code" in field_names and not out.get("course_code"):
            out["course_code"] = str(article_course_code)
        if "enrollment_term" in field_names and not out.get("enrollment_term"):
            term = merged.get("article_enrollment_term") or merged.get("enrollment_term")
            out["enrollment_term"] = str(term) if term is not None else "—"
        if state_code == "course_active" and "students" in field_names and not out.get("students"):
            from app.services.instructor_course_roster_service import (
                get_course_roster,
                roster_to_completion_tick_rows,
            )

            roster = await get_course_roster(db, str(article_course_code))
            rows = roster_to_completion_tick_rows(roster) if roster else []
            if student and not rows:
                sid = str(student.id)
                rows = [{
                    "student_id": sid,
                    "student_name": student.student_code or sid,
                    "completed": False,
                }]
            elif student and rows:
                sid = str(student.id)
                for row in rows:
                    if str(row.get("student_id")) == sid:
                        row["completed"] = merged.get("completion_ticked") is True
            out["students"] = rows
        if state_code == "instructor_eval_pending":
            if "student_name" in field_names and not out.get("student_name") and student is not None:
                out["student_name"] = student.student_code or str(student.id)

    if process_code == "ta_essay_upload":
        merged = {**context_data, **out}
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = course_name or merged.get("course_name") or "—"
        if "session_date" in field_names and not out.get("session_date"):
            out["session_date"] = (
                merged.get("session_date")
                or merged.get("class_session_date")
                or merged.get("lesson_date")
                or "—"
            )
        if "session_number" in field_names and not out.get("session_number"):
            sn = merged.get("session_number") or merged.get("session_index")
            if sn is not None:
                out["session_number"] = sn
        if not out.get("instructor_name") and merged.get("instructor_name"):
            out["instructor_name"] = merged["instructor_name"]
        if not out.get("teaching_assistant_name"):
            ta = merged.get("teaching_assistant_name") or merged.get("teaching_assistant")
            if ta:
                out["teaching_assistant_name"] = str(ta)
        if not out.get("course_track") and merged.get("course_track"):
            out["course_track"] = merged["course_track"]

    if process_code == "mentor_private_sessions" and state_code == "instructor_click":
        merged = {**context_data, **out}
        course_code = (
            merged.get("course_id")
            or merged.get("course_code")
            or merged.get("lesson_course_label")
            or course_name
        )
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = course_name or merged.get("course_name") or str(course_code or "—")
        if "instructor_name" in field_names and not out.get("instructor_name"):
            out["instructor_name"] = merged.get("instructor_name") or "—"
        if "teaching_assistant_name" in field_names and not out.get("teaching_assistant_name"):
            ta = merged.get("teaching_assistant_name") or merged.get("teaching_assistant")
            if not ta and student is not None:
                lms = _ctx(student.extra_data).get("lms") or {}
                ta_map = lms.get("teaching_assistants_by_course") or {}
                if course_code:
                    ta = ta_map.get(str(course_code)) or ta_map.get(course_code)
            if ta:
                out["teaching_assistant_name"] = str(ta)
            elif "teaching_assistant_name" in field_names:
                out.setdefault("teaching_assistant_name", "—")
        if student is not None:
            lms = _ctx(student.extra_data).get("lms") or {}
            sessions = lms.get("course_sessions") or []
            if isinstance(sessions, list):
                for sess in sessions:
                    if not isinstance(sess, dict):
                        continue
                    idx = sess.get("session_index") or sess.get("session_number")
                    try:
                        if int(idx) != 2:
                            continue
                    except (TypeError, ValueError):
                        continue
                    sess_course = sess.get("course_id") or sess.get("course_code")
                    if course_code and sess_course and str(sess_course) != str(course_code):
                        continue
                    s2_date = sess.get("session_date") or sess.get("date")
                    s2_time = sess.get("session_time") or sess.get("start_time")
                    if s2_date and not out.get("session_2_class_date"):
                        out["session_2_class_date"] = s2_date
                    if s2_time and not out.get("session_2_class_time"):
                        out["session_2_class_time"] = str(s2_time)
                    break

    _ta_session_codes = (
        "ta_conceptual_questions",
        "ta_blog_content",
        "ta_essay_upload",
        "ta_student_consultation",
    )
    if process_code in _ta_session_codes:
        merged = {**context_data, **out}
        course_code = (
            merged.get("course_id")
            or merged.get("course_code")
            or merged.get("lesson_course_label")
            or course_name
        )
        if "course_name" in field_names and not out.get("course_name"):
            out["course_name"] = course_name or merged.get("course_name") or str(course_code or "—")
        if "session_number" in field_names and not out.get("session_number"):
            sn = merged.get("session_number") or merged.get("session_index")
            if sn is not None:
                out["session_number"] = sn
        if "session_date" in field_names and not out.get("session_date"):
            out["session_date"] = (
                merged.get("session_date")
                or merged.get("class_session_date")
                or merged.get("lesson_date")
                or "—"
            )
        if "milestone_session" in field_names and not out.get("milestone_session"):
            ms = merged.get("milestone_session") or merged.get("session_index")
            if ms is not None:
                out["milestone_session"] = f"جلسه {ms}"
        if process_code == "ta_student_consultation" and state_code == "ta_form_fill":
            from datetime import date

            if "submitted_at" in field_names and not out.get("submitted_at"):
                out["submitted_at"] = date.today().isoformat()
            if "blog_content" in field_names and merged.get("blog_content_draft"):
                out.setdefault("blog_content", merged["blog_content_draft"])
            if course_code and "students" in field_names:
                from app.services.instructor_course_roster_service import get_course_roster

                roster = await get_course_roster(db, str(course_code))
                if roster and not out.get("students"):
                    out["class_roster_options"] = [
                        {
                            "value": r.get("student_id") or r.get("student_name"),
                            "label_fa": r.get("name_fa")
                            or r.get("student_code")
                            or "—",
                        }
                        for r in roster
                        if isinstance(r, dict)
                    ]

    if process_code == "ta_blog_content" and state_code in ("ta_write", "rejected_revision", "instructor_review"):
        merged = {**context_data, **out}
        if "blog_content" in field_names and merged.get("blog_content") and not out.get("blog_content"):
            out["blog_content"] = merged["blog_content"]

    if process_code == "student_non_registration" and state_code == "meeting_held":
        merged = {**context_data, **out}
        if "weeks_since_start" in field_names and out.get("weeks_since_start") in (None, "", "—"):
            weeks = await _weeks_since_term_start(db, merged, student)
            if weeks is not None:
                out["weeks_since_start"] = weeks
                out["weeks_since_term_start"] = weeks

    if process_code == "thesis_defense_request" and state_code == "eligibility_check":
        from app.services.thesis_defense_eligibility_service import (
            build_thesis_defense_eligibility_context,
            eligibility_readonly_labels,
        )

        merged = {**context_data, **out}
        if student_id:
            fields_data = await build_thesis_defense_eligibility_context(db, student_id)
            merged.update(fields_data)
            out.update(fields_data)
            labels = eligibility_readonly_labels(fields_data)
            for fname, label in labels.items():
                if fname in field_names and not out.get(fname):
                    out[fname] = label

    if process_code == "thesis_defense_request" and state_code == "first_defense_held":
        if "defense_type" in field_names and not out.get("defense_type"):
            out["defense_type"] = "دفاع اول"

    if process_code == "thesis_defense_request" and state_code == "second_defense_held":
        if "defense_type" in field_names and not out.get("defense_type"):
            out["defense_type"] = "دفاع مجدد"

    if process_code == "intern_bulk_patient_referral":
        merged = {**context_data, **out}
        rows = merged.get("patient_referral_rows")
        if "patient_referral_rows" in field_names and isinstance(rows, list) and rows:
            if not out.get("patient_referral_rows"):
                out["patient_referral_rows"] = _build_referral_rows_for_state(state_code, rows)
        if state_code == "supervision_start":
            for key in ("meeting_datetime", "meeting_held", "referral_conditions"):
                if key in field_names and not out.get(key) and merged.get(key) not in (None, ""):
                    out[key] = merged[key]

    if process_code == "violation_registration":
        merged = {**context_data, **out}
        _VTYPE_FA = {
            "professional": "حرفه‌ای",
            "educational": "آموزشی",
            "disciplinary": "انضباطی",
        }
        _VERDICT_FA = {
            "cleared": "مبرا",
            "notice": "تذکر",
            "warning_1": "اخطار مرحله اول",
            "warning_2": "اخطار مرحله دوم",
            "warning_3": "اخطار مرحله سوم",
            "suspension_next_term": "تعلیق از ترم بعد",
            "suspension_immediate": "تعلیق آنی",
            "refer_education": "ارجاع به کمیته آموزش",
            "no_expulsion": "عدم اخراج",
            "expulsion": "اخراج",
        }
        if "source_reason" in field_names and not out.get("source_reason"):
            out["source_reason"] = merged.get("source_reason") or merged.get("reason") or "—"
        if "source_process_code" in field_names and not out.get("source_process_code"):
            out["source_process_code"] = merged.get("source_process_code") or "—"
        if "violation_type_display" in field_names and not out.get("violation_type_display"):
            vt = merged.get("violation_type")
            out["violation_type_display"] = _VTYPE_FA.get(str(vt or ""), vt) or "—"
        if "meeting_at_display" in field_names and not out.get("meeting_at_display"):
            out["meeting_at_display"] = merged.get("meeting_at") or "—"
        if "verdict_action" in field_names and not out.get("verdict_action"):
            v = merged.get("verdict")
            out["verdict_action"] = _VERDICT_FA.get(str(v or ""), v) or merged.get("verdict_action") or "—"
        if "violation_type" in field_names and not out.get("violation_type"):
            vt = merged.get("violation_type")
            out["violation_type"] = _VTYPE_FA.get(str(vt or ""), vt) or "—"
        if "compensatory_conditions" in field_names and not out.get("compensatory_conditions"):
            out["compensatory_conditions"] = merged.get("compensatory_conditions") or "—"
        if "final_status" in field_names and not out.get("final_status"):
            fd = merged.get("final_decision")
            out["final_status"] = _VERDICT_FA.get(str(fd or ""), fd) or "—"
        if not out.get("description") and merged.get("description"):
            out["description"] = merged["description"]

    return out


async def _weeks_since_term_start(
    db: AsyncSession,
    context: dict[str, Any],
    student: Optional[Student],
) -> Optional[int]:
    """هفته‌های گذشته از شروع ترم — برای فرم نتیجه فرایند ۴۲."""
    from datetime import date

    from app.services.institute_calendar_service import get_active_calendar

    term_start = None
    cal = await get_active_calendar(db)
    if cal and cal.term_start_date:
        term_start = cal.term_start_date
    if term_start is None and student:
        extra = _ctx(student.extra_data)
        raw = extra.get("term_start_date")
        if raw:
            try:
                term_start = date.fromisoformat(str(raw)[:10])
            except (TypeError, ValueError):
                pass
    if term_start is None:
        return None
    delta_days = (date.today() - term_start).days
    if delta_days < 0:
        return 0
    return delta_days // 7
