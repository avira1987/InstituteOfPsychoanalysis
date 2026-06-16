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

from typing import Optional

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
        enrolled = list(lms.get("enrolled_courses") or [])
        for c in courses:
            if c not in enrolled:
                enrolled.append(c)
        lms["enrolled_courses"] = enrolled
        lms["last_enrollment_at"] = C.now_iso()
        result = f"enrolled n={len(courses)} total={len(enrolled)}"

    elif action_type in ("load_available_courses", "load_term3_courses"):
        courses = _course_list(ctx, action)
        if not courses:
            # Default catalog by course type / term when not provided.
            term = 3 if action_type == "load_term3_courses" else int(student.current_term or 1)
            courses = [f"{student.course_type}_term{term}_course{i}" for i in range(1, 4)]
        lms["available_courses"] = courses
        lms["available_loaded_at"] = C.now_iso()
        result = f"available_courses n={len(courses)}"

    elif action_type == "create_lms_course_links":
        courses = _course_list(ctx, action) or list(lms.get("enrolled_courses") or [])
        links = dict(lms.get("course_links") or {})
        for c in courses:
            links[str(c)] = f"/lms/courses/{c}/{student.student_code}"
        lms["course_links"] = links
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

    elif action_type == "publish_courses_to_website":
        lms["published"] = True
        lms["published_at"] = C.now_iso()
        published = list(lms.get("available_courses") or lms.get("enrolled_courses") or [])
        lms["published_courses"] = published
        result = f"published n={len(published)}"

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
        for c in courses:
            code = str(c)
            url = links.get(code) or f"/lms/courses/{code}/{student.student_code}"
            portal_links[code] = url
        lms["portal_course_links"] = portal_links
        lms["links_placed_at"] = C.now_iso()
        lms["links_placed"] = True
        result = f"links_placed n={len(portal_links)}"

    elif action_type == "build_class_attendance_list":
        courses = _course_list(ctx, action) or list(lms.get("enrolled_courses") or [])
        rosters = dict(lms.get("lesson_attendance") or {})
        for c in courses:
            code = str(c)
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
                "updated_at": C.now_iso(),
            }
        lms["lesson_attendance"] = rosters
        lms["attendance_list_ready"] = True
        lms["attendance_list_ready_at"] = C.now_iso()
        result = f"attendance_lists n={len(rosters)}"

    elif action_type == "register_lesson_teaching_assistants":
        courses = _course_list(ctx, action) or list(lms.get("enrolled_courses") or [])
        ta_map = dict(lms.get("teaching_assistants_by_course") or {})
        prep_rows = ctx.get("prep_course_rows") or ctx.get("courses") or []
        if isinstance(prep_rows, list):
            for row in prep_rows:
                if not isinstance(row, dict):
                    continue
                name = (row.get("course_name") or row.get("course_code") or "").strip()
                ta = (row.get("teaching_assistant") or row.get("ta_name") or "").strip()
                if name and ta:
                    ta_map[name] = ta
        for c in courses:
            code = str(c)
            if code not in ta_map:
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
