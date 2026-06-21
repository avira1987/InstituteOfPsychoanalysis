"""پنل نقش‌ها — صف اقدامات پیشنهادی برای UI و اتوماسیون."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_admin_only
from app.database import get_db
from app.meta.student_lifecycle_matrix import get_panel_action_queue_for_role
from app.models.operational_models import User
from app.services.nav_pending_counts import compute_nav_pending_counts
from app.services.operator_followup_inbox import build_operator_followup_inbox_full
from app.services.operator_readiness import compute_operator_readiness_alerts
from app.services.panel_action_notifications import build_action_notifications
from app.services.panel_task_reminders import dismiss_panel_task_reminder, load_active_panel_reminders
from app.services.portal_role_inbox import build_portal_role_process_inbox
from app.services import sms_simulation_service

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
    ok = await dismiss_panel_task_reminder(db, reminder_id=reminder_id, user_id=user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="reminder not found")
    await db.commit()
    return {"ok": True}


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
