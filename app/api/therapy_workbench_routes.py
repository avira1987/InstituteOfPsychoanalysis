"""API میزکار مقیاس‌پذیر درمان — خلاصه، جلسات صفحه‌بندی، تعمیر تک‌دانشجو."""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_role
from app.database import get_db
from app.models.operational_models import User
from app.services.therapy_session_schedule import repair_student_therapy_continuity
from app.services.therapy_workbench_service import (
    DEFAULT_PAGE_SIZE,
    get_workbench_sessions,
    get_workbench_summary,
    assert_can_repair_student,
)
from app.utils.shamsi_calendar_utils import parse_iso_date

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/therapy-workbench", tags=["TherapyWorkbench"])

RoleScope = Literal["therapist", "staff", "site_manager"]


def _resolve_role_scope(user: User, role_scope: Optional[str]) -> RoleScope:
    if role_scope:
        if role_scope not in ("therapist", "staff", "site_manager"):
            raise HTTPException(status_code=400, detail="role_scope نامعتبر است.")
        if role_scope == "therapist" and user.role != "therapist":
            raise HTTPException(status_code=403, detail="این scope فقط برای درمانگر است.")
        return role_scope  # type: ignore[return-value]
    if user.role == "therapist":
        return "therapist"
    if user.role == "site_manager":
        return "site_manager"
    return "staff"


@router.get("/summary")
async def therapy_workbench_summary(
    role_scope: Optional[str] = Query(None, description="therapist | staff | site_manager"),
    q: Optional[str] = Query(None, description="جستجوی کد دانشجو"),
    needs_action: Optional[bool] = Query(None),
    filter: Optional[str] = Query(
        None,
        alias="filter",
        description="needs_action | missing_future | needs_recording | today | week",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("therapist", "admin", "staff", "site_manager")),
):
    scope = _resolve_role_scope(current_user, role_scope)
    try:
        return await get_workbench_summary(
            db,
            current_user,
            role_scope=scope,
            q=q,
            needs_action=needs_action,
            filter_kind=filter,
            limit=limit,
            offset=offset,
        )
    except Exception:
        logger.exception("therapy_workbench_summary failed user=%s", current_user.id)
        raise HTTPException(status_code=500, detail="بارگذاری خلاصه میزکار ممکن نشد.")


@router.get("/sessions")
async def therapy_workbench_sessions(
    student_id: str = Query(..., description="شناسه دانشجو"),
    role_scope: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    status: Optional[str] = Query(None),
    needs_recording: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("therapist", "admin", "staff", "site_manager")),
):
    try:
        sid = uuid.UUID(student_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسهٔ دانشجو نامعتبر است.")

    scope = _resolve_role_scope(current_user, role_scope)
    from_d = parse_iso_date(from_date) if from_date else None
    to_d = parse_iso_date(to_date) if to_date else None

    if scope in ("staff", "site_manager") and not from_d and not to_d:
        raise HTTPException(
            status_code=400,
            detail="برای staff/site_manager پارامتر from و to الزامی است.",
        )

    try:
        return await get_workbench_sessions(
            db,
            current_user,
            role_scope=scope,
            student_id=sid,
            from_date=from_d,
            to_date=to_d,
            status=status,
            needs_recording=needs_recording,
            page=page,
            page_size=page_size,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("therapy_workbench_sessions failed student=%s", student_id)
        raise HTTPException(status_code=500, detail="بارگذاری جلسات ممکن نشد.")


@router.post("/repair/{student_id}")
async def therapy_workbench_repair(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("therapist", "admin", "staff", "site_manager")),
):
    try:
        sid = uuid.UUID(student_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="شناسهٔ دانشجو نامعتبر است.")

    try:
        await assert_can_repair_student(db, current_user, sid)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        result = await repair_student_therapy_continuity(db, sid)
        if (result.get("seed") or {}).get("created") or (result.get("session_payment") or {}).get("started"):
            await db.commit()
        return result
    except Exception:
        logger.exception("therapy_workbench_repair failed student=%s", student_id)
        raise HTTPException(status_code=500, detail="تعمیر تقویم درمان ممکن نشد.")
