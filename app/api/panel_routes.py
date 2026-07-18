"""پنل نقش‌ها — صف اقدامات پیشنهادی برای UI و اتوماسیون."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_admin_only
from app.database import get_db
from app.meta.student_lifecycle_matrix import get_panel_action_queue_for_role
from app.models.operational_models import Student, User
from app.services.nav_pending_counts import compute_nav_pending_counts
from app.services.operator_followup_inbox import build_operator_followup_inbox_full
from app.services.operator_readiness import compute_operator_readiness_alerts
from app.services.panel_action_notifications import build_action_notifications
from app.services.panel_notification_dismiss import dismiss_action_notification
from app.services.panel_flash_messages import create_panel_flash_message
from app.services.portal_role_inbox import build_portal_role_process_inbox
from app.services.process_nav_service import build_process_nav_items
from app.services import sms_simulation_service
from app.services.student_online_sessions_service import list_student_online_sessions
from sqlalchemy import select

router = APIRouter(prefix="/api/panel", tags=["Panel"])


def _merge_readiness_into_inbox_items(
    core_items: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """هشدارهای آمادگی را به‌صورت آیتم «readiness» به ابتدای کارتابل می‌چسباند تا در UI اقدام‌پذیر دیده شوند."""
    if not alerts:
        return list(core_items)
    now_iso = datetime.now(timezone.utc).isoformat()
    extra: list[dict[str, Any]] = []
    for a in alerts:
        extra.append(
            {
                "kind": "readiness",
                "readiness_id": str(a.get("id", "")),
                "title_fa": a.get("title_fa") or "",
                "detail_fa": a.get("detail_fa") or "",
                "action_href": a.get("action_href") or "",
                "action_label_fa": a.get("action_label_fa") or "",
                "severity": a.get("severity") or "warning",
                "sort_at": now_iso,
            }
        )
    merged = extra + list(core_items)

    def _sk(x: dict[str, Any]) -> tuple[int, str]:
        return (0 if x.get("kind") == "readiness" else 1, x.get("sort_at") or "")

    merged.sort(key=_sk)
    return merged


@router.get("/action-queue")
async def panel_action_queue(user: User = Depends(get_current_user)):
    """اقدامات منتظر انجام (الگوی نقش + فرایندهای رجیستری مرتبط) — نیاز به JWT."""
    return get_panel_action_queue_for_role(user.role)


@router.get("/my-process-inbox")
async def panel_my_process_inbox(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    process_limit: int = Query(120, ge=1, le=200),
    scan_cap: int = Query(600, ge=100, le=2000),
):
    """
    نمونه‌های فرایند باز متناسب با نقش ورود (طبق assigned_role در DB و نگاشت پنل).
    دانشجو: خالی؛ سایر نقش‌ها: فهرست قابل استفاده برای لینک عمیق به همان پرونده.
    """
    if user.role == "student":
        return {
            "items": [],
            "summary": {"process_count": 0, "assignment_count": 0, "portal_role": "student"},
        }
    pl = min(process_limit, 200)
    sc = min(max(scan_cap, pl), 2000)
    return await build_portal_role_process_inbox(
        db,
        portal_role=user.role,
        process_limit=pl,
        scan_cap=sc,
        include_assignments_for_staff=(user.role in ("staff", "admin")),
    )


@router.get("/my-operator-followup")
async def panel_my_operator_followup(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    process_limit: int = Query(120, ge=1, le=200),
    scan_cap: int = Query(600, ge=100, le=2000),
):
    """
    کارتابل نمونهٔ فرایند + هشدارهای آمادگی نقش (اسلات، جلسات درمان، …) — همهٔ نقش‌های غیردانشجو.
    """
    if user.role == "student":
        return {
            "items": [],
            "readiness_alerts": [],
            "summary": {
                "process_count": 0,
                "assignment_count": 0,
                "portal_role": "student",
                "readiness_count": 0,
            },
        }
    pl = min(process_limit, 200)
    sc = min(max(scan_cap, pl), 2000)
    core = await build_portal_role_process_inbox(
        db,
        portal_role=user.role,
        process_limit=pl,
        scan_cap=sc,
        include_assignments_for_staff=(user.role in ("staff", "admin")),
    )
    alerts = await compute_operator_readiness_alerts(db, user)
    summary = dict(core.get("summary") or {})
    summary["readiness_count"] = len(alerts)
    merged_items = _merge_readiness_into_inbox_items(core.get("items") or [], alerts)
    return {**core, "items": merged_items, "readiness_alerts": alerts, "summary": summary}


@router.get("/nav-pending-counts")
async def panel_nav_pending_counts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    شمارش کارهای منتظر برای آیتم‌های منو (همان منطق پنل‌های نقش + تیکت‌های باز/در حال رسیدگی).
    """
    return await compute_nav_pending_counts(db, user)


@router.get("/process-nav-items")
async def panel_process_nav_items(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """آیتم‌های منوی سایدبار — یک ورودی به ازای هر فرایند قابل اقدام برای نقش جاری."""
    return await build_process_nav_items(db, user)


@router.get("/action-notifications")
async def panel_action_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100_000),
    process_limit: int = Query(120, ge=1, le=200),
    scan_cap: int = Query(600, ge=100, le=2000),
):
    """فید یکپارچهٔ اعلان‌های اقدام (زنگوله + صفحهٔ همه اعلان‌ها)."""
    return await build_action_notifications(
        db,
        user,
        limit=limit,
        offset=offset,
        process_limit=process_limit,
        scan_cap=scan_cap,
    )


@router.post("/task-reminders/{reminder_id}/dismiss")
async def panel_dismiss_task_reminder(
    reminder_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """بستن نوتیفیکیشن ثبت‌شده (مثلاً یادآوری روزانه کار عقب‌افتاده)."""
    ok = await dismiss_action_notification(
        db,
        user_id=user.id,
        notification_id=f"daily_overdue:{reminder_id}",
    )
    if not ok:
        raise HTTPException(status_code=404, detail="reminder not found")
    await db.commit()
    return {"ok": True}


class ActionNotificationDismiss(BaseModel):
    notification_id: str = Field(..., min_length=3, max_length=255)


@router.post("/action-notifications/dismiss")
async def panel_dismiss_action_notification(
    body: ActionNotificationDismiss,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """بستن یک اعلان از فید (کار معلق، پیام فلش، یادآوری روزانه و …)."""
    ok = await dismiss_action_notification(
        db,
        user_id=user.id,
        notification_id=body.notification_id.strip(),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="notification not found")
    await db.commit()
    return {"ok": True}


class FlashMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    level: str = Field(default="success", pattern="^(success|error)$")
    source_path: Optional[str] = Field(default=None, max_length=1024)


@router.post("/flash-messages")
async def panel_create_flash_message(
    body: FlashMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """ثبت پیام پاپ‌آپ UI برای مرور در پنل اعلان‌ها."""
    try:
        row = await create_panel_flash_message(
            db,
            user_id=user.id,
            message=body.message,
            level=body.level,
            source_path=body.source_path,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return {"ok": True, "id": str(row.id)}


@router.get("/simulated-sms")
async def panel_simulated_sms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    since: datetime | None = Query(None, description="فقط پیامک‌های با created_at بعد از این زمان"),
    limit: int = Query(15, ge=1, le=50),
):
    """پیامک‌های شبیه‌سازی‌شده (حالت تست log). ناظر نقش دار: فید همهٔ گیرنده‌ها؛ نقش دانشجو: فقط خط خود."""
    items = await sms_simulation_service.list_pending_for_user(db, user, since=since, limit=limit)
    return {
        "items": items,
        "enabled": sms_simulation_service.simulation_popup_enabled(),
        "feed_scope": "global_all_recipients"
        if sms_simulation_service.user_sees_global_sms_popup_feed(user)
        else "own_phone_only",
        "popup_show_all": sms_simulation_service.simulation_popup_show_all_setting(),
    }


@router.get("/student-sms-history")
async def panel_student_sms_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=30),
):
    """تاریخچهٔ پیامک‌های ارسالی به دانشجو (بدون کد ورود و بدون پیامک رمز پورتال)."""
    enabled = sms_simulation_service.student_sms_history_available()
    items = (
        await sms_simulation_service.list_student_sms_history(db, user, limit=limit)
        if enabled
        else []
    )
    return {"enabled": enabled, "items": items}


@router.post("/simulated-sms/{sms_id}/dismiss")
async def panel_simulated_sms_dismiss(
    sms_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok = await sms_simulation_service.dismiss(db, user, sms_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="پیامک یافت نشد، قبلاً بسته شده، یا شما دسترسی بستن آن را ندارید.",
        )
    return {"success": True}


_PANEL_CALENDAR_ROLES = frozenset(
    {
        "student",
        "applicant",
        "admin",
        "staff",
        "finance",
        "therapist",
        "supervisor",
        "instructor",
        "site_manager",
        "interviewer",
        "deputy_education",
        "course_committee",
        "teaching_assistant",
        "monitoring_committee_officer",
        "progress_committee",
        "education_committee",
        "supervision_committee",
        "specialized_commission",
        "therapy_committee_chair",
        "therapy_committee_executor",
        "admissions_officer",
    }
)


@router.get("/my-online-sessions")
async def panel_my_online_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    include_past: bool = Query(False, description="شامل جلسات گذشته"),
):
    """لیست یکپارچهٔ جلسات و لینک‌های آنلاین دانشجو (درمان، مصاحبه، سوپرویژن، کلاس)."""
    if user.role != "student":
        raise HTTPException(status_code=403, detail="این endpoint فقط برای دانشجو است")
    st = (await db.execute(select(Student).where(Student.user_id == user.id))).scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="پروفایل دانشجو یافت نشد")
    return await list_student_online_sessions(db, st, user, include_past=include_past)


@router.get("/academic-calendar/active")
async def panel_active_academic_calendar(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """تقویم آموزشی فعال انستیتو — read-only برای دانشجو و سایر نقش‌های پورتال."""
    if user.role not in _PANEL_CALENDAR_ROLES:
        raise HTTPException(status_code=403, detail="دسترسی به تقویم آموزشی برای این نقش مجاز نیست")
    from app.services.institute_calendar_service import calendar_to_response_dict, get_active_calendar

    cal = await get_active_calendar(db)
    return calendar_to_response_dict(cal)


@router.get("/operator-followup-inbox")
async def panel_operator_followup_inbox(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin_only),
    process_limit: int = Query(150, ge=1, le=200, description="حداکثر موارد فرایندی در پاسخ"),
    assignment_limit: int = Query(50, ge=0, le=100, description="حداکثر تکلیف بدون نمره"),
    scan_cap: int = Query(800, ge=50, le=3000, description="حداکثر ردیف فرایند برای اسکن"),
    student_id: str | None = Query(None, description="فیلتر به شناسه دانشجو (UUID)"),
    student_code: str | None = Query(None, description="فیلتر با کد دانشجو"),
    include_reference: bool = Query(False, description="مرجع وظایف نقش و فرایندهای registry (پیش‌فرض خاموش)"),
    include_gaps: bool = Query(False, description="اجرای قواعد کمبود (operator_gap_rules.json)"),
    gap_limit: int = Query(100, ge=0, le=500, description="حداکثر ردیف gap"),
):
    """صندوق پیگیری سراسری (فرایند + تکلیف + هشدار آمادگی) — هر حساب admin. کمبودها on-demand."""
    pl = min(process_limit, 200)
    al = min(assignment_limit, 100)
    sc = min(max(scan_cap, pl * 2), 3000)
    sid: uuid.UUID | None = None
    if student_id and str(student_id).strip():
        try:
            sid = uuid.UUID(str(student_id).strip())
        except ValueError as e:
            raise HTTPException(status_code=400, detail="student_id باید UUID معتبر باشد") from e
    scode = str(student_code).strip() if student_code else None
    return await build_operator_followup_inbox_full(
        db,
        process_limit=pl,
        assignment_limit=al,
        scan_cap=sc,
        student_id=sid,
        student_code=scode,
        include_reference=include_reference,
        include_gaps=include_gaps,
        gap_limit=gap_limit,
        readiness_user=user,
    )


@router.get("/my-semester-courses")
async def panel_my_semester_courses(
    user: User = Depends(get_current_user),
):
    """دروس انتساب‌یافته از آماده‌سازی ترم — برای پنل مدرس و کمک‌مدرس."""
    meta = user.profile_meta if isinstance(user.profile_meta, dict) else {}
    items = meta.get("semester_course_assignments") or []
    if not isinstance(items, list):
        items = []
    role = (user.role or "").strip()
    if role in ("instructor", "teaching_assistant"):
        kind = "instructor" if role == "instructor" else "teaching_assistant"
        items = [x for x in items if isinstance(x, dict) and (x.get("role_kind") in (None, kind))]
    return {"courses": items, "role": role}


@router.get("/instructor/course-roster")
async def panel_instructor_course_roster(
    course_code: str,
    enrich_film_reports: bool = Query(False, alias="enrich_film_reports"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """لیست دانشجویان ثبت‌نام‌شده در یک درس — برای ثبت حضور توسط مدرس."""
    from app.services.instructor_course_roster_service import get_course_roster_for_user

    role = (user.role or "").strip()
    if role not in ("admin", "staff", "instructor", "teaching_assistant"):
        raise HTTPException(status_code=403, detail="دسترسی مدرس یا کمک‌مدرس لازم است.")
    code = str(course_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="course_code الزامی است.")
    roster = await get_course_roster_for_user(
        db, user, code, include_final_reports=enrich_film_reports,
    )
    if not roster and role in ("instructor", "teaching_assistant"):
        from app.services.instructor_course_roster_service import user_may_access_course
        if not user_may_access_course(user, code):
            raise HTTPException(status_code=403, detail="این درس به شما انتساب داده نشده است.")
    return {"course_code": code, "roster": roster}


@router.get("/instructor/class-cancellation-preview")
async def panel_class_cancellation_preview(
    course_code: str = Query(..., alias="course_code"),
    session_key: Optional[str] = Query(None, alias="session_key"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """پیش‌نمایش زمان جبرانی — فرایند ۵۶."""
    from app.services.class_session_cancellation_service import preview_cancellation

    role = (user.role or "").strip()
    if role not in (
        "admin",
        "staff",
        "instructor",
        "teaching_assistant",
        "scientific_officer_course_committee",
        "course_committee_executive",
        "deputy_education",
    ):
        raise HTTPException(status_code=403, detail="دسترسی مدرس یا کمیته دروس لازم است.")
    code = str(course_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="course_code الزامی است.")
    all_term = role in (
        "scientific_officer_course_committee",
        "course_committee_executive",
        "admin",
        "staff",
        "deputy_education",
    )
    return await preview_cancellation(
        db, user, code, session_key, all_term=all_term
    )


@router.get("/instructor/live-supervision/{course_code}/progress")
async def panel_live_supervision_progress(
    course_code: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """پیشرفت ۱۵+۳ هر دانشجو در درس سوپرویژن زنده."""
    from app.services.instructor_course_roster_service import get_course_roster_for_user
    from app.services.live_supervision_course_service import get_progress_for_course

    role = (user.role or "").strip()
    if role not in ("admin", "staff", "instructor", "teaching_assistant"):
        raise HTTPException(status_code=403, detail="دسترسی مدرس یا کمک‌مدرس لازم است.")
    code = str(course_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="course_code الزامی است.")
    roster = await get_course_roster_for_user(db, user, code)
    progress = await get_progress_for_course(db, code, roster)
    return {"course_code": code, "progress": progress, "roster_count": len(roster)}


@router.get("/instructor/skills-course/{course_code}/grades-preview")
async def panel_skills_course_grades_preview(
    course_code: str,
    instance_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """پیش‌نمایش نمرات درس تمرین مهارت‌ها — فرایند ۶۳."""
    from app.services.instructor_course_roster_service import get_course_roster_for_user, user_may_access_course
    from app.services.skills_course_completion_service import get_grades_preview

    role = (user.role or "").strip()
    if role not in ("admin", "staff", "instructor", "teaching_assistant"):
        raise HTTPException(status_code=403, detail="دسترسی مدرس یا کمک‌مدرس لازم است.")
    code = str(course_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="course_code الزامی است.")
    roster = await get_course_roster_for_user(db, user, code)
    if not roster and role in ("instructor", "teaching_assistant"):
        if not user_may_access_course(user, code):
            raise HTTPException(status_code=403, detail="این درس به شما انتساب داده نشده است.")
    instance = None
    if instance_id:
        try:
            from app.models.operational_models import ProcessInstance
            import uuid as _uuid

            instance = await db.get(ProcessInstance, _uuid.UUID(str(instance_id)))
        except (ValueError, TypeError):
            instance = None
    preview = await get_grades_preview(db, code, instance=instance)
    return preview


@router.get("/instructor/group-supervision/{course_code}/grades-preview")
async def panel_group_supervision_grades_preview(
    course_code: str,
    instance_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """پیش‌نمایش Pass/Fail سوپرویژن گروهی — فرایند ۶۲."""
    from app.services.instructor_course_roster_service import get_course_roster_for_user, user_may_access_course
    from app.services.group_supervision_course_completion_service import get_grades_preview

    role = (user.role or "").strip()
    if role not in ("admin", "staff", "instructor", "teaching_assistant"):
        raise HTTPException(status_code=403, detail="دسترسی مدرس یا کمک‌مدرس لازم است.")
    code = str(course_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="course_code الزامی است.")
    roster = await get_course_roster_for_user(db, user, code)
    if not roster and role in ("instructor", "teaching_assistant"):
        if not user_may_access_course(user, code):
            raise HTTPException(status_code=403, detail="این درس به شما انتساب داده نشده است.")
    instance = None
    if instance_id:
        try:
            from app.models.operational_models import ProcessInstance
            import uuid as _uuid

            instance = await db.get(ProcessInstance, _uuid.UUID(str(instance_id)))
        except (ValueError, TypeError):
            instance = None
    preview = await get_grades_preview(db, code, instance=instance)
    return preview


@router.get("/instructor/theory-course/{course_code}/grades-preview")
async def panel_theory_course_grades_preview(
    course_code: str,
    instance_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """پیش‌نمایش نمرات درس تئوری — فرایند ۶۱."""
    from app.services.instructor_course_roster_service import get_course_roster_for_user, user_may_access_course
    from app.services.theory_course_completion_service import get_grades_preview

    role = (user.role or "").strip()
    if role not in ("admin", "staff", "instructor", "teaching_assistant"):
        raise HTTPException(status_code=403, detail="دسترسی مدرس یا کمک‌مدرس لازم است.")
    code = str(course_code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="course_code الزامی است.")
    roster = await get_course_roster_for_user(db, user, code)
    if not roster and role in ("instructor", "teaching_assistant"):
        if not user_may_access_course(user, code):
            raise HTTPException(status_code=403, detail="این درس به شما انتساب داده نشده است.")
    instance = None
    if instance_id:
        try:
            from app.models.operational_models import ProcessInstance
            import uuid as _uuid

            instance = await db.get(ProcessInstance, _uuid.UUID(str(instance_id)))
        except (ValueError, TypeError):
            instance = None
    preview = await get_grades_preview(db, code, instance=instance)
    return preview


@router.get("/instructor/trait-catalog")
async def panel_instructor_trait_catalog(
    kind: str = "positive",
    user: User = Depends(get_current_user),
):
    """کاتالوگ ویژگی‌های مثبت/منفی فرم ارزیابی مدرس (سوال ۷ و ۸)."""
    role = (user.role or "").strip()
    if role not in ("admin", "staff", "instructor", "teaching_assistant"):
        raise HTTPException(status_code=403, detail="دسترسی مدرس یا اپراتور لازم است.")
    from app.services.trait_catalog_service import list_trait_options

    k = (kind or "positive").strip().lower()
    if k not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="kind باید positive یا negative باشد.")
    return {"kind": k, "traits": list_trait_options(k)}


class InstructorEvaluationSubmitBody(BaseModel):
    overall_score: int = Field(..., ge=1, le=5)
    teaching_clarity: int = Field(..., ge=1, le=5)
    interaction_quality: int = Field(..., ge=1, le=5)
    comments: Optional[str] = None


@router.get("/student/instructor-evaluation/{instance_id}/courses")
async def panel_student_instructor_evaluation_courses(
    instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """فهرست دروس قابل ارزیابی برای دانشجو (فرایند ۵۷)."""
    from app.services.student_instructor_evaluation_service import (
        get_evaluation_courses_for_instance,
        load_instance_for_student,
    )

    inst, student = await load_instance_for_student(db, instance_id, user)
    return await get_evaluation_courses_for_instance(db, inst, student)


@router.post("/student/instructor-evaluation/{instance_id}/courses/{course_code}")
async def panel_student_instructor_evaluation_submit(
    instance_id: uuid.UUID,
    course_code: str,
    body: InstructorEvaluationSubmitBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """ثبت ناشناس ارزیابی یک درس (فرایند ۵۷)."""
    from app.services.student_instructor_evaluation_service import (
        load_instance_for_student,
        submit_course_evaluation,
    )

    inst, student = await load_instance_for_student(db, instance_id, user)
    result = await submit_course_evaluation(
        db,
        inst,
        student,
        course_code,
        body.model_dump(),
    )
    await db.commit()
    return result


_INSTRUCTOR_EVAL_ROLES = frozenset({"admin", "staff", "instructor", "teaching_assistant"})


@router.get("/instructor/evaluation-results")
async def panel_instructor_evaluation_results(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    term_code: str | None = Query(None, description="کد ترم (پیش‌فرض: ترم فعال)"),
):
    """نتایج تجمیع‌شده ارزیابی مدرسین — فقط دروس انتساب‌یافته به مدرس."""
    role = (user.role or "").strip()
    if role not in _INSTRUCTOR_EVAL_ROLES:
        raise HTTPException(status_code=403, detail="دسترسی مدرس یا اپراتور لازم است")
    from app.services.student_instructor_evaluation_service import results_for_instructor

    return await results_for_instructor(db, user, term_code)


@router.get("/committee/evaluation-results")
async def panel_committee_evaluation_results(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    term_code: str | None = Query(None, description="کد ترم (پیش‌فرض: ترم فعال)"),
):
    """نتایج تجمیع‌شده ارزیابی — نمای کمیته دروس / پژوهش."""
    from app.services.student_instructor_evaluation_service import results_for_committee

    return await results_for_committee(db, user, term_code)
