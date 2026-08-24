"""Service B - LMS / Course-Registration Service.

Replaces the log-only stub for course enrollment, catalog loading, track
progression, supervision-block registration and attendance/link enablement.
State lives under ``Student.extra_data['lms']`` and is real, queryable data:

    lms = {
        "enrolled_courses": [...],
        "available_courses": [...],
        "course_links": {...},
        "track_progress": {"unlocked": [...]},
        "access_flags": {"therapist_selection_unlocked": True, ...},
        "supervision_blocks": [...],
        "attendance_enabled": {...},
        "online_links": [...],
        "pause_dates": [...],
        "published": True,
        "total_hours": <int>,
    }
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.workflow import _common as C


def _lms(extra: dict) -> dict:
    lms = dict(extra.get("lms") or {})
    extra["lms"] = lms
    return lms


def _course_list(ctx: dict, action: dict) -> list:
    raw = (
        action.get("courses")
        or ctx.get("selected_courses")
        or ctx.get("courses")
        or ctx.get("course_codes")
        or []
    )
    if isinstance(raw, str):
        raw = [c.strip() for c in raw.replace("،", ",").split(",") if c.strip()]
    return list(raw) if isinstance(raw, (list, tuple)) else []


def _normalize_course_code(c: Any) -> str:
    if isinstance(c, dict):
        return str(c.get("code") or c.get("course_code") or "").strip()
    return str(c or "").strip()


def _is_external_meeting_url(url: Any) -> bool:
    s = str(url or "").strip()
    if not s:
        return False
    if s.startswith("/panel/") or s.startswith("/online/"):
        return False
    return s.startswith("http://") or s.startswith("https://")


async def _seed_enrollment_side_effects(
    db: AsyncSession,
    student: Any,
    lms: dict,
    courses: list,
    ctx: dict,
) -> None:
    """پس از ثبت‌نام: لینک پورتال، لیست حضور، و تقویم جلسات."""
    codes = [_normalize_course_code(c) for c in courses]
    codes = [c for c in codes if c]
    if not codes:
        codes = [
            _normalize_course_code(c) for c in (lms.get("enrolled_courses") or [])
        ]
        codes = [c for c in codes if c]
    if not codes:
        return

    # create_lms_course_links (prefer real meeting URL from offering)
    links = dict(lms.get("course_links") or {})
    portal_links = dict(lms.get("portal_course_links") or {})
    meta = dict(lms.get("course_link_meta") or {})
    options_by_code = {}
    for opt in (lms.get("available_course_options") or ctx.get("prep_course_rows") or []):
        if not isinstance(opt, dict):
            continue
        code = str(opt.get("value") or opt.get("course_code") or "").strip()
        if code:
            options_by_code[code] = opt

    from app.services.term_course_offering_service import get_offering_by_code

    for code in codes:
        offering = await get_offering_by_code(db, code)
        opt = options_by_code.get(code) or {}
        meeting = ""
        if offering and getattr(offering, "online_meeting_url", None):
            meeting = str(offering.online_meeting_url or "").strip()
        if not meeting:
            meeting = str(opt.get("online_meeting_url") or opt.get("meeting_url") or "").strip()
        # Store external URL when available; else keep a stable portal deep-link for navigation
        portal_url = f"/panel/portal/student?tab=sessions&course={code}"
        url = meeting if _is_external_meeting_url(meeting) else portal_url
        links[code] = url
        portal_links[code] = url
        meta[code] = {
            "course_name_fa": (
                (offering.course_name_fa if offering else None)
                or opt.get("label_fa")
                or opt.get("course_name")
                or code
            ),
            "day": (offering.day if offering else None) or opt.get("day"),
            "time_text": (
                (offering.time_text if offering else None)
                or opt.get("time_text")
                or opt.get("time")
            ),
            "instructor_name": (
                (offering.instructor_name if offering else None)
                or opt.get("instructor_name")
                or opt.get("instructor")
            ),
            "teaching_assistant_name": (
                (offering.teaching_assistant_name if offering else None)
                or opt.get("teaching_assistant_name")
                or opt.get("teaching_assistant")
            ),
            "classroom_location": (
                (offering.classroom_location if offering else None)
                or opt.get("classroom_location")
            ),
            "online_meeting_url": meeting if _is_external_meeting_url(meeting) else None,
            "url": url,
        }

    lms["course_links"] = links
    lms["portal_course_links"] = portal_links
    lms["course_link_meta"] = meta
    lms["links_placed"] = True
    lms["links_placed_at"] = C.now_iso()

    # build_class_attendance_list (idempotent — keep existing sessions)
    rosters = dict(lms.get("lesson_attendance") or {})
    for code in codes:
        existing = rosters.get(code)
        if isinstance(existing, dict) and existing.get("sessions") is not None:
            # ensure student is on roster
            students_rows = list(existing.get("students") or [])
            sid = str(student.id)
            if not any(str(r.get("student_id")) == sid for r in students_rows if isinstance(r, dict)):
                students_rows.append({
                    "student_id": sid,
                    "student_code": student.student_code,
                    "name_fa": ctx.get("student_name_fa") or student.student_code,
                })
                existing["students"] = students_rows
                existing["updated_at"] = C.now_iso()
                rosters[code] = existing
            continue
        rosters[code] = {
            "course_code": code,
            "students": [
                {
                    "student_id": str(student.id),
                    "student_code": student.student_code,
                    "name_fa": ctx.get("student_name_fa") or student.student_code,
                }
            ],
            "sessions": [],
            "absence_count": 0,
            "updated_at": C.now_iso(),
        }
    lms["lesson_attendance"] = rosters
    lms["attendance_list_ready"] = True
    lms["attendance_list_ready_at"] = C.now_iso()

    # seed course_sessions calendar
    try:
        from app.services.course_session_calendar_service import seed_course_sessions_for_student

        # temporarily attach lms so seed sees latest enrolled
        extra = C.student_extra(student)
        extra["lms"] = lms
        student.extra_data = extra
        await seed_course_sessions_for_student(db, student, course_codes=codes)
        # refresh lms from student after seed
        lms.update(dict((student.extra_data or {}).get("lms") or {}))
    except Exception:
        pass


async def handle(db: AsyncSession, instance: ProcessInstance, action: dict, context: dict) -> Optional[str]:
    action_type = action.get("type", "")
    ctx = C.merged_context(instance, action, context)
    student = await C.get_student(db, instance.student_id)
    if not student:
        return "student_not_found"

    extra = C.student_extra(student)
    lms = _lms(extra)
    result = action_type

    if action_type in ("register_courses_in_portal", "register_student_in_courses"):
        courses = _course_list(ctx, action)
        from app.meta.course_selection_validation import (
            course_selection_config,
            normalize_course_codes,
            validate_selected_courses_for_process,
        )

        if course_selection_config(instance.process_code):
            codes = normalize_course_codes(courses)
            ok, err = await validate_selected_courses_for_process(
                db, instance.process_code, ctx, codes, student=student, instance=instance
            )
            if not ok:
                return f"enroll_rejected: {err}"
        enrolled = list(lms.get("enrolled_courses") or [])
        for c in courses:
            code = _normalize_course_code(c) if not isinstance(c, (str, int)) else str(c).strip()
            # keep dict entries if already structured; prefer code string for uniqueness
            existing_codes = {
                _normalize_course_code(x) if not isinstance(x, (str, int)) else str(x).strip()
                for x in enrolled
            }
            entry = c if isinstance(c, dict) else code
            check = _normalize_course_code(entry) if isinstance(entry, dict) else str(entry).strip()
            if check and check not in existing_codes:
                enrolled.append(entry if isinstance(c, dict) else code)
        lms["enrolled_courses"] = enrolled
        lms["last_enrollment_at"] = C.now_iso()
        await _seed_enrollment_side_effects(db, student, lms, courses, ctx)
        result = f"enrolled n={len(courses)} total={len(enrolled)}"

    elif action_type in ("load_available_courses", "load_term3_courses"):
        from app.services.term_course_offering_service import (
            NO_OFFERINGS_REASON_FA,
            merge_offerings_into_instance_context,
            resolve_program_term_for_process,
        )

        program_term = await resolve_program_term_for_process(
            instance.process_code, student=student
        )
        if program_term:
            pk, tn = program_term
            merged_ctx = await merge_offerings_into_instance_context(
                db, instance.process_code, ctx, student=student
            )
            courses = merged_ctx.get("available_courses") or []
            lms.update(merged_ctx.get("lms") or {})
            if not courses:
                lms["unavailable_reason_fa"] = merged_ctx.get(
                    "course_selection_hint_fa"
                ) or NO_OFFERINGS_REASON_FA
        else:
            courses = _course_list(ctx, action)
        lms["available_courses"] = list(courses) if isinstance(courses, list) else []
        lms["available_loaded_at"] = C.now_iso()
        result = f"available_courses n={len(lms['available_courses'])}"

    elif action_type == "publish_courses_to_website":
        from app.services.term_course_offering_service import publish_offerings_from_prep

        pub = await publish_offerings_from_prep(db, instance, ctx)
        lms["published"] = pub.get("published", False)
        lms["published_at"] = C.now_iso()
        lms["published_count"] = pub.get("count", 0)
        result = f"publish_term_course_offerings n={pub.get('count', 0)}"

    elif action_type == "create_lms_course_links":
        courses = _course_list(ctx, action) or list(lms.get("enrolled_courses") or [])
        links = dict(lms.get("course_links") or {})
        meta = dict(lms.get("course_link_meta") or {})
        options_by_code = {}
        for opt in (lms.get("available_course_options") or ctx.get("prep_course_rows") or []):
            if not isinstance(opt, dict):
                continue
            code = str(opt.get("value") or opt.get("course_code") or "").strip()
            if code:
                options_by_code[code] = opt
        from app.services.term_course_offering_service import get_offering_by_code

        for c in courses:
            code = str(c.get("code") or c.get("course_code") or c) if isinstance(c, dict) else str(c)
            offering = await get_offering_by_code(db, code)
            opt = options_by_code.get(code) or {}
            meeting = ""
            if offering and getattr(offering, "online_meeting_url", None):
                meeting = str(offering.online_meeting_url or "").strip()
            if not meeting:
                meeting = str(opt.get("online_meeting_url") or "").strip()
            portal_url = f"/panel/portal/student?tab=sessions&course={code}"
            url = meeting if _is_external_meeting_url(meeting) else portal_url
            links[code] = url
            opt_meta = {
                "course_name_fa": (
                    (offering.course_name_fa if offering else None)
                    or opt.get("label_fa")
                    or opt.get("course_name")
                    or code
                ),
                "day": (offering.day if offering else None) or opt.get("day"),
                "time_text": (
                    (offering.time_text if offering else None)
                    or opt.get("time_text")
                    or opt.get("time")
                ),
                "instructor_name": (
                    (offering.instructor_name if offering else None)
                    or opt.get("instructor_name")
                    or opt.get("instructor")
                ),
                "teaching_assistant_name": (
                    (offering.teaching_assistant_name if offering else None)
                    or opt.get("teaching_assistant_name")
                    or opt.get("teaching_assistant")
                ),
                "classroom_location": (
                    (offering.classroom_location if offering else None)
                    or opt.get("classroom_location")
                ),
                "online_meeting_url": meeting if _is_external_meeting_url(meeting) else None,
                "url": url,
            }
            meta[code] = opt_meta
        lms["course_links"] = links
        lms["course_link_meta"] = meta
        result = f"course_links n={len(links)}"

    elif action_type == "unlock_next_course_in_track":
        nxt = action.get("course_code") or ctx.get("next_course_code") or ctx.get("course_code")
        track = dict(lms.get("track_progress") or {})
        unlocked = list(track.get("unlocked") or [])
        if not nxt:
            nxt = f"track_step_{len(unlocked) + 1}"
        if nxt not in unlocked:
            unlocked.append(nxt)
        track["unlocked"] = unlocked
        track["updated_at"] = C.now_iso()
        lms["track_progress"] = track
        result = f"unlocked_course={nxt}"

    elif action_type in ("send_unlock_to_lms", "unlock_student_therapist_selection"):
        flags = dict(lms.get("access_flags") or {})
        key = "therapist_selection_unlocked" if action_type == "unlock_student_therapist_selection" else "lms_unlocked"
        flags[key] = True
        flags[f"{key}_at"] = C.now_iso()
        lms["access_flags"] = flags
        result = f"flag:{key}=true"

    elif action_type == "register_new_supervision_block_in_lms":
        blocks = list(lms.get("supervision_blocks") or [])
        block = {
            "id": C.new_id(),
            "supervisor_id": ctx.get("new_supervisor_id") or ctx.get("supervisor_id"),
            "registered_at": C.now_iso(),
            "hours": 0,
            "status": "active",
        }
        blocks.append(block)
        lms["supervision_blocks"] = blocks
        result = f"supervision_block_registered id={block['id']}"

    elif action_type in ("enable_attendance_for_new_supervisor", "enable_attendance_for_current_supervisor_50th"):
        att = dict(lms.get("attendance_enabled") or {})
        sup = ctx.get("new_supervisor_id") or ctx.get("supervisor_id") or "current"
        att[str(sup)] = {"enabled": True, "at": C.now_iso(), "context": action_type}
        lms["attendance_enabled"] = att
        result = f"attendance_enabled supervisor={sup}"

    elif action_type == "create_online_link_50th":
        links = list(lms.get("online_links") or [])
        link = {
            "id": C.new_id(),
            "kind": "supervision_50th",
            "url": ctx.get("online_link") or f"/online/supervision/{instance.id}",
            "created_at": C.now_iso(),
        }
        links.append(link)
        lms["online_links"] = links
        result = f"online_link_50th={link['url']}"

    elif action_type == "record_pause_dates_in_lms":
        pauses = list(lms.get("pause_dates") or [])
        pauses.append({
            "id": C.new_id(),
            "start": ctx.get("pause_start") or ctx.get("interruption_start_date"),
            "end": ctx.get("pause_end") or ctx.get("interruption_end_date"),
            "recorded_at": C.now_iso(),
        })
        lms["pause_dates"] = pauses
        result = f"pause_dates n={len(pauses)}"

    elif action_type == "update_total_hours":
        try:
            delta = int(action.get("hours") or ctx.get("hours_delta") or ctx.get("hours") or 0)
        except (TypeError, ValueError):
            delta = 0
        lms["total_hours"] = int(lms.get("total_hours") or 0) + delta
        result = f"total_hours={lms['total_hours']}"

    elif action_type == "record_lms_links_placed":
        courses = _course_list(ctx, action) or list(lms.get("enrolled_courses") or [])
        links = dict(lms.get("course_links") or {})
        portal_links = dict(lms.get("portal_course_links") or {})
        meta = dict(lms.get("course_link_meta") or {})
        for c in courses:
            code = str(c.get("code") or c.get("course_code") or c) if isinstance(c, dict) else str(c)
            meta_url = (meta.get(code) or {}).get("online_meeting_url") if isinstance(meta.get(code), dict) else None
            preferred = meta_url if _is_external_meeting_url(meta_url) else None
            existing = links.get(code)
            url = preferred or (existing if _is_external_meeting_url(existing) else None) or (
                f"/panel/portal/student?tab=sessions&course={code}"
            )
            portal_links[code] = url
            links.setdefault(code, url)
        lms["course_links"] = links
        lms["portal_course_links"] = portal_links
        lms["links_placed_at"] = C.now_iso()
        lms["links_placed"] = True
        result = f"links_placed n={len(portal_links)}"

    elif action_type == "build_class_attendance_list":
        courses = _course_list(ctx, action) or list(lms.get("enrolled_courses") or [])
        rosters = dict(lms.get("lesson_attendance") or {})
        for c in courses:
            code = _normalize_course_code(c) if not isinstance(c, (str, int)) else str(c).strip()
            if not code:
                continue
            existing = rosters.get(code)
            if isinstance(existing, dict) and isinstance(existing.get("sessions"), list):
                continue
            rosters[code] = {
                "course_code": code,
                "students": [
                    {
                        "student_id": str(student.id),
                        "student_code": student.student_code,
                        "name_fa": ctx.get("student_name_fa") or student.student_code,
                    }
                ],
                "sessions": [],
                "absence_count": 0,
                "updated_at": C.now_iso(),
            }
        lms["lesson_attendance"] = rosters
        lms["attendance_list_ready"] = True
        lms["attendance_list_ready_at"] = C.now_iso()
        try:
            from app.services.course_session_calendar_service import seed_course_sessions_for_student

            codes = [
                _normalize_course_code(c) if not isinstance(c, (str, int)) else str(c).strip()
                for c in courses
            ]
            codes = [c for c in codes if c]
            extra["lms"] = lms
            student.extra_data = extra
            await seed_course_sessions_for_student(db, student, course_codes=codes or None)
            lms.update(dict((student.extra_data or {}).get("lms") or {}))
        except Exception:
            pass
        result = f"attendance_lists n={len(rosters)}"

    elif action_type == "register_lesson_teaching_assistants":
        courses = _course_list(ctx, action) or list(lms.get("enrolled_courses") or [])
        ta_map = dict(lms.get("teaching_assistants_by_course") or {})
        prep_rows = (
            ctx.get("prep_course_rows")
            or lms.get("available_course_options")
            or ctx.get("courses")
            or []
        )
        if isinstance(prep_rows, list):
            for row in prep_rows:
                if not isinstance(row, dict):
                    continue
                code = str(
                    row.get("course_code")
                    or row.get("value")
                    or row.get("course_name")
                    or ""
                ).strip()
                ta = (
                    row.get("teaching_assistant_name")
                    or row.get("teaching_assistant")
                    or row.get("ta_name")
                    or ""
                ).strip()
                name = (row.get("course_name") or row.get("label_fa") or code).strip()
                if code and ta:
                    ta_map[code] = ta
                if name and ta and name not in ta_map:
                    ta_map[name] = ta
        # Enrich from published offerings when prep rows missing TA
        missing = [
            str(c.get("code") or c.get("course_code") or c) if isinstance(c, dict) else str(c)
            for c in courses
            if str(c.get("code") or c.get("course_code") or c if isinstance(c, dict) else c) not in ta_map
            or ta_map.get(str(c.get("code") or c.get("course_code") or c if isinstance(c, dict) else c)) in ("", "—", None)
        ]
        if missing:
            from app.services.term_course_offering_service import get_offering_by_code

            for code in missing:
                offering = await get_offering_by_code(db, code)
                if offering and offering.teaching_assistant_name:
                    ta_map[code] = offering.teaching_assistant_name
                elif offering and offering.instructor_name and code not in ta_map:
                    ta_map[code] = "—"
        for c in courses:
            code = str(c.get("code") or c.get("course_code") or c) if isinstance(c, dict) else str(c)
            if code not in ta_map or not ta_map.get(code):
                ta_map[code] = ctx.get("teaching_assistant") or "—"
        lms["teaching_assistants_by_course"] = ta_map
        lms["lesson_active_at"] = C.now_iso()
        result = f"teaching_assistants n={len(ta_map)}"

    else:
        C.record_event(instance, action_type, {"unhandled_in": "lms_service"})
        return f"lms_noop:{action_type}"

    C.commit_student_extra(student, extra)
    C.record_event(instance, action_type, {"result": result})
    return result
